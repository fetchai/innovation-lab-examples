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

"""Exceptions."""


class QueryError(RuntimeError):
    """Invalid Query Error."""


class NotFoundError(QueryError):
    """Not found Error."""


class QueryTimeoutError(QueryError):
    """Query timeout Error."""


class BroadcastError(RuntimeError):
    """Broadcast Error."""

    def __init__(self, tx_hash: str, message: str):
        """Init Broadcast error.

        :param tx_hash: transaction hash
        :param message: message
        """
        super().__init__(message)
        self.tx_hash = tx_hash


class OutOfGasError(BroadcastError):
    """Insufficient Fess Error."""

    def __init__(self, tx_hash: str, gas_wanted: int, gas_used: int):
        """Initialize.

        :param tx_hash: transaction hash
        :param gas_wanted: gas required to complete the transaction
        :param gas_used: gas used
        """
        self.gas_wanted = gas_wanted
        self.gas_used = gas_used
        super().__init__(
            tx_hash, f"Out of Gas (wanted: {self.gas_wanted}, used: {self.gas_used})"
        )


class InsufficientFeesError(BroadcastError):
    """Insufficient Fess Error."""

    def __init__(self, tx_hash: str, minimum_required_fee: str):
        """Initialize.

        :param tx_hash: transaction hash
        :param minimum_required_fee: Minimum required fee
        """
        self.minimum_required_fee = minimum_required_fee
        super().__init__(
            tx_hash,
            f"Insufficient Fees (minimum required: {self.minimum_required_fee})",
        )
