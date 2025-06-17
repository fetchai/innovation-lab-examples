# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2018-2021 Fetch.AI Limited
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""Types."""


from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, List

from google.protobuf.timestamp_pb2 import Timestamp

from cosmpy.crypto.address import Address
from cosmpy.crypto.hashfuncs import sha256


@dataclass
class Account:
    """Account."""

    address: Address
    number: int
    sequence: int


@dataclass
class Block:
    """Block."""

    height: int
    time: datetime
    chain_id: str
    tx_hashes: List[str]

    @staticmethod
    def from_proto(block: Any) -> "Block":
        """Parse the block.

        :param block: block as Any
        :return: parsed block as Block
        """
        return Block(
            height=int(block.header.height),
            time=Block._parse_timestamp(block.header.time),
            tx_hashes=[sha256(tx).hex().upper() for tx in block.data.txs],
            chain_id=block.header.chain_id,
        )

    @staticmethod
    def _parse_timestamp(timestamp: Timestamp):
        """Parse the timestamp.

        :param timestamp: timestamp
        :return: parsed timestamp
        """
        return datetime.fromtimestamp(timestamp.seconds, tz=timezone.utc) + timedelta(
            microseconds=timestamp.nanos // 1000
        )
