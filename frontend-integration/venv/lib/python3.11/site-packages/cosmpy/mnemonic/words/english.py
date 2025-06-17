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

"""Mnemonic words."""
import base64
import gzip
from typing import List


def decompress_words(encoded_data: str) -> List[str]:
    """
    Decode base64 encoded and compressed list of words.

    :param encoded_data: str The base64 encoded compressed data.

    :return: List[str] The decoded and decompressed list of words.
    """
    decoded_data = base64.b64decode(encoded_data)
    decompressed_data = gzip.decompress(decoded_data).decode()
    return decompressed_data.split(",")


ENGLISH_COMPRESSED = (
    "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"
)

ENGLISH_MNEMONIC_WORDS_LIST = decompress_words(ENGLISH_COMPRESSED)
ENGLISH_MNEMONIC_WORDS = set(ENGLISH_MNEMONIC_WORDS_LIST)
