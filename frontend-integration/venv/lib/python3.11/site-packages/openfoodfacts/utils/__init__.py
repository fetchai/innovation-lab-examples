import dataclasses
import gzip
import json
import logging
import shutil
import time
from io import BytesIO
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Union

import requests
import tqdm

from ..types import COUNTRY_CODE_TO_NAME, Country, Environment, Flavor

_orjson_available = True
try:
    import orjson
except ImportError:
    _orjson_available = False

_pillow_available = True
try:
    import PIL
    from PIL import Image
except ImportError:
    _pillow_available = False

http_session = requests.Session()
http_session.headers.update({"User-Agent": "openfoodfacts-python"})


def configure_root_logger(
    logger: logging.Logger,
    level: int = logging.INFO,
    formatter_string: Optional[str] = None,
):
    logger.setLevel(level)
    handler = logging.StreamHandler()

    if formatter_string is None:
        formatter_string = "%(asctime)s :: %(levelname)s :: %(message)s"

    formatter = logging.Formatter(formatter_string)
    handler.setFormatter(formatter)
    handler.setLevel(level)
    logger.addHandler(handler)
    return logger


def get_logger(name=None, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if name is None:
        configure_root_logger(logger, level)

    return logger


logger = get_logger(__name__)


class URLBuilder:
    """URLBuilder allows to generate URLs for Product Opener/Robotoff.

    Example usage: URLBuilder.robotoff() returns the Robotoff URL.
    """

    @staticmethod
    def _get_url(
        base_domain: str,
        prefix: Optional[str] = "world",
        tld: str = "org",
        scheme: Optional[str] = None,
    ):
        data = {
            "domain": f"{base_domain}.{tld}",
            "scheme": "https",
        }
        if prefix:
            data["prefix"] = prefix
        if scheme:
            data["scheme"] = scheme

        if "prefix" in data:
            return "%(scheme)s://%(prefix)s.%(domain)s" % data

        return "%(scheme)s://%(domain)s" % data

    @staticmethod
    def world(flavor: Flavor, environment: Environment):
        return URLBuilder._get_url(
            prefix="world", tld=environment.value, base_domain=flavor.get_base_domain()
        )

    @staticmethod
    def robotoff(environment: Environment) -> str:
        return URLBuilder._get_url(
            prefix="robotoff",
            tld=environment.value,
            base_domain=Flavor.off.get_base_domain(),
        )

    @staticmethod
    def static(flavor: Flavor, environment: Environment) -> str:
        return URLBuilder._get_url(
            prefix="static", tld=environment.value, base_domain=flavor.get_base_domain()
        )

    @staticmethod
    def image_url(flavor: Flavor, environment: Environment, image_path: str) -> str:
        prefix = URLBuilder._get_url(
            prefix="images", tld=environment.value, base_domain=flavor.get_base_domain()
        )
        return prefix + f"/images/products{image_path}"

    @staticmethod
    def country(flavor: Flavor, environment: Environment, country_code: str) -> str:
        return URLBuilder._get_url(
            prefix=country_code,
            tld=environment.value,
            base_domain=flavor.get_base_domain(),
        )


def jsonl_iter(jsonl_path: Union[str, Path]) -> Iterable[Dict]:
    """Iterate over elements of a JSONL file.

    :param jsonl_path: the path of the JSONL file. Both plain (.jsonl) and
        gzipped (jsonl.gz) files are supported.
    :yield: dict contained in the JSONL file
    """
    open_fn = get_open_fn(jsonl_path)

    with open_fn(str(jsonl_path), "rt", encoding="utf-8") as f:
        yield from jsonl_iter_fp(f)


def get_open_fn(filepath: Union[str, Path]) -> Callable:
    filepath = str(filepath)
    if filepath.endswith(".gz"):
        return gzip.open
    else:
        return open


def jsonl_iter_fp(fp) -> Iterable[Dict]:
    for line in fp:
        line = line.strip("\n")
        if line:
            if _orjson_available:
                yield orjson.loads(line)
            else:
                yield json.loads(line)


def load_json(filepath: Union[str, Path]) -> Union[Dict, List]:
    """Load a JSON file, support gzipped JSON files.

    :param path: the path of the file
    """
    open = get_open_fn(filepath)
    with open(filepath, "rb") as f:
        if _orjson_available:
            return orjson.loads(f.read())
        else:
            return json.loads(f.read().decode("utf-8"))


def _sanitize_file_path(file_path: Path, suffix: str = "") -> Path:
    """A internal function to normalize cached filenames.

    :param file_path: the cached file path
    :param suffix: a optional filename suffix to add
    :return: a sanitized filepath
    """
    return file_path.with_name(file_path.name.replace(".", "_") + suffix)


def download_file(url: str, output_path: Path):
    """Download a dataset file and store it in `output_path`.

    The file metadata (`etag`, `url`, `created_at`) are stored in a JSON
        file whose name is derived from `output_path`
    :param url: the file URL
    :param output_path: the file output path
    """
    r = http_session.get(url, stream=True)
    etag = r.headers.get("ETag", "").strip("'\"")

    tmp_output_path = output_path.with_name(output_path.name + ".part")
    with tmp_output_path.open("wb") as f, tqdm.tqdm(
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        miniters=1,
        desc=str(output_path),
        total=int(r.headers.get("content-length", 0)),
    ) as pbar:
        for chunk in r.iter_content(chunk_size=4096):
            f.write(chunk)
            pbar.update(len(chunk))

    shutil.move(tmp_output_path, output_path)

    _sanitize_file_path(output_path, ".json").write_text(
        json.dumps(
            {
                "etag": etag,
                "created_at": int(time.time()),
                "url": url,
            }
        )
    )


def get_file_etag(dataset_path: Path) -> Optional[str]:
    """Return a dataset Etag.

    :param dataset_path: the path of the dataset
    :return: the file Etag
    """
    metadata_path = _sanitize_file_path(dataset_path, ".json")

    if metadata_path.is_file():
        return json.loads(metadata_path.read_text())["etag"]

    return None


def fetch_etag(url: str) -> str:
    """Get the Etag of a remote file.

    :param url: the file URL
    :return: the Etag
    """
    r = http_session.head(url)
    return r.headers.get("ETag", "").strip("'\"")


def should_download_file(
    url: str, filepath: Path, force_download: bool, download_newer: bool
) -> bool:
    """Return True if the file located at `url` should be downloaded again.

    :param url: the file URL
    :param filepath: the file cached location
    :param force_download: if True, (re)download the file even if it was
        cached, defaults to False
    :param download_newer: if True, download the dataset if a more recent
        version compared to the cached version is available (based on file
        Etag). This parameter if ignored if force_download is True, defaults
        to False.
    :return: True if the file should be downloaded again, False otherwise
    """
    if filepath.is_file():
        if force_download:
            # Always download the file if force_download is True
            return True

        if download_newer:
            # Check if the file is up to date
            cached_etag = get_file_etag(filepath)
            current_etag = fetch_etag(url)
            return cached_etag != current_etag
        else:
            # The file exists, no need to download it again
            return False

    return True


def get_country_name(country: Country) -> str:
    """Return country name code (ex: `en:portugal`) from `Country`."""
    return COUNTRY_CODE_TO_NAME[country]


class AssetLoadingException(Exception):
    """Exception raised by `get_asset_from_url` when an asset cannot be fetched
    from URL or if loading failed.
    """

    pass


@dataclasses.dataclass
class AssetDownloadItem:
    """ "The result of a asset download operation.

    :param url: the URL of the asset
    :param response: the requests response object (or None)
    :param error: the error message if an error occured (or None)
    """

    url: str
    response: Optional[requests.Response] = None
    error: Optional[str] = None


@dataclasses.dataclass
class ImageDownloadItem(AssetDownloadItem):
    """The result of a image download operation.

    :param image: the loaded PIL image, or None if an error occured
    :param image_bytes: the image bytes, or None if an error occured
    """

    image: Optional["Image.Image"] = None
    image_bytes: Optional[bytes] = None


def get_asset_from_url(
    asset_url: str,
    error_raise: bool = True,
    session: Optional[requests.Session] = None,
    auth: Optional[tuple[str, str]] = None,
) -> AssetDownloadItem:
    try:
        if session:
            r = session.get(asset_url, auth=auth)
        else:
            r = requests.get(asset_url, auth=auth)
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.SSLError,
        requests.exceptions.Timeout,
    ) as e:
        error_message = "Cannot download %s"
        if error_raise:
            raise AssetLoadingException(error_message % asset_url) from e
        logger.info(error_message, asset_url, exc_info=e)
        return AssetDownloadItem(asset_url, error=error_message % asset_url)

    if not r.ok:
        error_message = "Cannot download %s: HTTP %s"
        error_args = (asset_url, r.status_code)
        if error_raise:
            raise AssetLoadingException(error_message % error_args)
        logger.log(
            logging.INFO if r.status_code < 500 else logging.WARNING,
            error_message,
            *error_args,
        )
        return AssetDownloadItem(
            asset_url, response=r, error=error_message % error_args
        )

    return AssetDownloadItem(asset_url, response=r)


