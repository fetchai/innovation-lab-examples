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

"""Interface for a Signer."""

from abc import ABC, abstractmethod


class Signer(ABC):
    """Signer abstract class."""

    @abstractmethod
    def sign(
        self, message: bytes, deterministic: bool = False, canonicalise: bool = True
    ) -> bytes:
        """
        Perform signing.

        :param message: bytes to sign
        :param deterministic: bool, default false
        :param canonicalise: bool,default True
        """

    @abstractmethod
    def sign_digest(
        self, digest: bytes, deterministic=False, canonicalise: bool = True
    ) -> bytes:
        """
        Perform digest signing.

        :param digest: bytes to sign
        :param deterministic: bool, default false
        :param canonicalise: bool,default True
        """
