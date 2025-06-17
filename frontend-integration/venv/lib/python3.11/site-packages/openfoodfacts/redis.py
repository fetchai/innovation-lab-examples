import datetime
from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional, Union, cast

from pydantic import BaseModel, Json
from redis import Redis

from openfoodfacts.utils import get_logger

logger = get_logger(__name__)


def get_redis_client(**kwargs) -> Redis:
    return Redis(
        decode_responses=True,
        **kwargs,
    )


class RedisUpdate(BaseModel):
    """A class representing a product update from a Redis Stream."""

    # The Redis ID of the update
    id: str
    # The name of the Redis stream where the update was published
    stream: str
    # The timestamp of the update
    timestamp: datetime.datetime
    # The code of the product
    code: str
    # The flavor of the product (off, obf, opff, off_pro)
    flavor: str
    # The user ID of the user who performed the action
    user_id: str
    # The action performed by the user (either updated or deleted)
    action: str
    # A comment provided by the user
    comment: str
    # the type of the product (food, product, petfood, beauty)
    product_type: str
    # A JSON object representing the differences between the old and new
    # product data
    diffs: Optional[Json[Any]] = None

    def is_image_upload(self) -> bool:
        """Returns True if the update is an image upload."""
        return bool(
            self.diffs is not None
            and "uploaded_images" in self.diffs
            and "add" in self.diffs["uploaded_images"]
        )


def get_processed_since(
    redis_client: Redis,
    stream_name: str,
    min_id: Union[str, datetime.datetime],
    batch_size: int = 100,
) -> Iterator[RedisUpdate]:
    """Fetches all the updates that have been published since the given
    timestamp.

    :param redis_client: the Redis client
    :param stream_name: the name of the Redis stream to read from
    :param min_id: the minimum ID to start from, or a datetime object
    :param batch_size: the size of the batch to fetch, defaults to 100
    :yield: a RedisUpdate instance for each update
    """
    if isinstance(min_id, datetime.datetime):
        min_id = f"{int(min_id.timestamp() * 1000)}-0"

    while True:
        logger.debug(
            "Fetching batch from Redis, stream %s, min_id %s, count %d",
            stream_name,
            min_id,
            batch_size,
        )
        batch = redis_client.xrange(stream_name, min=min_id, count=batch_size)
        if not batch:
            # We reached the end of the stream
            break

        batch = cast(list[tuple[str, dict]], batch)
        # We update the min_id to the last ID of the batch
        min_id = f"({batch[-1][0]}"
        for timestamp_id, item in batch:
            # Get the timestamp from the ID
            timestamp = int(timestamp_id.split("-")[0])
            yield RedisUpdate(
                id=timestamp_id,
                timestamp=timestamp,  # type: ignore
                stream=stream_name,
                code=item["code"],
                flavor=item["flavor"],
                user_id=item["user_id"],
                action=item["action"],
                comment=item["comment"],
                product_type=item["product_type"],
                diffs=item.get("diffs"),
            )


def get_new_updates(
    redis_client: Redis,
    stream_name: str,
    min_id: Union[str, datetime.datetime, None] = "$",
    batch_size: int = 100,
) -> Iterator[RedisUpdate]:
    """Reads new updates from a Redis Stream, starting from the moment this
    function is called.

    The function will block until new updates are available.

    :param redis_client: the Redis client
    :param stream_name: the name of the Redis stream to read from
    :param min_id: the minimum ID to start from, defaults to "$".
        A datetime object can also be passed.
    :param batch_size: the size of the batch to fetch, defaults to 100
    :yield: a RedisUpdate instance for each update
    """
    yield from get_new_updates_multistream(
        redis_client=redis_client,
        stream_names=[stream_name],
        min_id=min_id,
        batch_size=batch_size,
    )


