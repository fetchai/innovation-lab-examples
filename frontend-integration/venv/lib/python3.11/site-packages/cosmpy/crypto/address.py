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

"""Address of the Crypto package."""

from collections import UserString
from typing import Optional, Union

import bech32

from cosmpy.crypto.hashfuncs import ripemd160, sha256
from cosmpy.crypto.keypairs import PublicKey


DEFAULT_PREFIX = "fetch"


def _to_bech32(prefix: str, data: bytes) -> str:
    data_base5 = bech32.convertbits(data, 8, 5, True)
    if data_base5 is None:
        raise RuntimeError("Unable to parse address")  # pragma: no cover
    return bech32.bech32_encode(prefix, data_base5)


class Address(UserString):
    """Address class."""

    def __init__(
        self,
        value: Union[str, bytes, PublicKey, "Address"],
        prefix: Optional[str] = None,
    ):
        """Initialize Address instance.

        :param value: str, byte, public key or Address another instance
        :param prefix: optional string
        :raises RuntimeError: Unable to parse address
        :raises RuntimeError: Incorrect address length
        :raises TypeError: Unexpected type of `value` parameter
        """
        # pylint: disable=super-init-not-called
        if prefix is None:
            prefix = DEFAULT_PREFIX

        if isinstance(value, str):
            _, data_base5 = bech32.bech32_decode(value)
            if data_base5 is None:
                raise RuntimeError("Unable to parse address")

            data_base8 = bech32.convertbits(data_base5, 5, 8, False)
            if data_base8 is None:
                raise RuntimeError("Unable to parse address")  # pragma: no cover

            self._address = bytes(data_base8)
            self._display = value

        elif isinstance(value, bytes):
            if len(value) != 20:
                raise RuntimeError("Incorrect address length")

            self._address = value
            self._display = _to_bech32(prefix, self._address)

        elif isinstance(value, PublicKey):
            self._address = ripemd160(sha256(value.public_key_bytes))
            self._display = _to_bech32(prefix, self._address)

        elif isinstance(value, Address):
            self._address = value._address
            # prefix might be different from the original Address, so we need to reencode it here.
            self._display = _to_bech32(prefix, self._address)
        else:
            raise TypeError("Unexpected type of `value` parameter")  # pragma: no cover

    def __str__(self):
        """String representation of the address."""  # noqa: D401
        return self._display

    def __bytes__(self):
        """bytes representation of the address."""
        return self._address

    @property
    def data(self):  # noqa:
        """Return address in string."""
        return str(self)

    def __json__(self):  # noqa:
        return str(self)
