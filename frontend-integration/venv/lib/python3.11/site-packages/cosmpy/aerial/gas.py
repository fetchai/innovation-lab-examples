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

"""Transaction gas strategy."""

from abc import ABC, abstractmethod
from typing import Dict, Optional

from cosmpy.aerial.tx import Transaction


class GasStrategy(ABC):
    """Transaction gas strategy."""

    @abstractmethod
    def estimate_gas(self, tx: Transaction) -> int:
        """Estimate the transaction gas.

        :param tx: Transaction
        :return: None
        """

    @abstractmethod
    def block_gas_limit(self) -> int:
        """Get the block gas limit.

        :return: None
        """

    def _clip_gas(self, value: int) -> int:
        block_limit = self.block_gas_limit()
        if block_limit < 0:
            return value

        return min(value, block_limit)


class SimulationGasStrategy(GasStrategy):
    """Simulation transaction gas strategy.

    :param GasStrategy: gas strategy
    """

    DEFAULT_MULTIPLIER = 1.65

    def __init__(self, client: "LedgerClient", multiplier: Optional[float] = None):  # type: ignore # noqa: F821
        """Init the Simulation transaction gas strategy.

        :param client: Ledger client
        :param multiplier: multiplier, defaults to None
        """
        self._client = client
        self._max_gas: Optional[int] = None
        self._multiplier = multiplier or self.DEFAULT_MULTIPLIER

    def estimate_gas(self, tx: Transaction) -> int:
        """Get estimated transaction gas.

        :param tx: transaction
        :return: Estimated transaction gas
        """
        gas_estimate = self._client.simulate_tx(tx)
        return self._clip_gas(int(gas_estimate * self._multiplier))

    def block_gas_limit(self) -> int:
        """Get the block gas limit.

        :return: block gas limit
        """
        if self._max_gas is None:
            block_params = self._client.query_params("baseapp", "BlockParams")
            self._max_gas = int(block_params["max_gas"])

        return self._max_gas or -1


class OfflineMessageTableStrategy(GasStrategy):
    """Offline message table strategy.

    :param GasStrategy: gas strategy
    """

    DEFAULT_FALLBACK_GAS_LIMIT = 400_000
    DEFAULT_BLOCK_LIMIT = 2_000_000

    @staticmethod
    def default_table() -> "OfflineMessageTableStrategy":
        """offline message strategy default table.

        :return: offline message default table strategy
        """
        strategy = OfflineMessageTableStrategy()
        strategy.update_entry("cosmos.bank.v1beta1.MsgSend", 100_000)
        strategy.update_entry("cosmwasm.wasm.v1.MsgStoreCode", 2_000_000)
        strategy.update_entry("cosmwasm.wasm.v1.MsgInstantiateContract", 250_000)
        strategy.update_entry("cosmwasm.wasm.v1.MsgExecuteContract", 400_000)
        return strategy

    def __init__(
        self,
        fallback_gas_limit: Optional[int] = None,
        block_limit: Optional[int] = None,
    ):
        """Init offline message table strategy.

        :param fallback_gas_limit: Fallback gas limit, defaults to None
        :param block_limit: Block limit, defaults to None
        """
        self._table: Dict[str, int] = {}
        self._block_limit = block_limit or self.DEFAULT_BLOCK_LIMIT
        self._fallback_gas_limit = fallback_gas_limit or self.DEFAULT_FALLBACK_GAS_LIMIT

    def update_entry(self, transaction_type: str, gas_limit: int):
        """Update the entry of the transaction.

        :param transaction_type: transaction type
        :param gas_limit: gas limit
        """
        self._table[str(transaction_type)] = int(gas_limit)

    def estimate_gas(self, tx: Transaction) -> int:
        """Get estimated transaction gas.

        :param tx: transaction
        :return: Estimated transaction gas
        """
        gas_estimate = 0
        for msg in tx.msgs:
            gas_estimate += self._table.get(
                msg.DESCRIPTOR.full_name, self._fallback_gas_limit
            )
        return self._clip_gas(gas_estimate)

    def block_gas_limit(self) -> int:
        """Get the block gas limit.

        :return: block gas limit
        """
        return self._block_limit
