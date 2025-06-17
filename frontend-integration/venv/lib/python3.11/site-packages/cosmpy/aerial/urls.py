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

"""Parsing the URL."""

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


class Protocol(Enum):
    """Protocol Enum.

    :param Enum: Enum
    """

    GRPC = 1
    REST = 2


@dataclass
class ParsedUrl:
    """Parse URL.

    :return: Parsed URL
    """

    protocol: Protocol
    secure: bool
    hostname: str
    port: int

    @property
    def host_and_port(self) -> str:
        """Get the host and port of the url.

        :return: host and port
        """
        return f"{self.hostname}:{self.port}"

    @property
    def rest_url(self) -> str:
        """Get the rest url.

        :return: rest url
        """
        assert self.protocol == Protocol.REST
        if self.secure:
            prefix = "https"
            default_port = 443
        else:
            prefix = "http"
            default_port = 80

        url = f"{prefix}://{self.hostname}"
        if self.port != default_port:
            url += f":{self.port}"
        return url


def parse_url(url: str) -> ParsedUrl:
    """Initialize.

    :param url: url
    :raises RuntimeError: If url scheme is unsupported
    :return: Parsed URL
    """
    result = urlparse(url)
    if result.scheme == "grpc+https":
        protocol = Protocol.GRPC
        secure = True
        default_port = 443
    elif result.scheme == "grpc+http":
        protocol = Protocol.GRPC
        secure = False
        default_port = 80
    elif result.scheme == "rest+https":
        protocol = Protocol.REST
        secure = True
        default_port = 443
    elif result.scheme == "rest+http":
        protocol = Protocol.REST
        secure = False
        default_port = 80
    else:
        raise RuntimeError(f"Unsupported url scheme: {result.scheme}")

    hostname = str(result.hostname)
    port = default_port if result.port is None else int(result.port)

    return ParsedUrl(protocol=protocol, secure=secure, hostname=hostname, port=port)