def get_new_updates_multistream(
    redis_client: Redis,
    stream_names: list[str],
    min_id: Union[str, datetime.datetime, None] = "$",
    batch_size: int = 100,
) -> Iterator[RedisUpdate]:
    """Reads new updates from Redis Stream, starting from the moment this
    function is called.

    The function will block until new updates are available.

    :param redis_client: the Redis client.
    :param stream_names: the names of the Redis streams to read from.
    :param min_id: the minimum ID to start from, defaults to "$".
    :param batch_size: the size of the batch to fetch, defaults to 100.
    :yield: a RedisUpdate instance for each update.
    """
    if min_id is None:
        min_id = "$"
    elif isinstance(min_id, datetime.datetime):
        min_id = f"{int(min_id.timestamp() * 1000)}-0"

    # We start from the last ID
    min_ids: dict[Union[bytes, str, memoryview], Union[int, bytes, str, memoryview]] = {
        stream_name: min_id for stream_name in stream_names
    }
    while True:
        logger.debug(
            "Listening to new updates from streams %s (ID: %s)", stream_names, min_ids
        )
        # We use block=0 to wait indefinitely for new updates
        response = redis_client.xread(streams=min_ids, block=0, count=batch_size)
        response = cast(list[tuple[str, list[tuple[str, dict]]]], response)
        # The response is a list of tuples (stream_name, batch)

        for stream_name, batch in response:
            # We update the min_id to the last ID of the batch
            new_min_id = batch[-1][0]
            min_ids[stream_name] = new_min_id
            for timestamp_id, item in batch:
                # Get the timestamp from the ID
                timestamp = int(timestamp_id.split("-")[0])
                yield RedisUpdate(
                    id=timestamp_id,
                    timestamp=timestamp,  # type: ignore
                    stream=stream_name,
                    code=item["code"],
                    flavor=item["flavor"],
                    user_id=item["user_id"],
                    action=item["action"],
                    comment=item["comment"],
                    product_type=item["product_type"],
                    diffs=item.get("diffs"),
                )


class UpdateListener(ABC):
    """A class representing a daemon that listens to updates from a Redis
    stream and processes them.

    The class is meant to be subclassed to implement the processing logic.
    Subclasses must implement the `process_redis_update` method.
    """

    def __init__(
        self, redis_client: Redis, redis_stream_name: str, redis_latest_id_key: str
    ):
        self.redis_client = redis_client
        self.redis_stream_name = redis_stream_name
        self.redis_latest_id_key = redis_latest_id_key

    def run(self):
        """Run the update import daemon.

        This daemon listens to the Redis stream containing information about
        product updates, and triggers
        """
        logger.info("Starting update listener daemon")

        logger.info("Redis client: %s", self.redis_client)
        logger.info("Pinging client...")
        self.redis_client.ping()
        logger.info("Connection successful")

        latest_id = self.redis_client.get(self.redis_latest_id_key)

        if latest_id:
            logger.info(
                "Latest ID processed: %s (datetime: %s)",
                latest_id,
                datetime.datetime.fromtimestamp(int(latest_id.split("-")[0]) / 1000),
            )
        else:
            logger.info("No latest ID found")

        for redis_update in get_new_updates(
            self.redis_client, stream_name=self.redis_stream_name, min_id=latest_id
        ):
            try:
                self.process_redis_update(redis_update)
            except Exception as e:
                logger.exception(e)
            self.redis_client.set(self.redis_latest_id_key, redis_update.id)

    def process_updates_since(
        self, since: datetime.datetime, to: Optional[datetime.datetime] = None
    ):
        """Process all the updates since the given timestamp.

        :param client: the Redis client
        :param since: the timestamp to start from
        :param to: the timestamp to stop, defaults to None (process all
            updates)
        """
        logger.info("Redis client: %s", self.redis_client)
        logger.info("Pinging client...")
        self.redis_client.ping()

        processed = 0
        for product_update in get_processed_since(
            self.redis_client, stream_name=self.redis_stream_name, min_id=since
        ):
            if to is not None and product_update.timestamp > to:
                break
            self.process_redis_update(product_update)
            processed += 1

        logger.info("Processed %d updates", processed)

    @abstractmethod
    def process_redis_update(self, redis_update: RedisUpdate):
        pass