def get_image_from_url(
    image_url: str,
    error_raise: bool = True,
    session: Optional[requests.Session] = None,
    return_struct: bool = False,
) -> Union[ImageDownloadItem, "Image.Image", None]:
    """Fetch an image from `image_url` and load it.

    :param image_url: URL of the image to load.
    :param error_raise: if True, raises a `AssetLoadingException` if an error
      occured, defaults to False. If False, None is returned if an error
      occured.
    :param session: requests Session to use, by default no session is used.
    :param return_struct: if True, return a `ImageDownloadItem` object
        containing the image, image bytes and the response object.
    :return: the loaded image, or None if an error occured and `error_raise`
        is False. If `return_struct` is True, return a `ImageDownloadItem`
        object.
    """
    if not _pillow_available:
        raise ImportError("Pillow is required to load images")

    asset_item = get_asset_from_url(image_url, error_raise, session)
    response = asset_item.response
    if response is None or asset_item.error:
        if return_struct:
            return ImageDownloadItem(
                url=image_url, response=response, error=asset_item.error
            )
        else:
            return None

    content_bytes = response.content
    try:
        image = Image.open(BytesIO(content_bytes))
        if return_struct:
            return ImageDownloadItem(
                url=image_url,
                response=response,
                image=image,
                image_bytes=content_bytes,
            )
        return image
    except PIL.UnidentifiedImageError:
        error_message = f"Cannot identify image {image_url}"
        if error_raise:
            raise AssetLoadingException(error_message)
        logger.info(error_message)
    except PIL.Image.DecompressionBombError:
        error_message = f"Decompression bomb error for image {image_url}"
        if error_raise:
            raise AssetLoadingException(error_message)
        logger.info(error_message)

    if return_struct:
        return ImageDownloadItem(url=image_url, response=response, error=error_message)

    return None
