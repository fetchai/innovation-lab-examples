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

"""Hash functions of Crypto package."""

import hashlib

from Crypto.Hash import RIPEMD160  # type: ignore # nosec


def sha256(contents: bytes) -> bytes:
    """
    Get sha256 hash.

    :param contents: bytes contents.

    :return: bytes sha256 hash.
    """
    h = hashlib.sha256()
    h.update(contents)
    return h.digest()


def ripemd160(contents: bytes) -> bytes:
    """
    Get ripemd160 hash using PyCryptodome.

    :param contents: bytes contents.

    :return: bytes ripemd160 hash.
    """
    h = RIPEMD160.new()
    h.update(contents)
    return h.digest()
