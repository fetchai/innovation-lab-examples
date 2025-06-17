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

"""Client functionality."""

import json
import math
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import certifi
import grpc
from dateutil.parser import isoparse

from cosmpy.aerial import cast_to_int
from cosmpy.aerial.client.bank import create_bank_send_msg
from cosmpy.aerial.client.distribution import create_withdraw_delegator_reward
from cosmpy.aerial.client.staking import (
    StakingPosition,
    StakingSummary,
    UnbondingPositions,
    Validator,
    ValidatorStatus,
    create_delegate_msg,
    create_redelegate_msg,
    create_undelegate_msg,
)
from cosmpy.aerial.client.utils import (
    TxFee,
    ensure_timedelta,
    get_paginated,
    prepare_and_broadcast_basic_transaction,
)
from cosmpy.aerial.coins import Coin
from cosmpy.aerial.config import NetworkConfig
from cosmpy.aerial.exceptions import NotFoundError, QueryTimeoutError
from cosmpy.aerial.gas import GasStrategy, SimulationGasStrategy
from cosmpy.aerial.tx import Transaction, TxState
from cosmpy.aerial.tx_helpers import MessageLog, SubmittedTx, TxResponse
from cosmpy.aerial.types import Account, Block
from cosmpy.aerial.urls import Protocol, parse_url
from cosmpy.aerial.wallet import Wallet
from cosmpy.auth.rest_client import AuthRestClient
from cosmpy.bank.rest_client import BankRestClient
from cosmpy.common.rest_client import RestClient
from cosmpy.cosmwasm.rest_client import CosmWasmRestClient
from cosmpy.crypto.address import Address
from cosmpy.distribution.rest_client import DistributionRestClient
from cosmpy.params.rest_client import ParamsRestClient
from cosmpy.protos.cosmos.auth.v1beta1.auth_pb2 import BaseAccount
from cosmpy.protos.cosmos.auth.v1beta1.query_pb2 import QueryAccountRequest
from cosmpy.protos.cosmos.auth.v1beta1.query_pb2_grpc import QueryStub as AuthGrpcClient
from cosmpy.protos.cosmos.bank.v1beta1.query_pb2 import (
    QueryAllBalancesRequest,
    QueryBalanceRequest,
)
from cosmpy.protos.cosmos.bank.v1beta1.query_pb2_grpc import QueryStub as BankGrpcClient
from cosmpy.protos.cosmos.base.tendermint.v1beta1.query_pb2 import (
    GetBlockByHeightRequest,
    GetLatestBlockRequest,
)
from cosmpy.protos.cosmos.base.tendermint.v1beta1.query_pb2_grpc import (
    ServiceStub as TendermintQueryGrpcClient,
)
from cosmpy.protos.cosmos.crypto.ed25519.keys_pb2 import (  # noqa # pylint: disable=unused-import
    PubKey,
)
from cosmpy.protos.cosmos.distribution.v1beta1.query_pb2 import (
    QueryDelegationRewardsRequest,
)
from cosmpy.protos.cosmos.distribution.v1beta1.query_pb2_grpc import (
    QueryStub as DistributionGrpcClient,
)
from cosmpy.protos.cosmos.params.v1beta1.query_pb2 import QueryParamsRequest
from cosmpy.protos.cosmos.params.v1beta1.query_pb2_grpc import (
    QueryStub as QueryParamsGrpcClient,
)
from cosmpy.protos.cosmos.staking.v1beta1.query_pb2 import (
    QueryDelegatorDelegationsRequest,
    QueryDelegatorUnbondingDelegationsRequest,
    QueryValidatorsRequest,
)
from cosmpy.protos.cosmos.staking.v1beta1.query_pb2_grpc import (
    QueryStub as StakingGrpcClient,
)
from cosmpy.protos.cosmos.tx.v1beta1.service_pb2 import (
    BroadcastMode,
    BroadcastTxRequest,
    GetTxRequest,
    SimulateRequest,
)
from cosmpy.protos.cosmos.tx.v1beta1.service_pb2_grpc import ServiceStub as TxGrpcClient
from cosmpy.protos.cosmwasm.wasm.v1.query_pb2_grpc import (
    QueryStub as CosmWasmGrpcClient,
)
from cosmpy.staking.rest_client import StakingRestClient
from cosmpy.tendermint.rest_client import (
    CosmosBaseTendermintRestClient as TendermintRestClient,
)
from cosmpy.tx.rest_client import TxRestClient


DEFAULT_QUERY_TIMEOUT_SECS = 15
DEFAULT_QUERY_INTERVAL_SECS = 2
COSMOS_SDK_DEC_COIN_PRECISION = 10**18


class LedgerClient:
    """Ledger client."""

    def __init__(
        self,
        cfg: NetworkConfig,
        query_interval_secs: int = DEFAULT_QUERY_INTERVAL_SECS,
        query_timeout_secs: int = DEFAULT_QUERY_TIMEOUT_SECS,
    ):
        """Init ledger client.

        :param cfg: Network configurations
        :param query_interval_secs: int. optional interval int seconds
        :param query_timeout_secs: int. optional interval int seconds
        """
        self._query_interval_secs = query_interval_secs
        self._query_timeout_secs = query_timeout_secs
        cfg.validate()
        self._network_config = cfg
        self._gas_strategy: GasStrategy = SimulationGasStrategy(self)

        parsed_url = parse_url(cfg.url)

        if parsed_url.protocol == Protocol.GRPC:
            if parsed_url.secure:
                with open(certifi.where(), "rb") as f:
                    trusted_certs = f.read()
                credentials = grpc.ssl_channel_credentials(
                    root_certificates=trusted_certs
                )
                grpc_client = grpc.secure_channel(parsed_url.host_and_port, credentials)
            else:
                grpc_client = grpc.insecure_channel(parsed_url.host_and_port)

            self.wasm = CosmWasmGrpcClient(grpc_client)
            self.auth = AuthGrpcClient(grpc_client)
            self.txs = TxGrpcClient(grpc_client)
            self.bank = BankGrpcClient(grpc_client)
            self.staking = StakingGrpcClient(grpc_client)
            self.distribution = DistributionGrpcClient(grpc_client)
            self.params = QueryParamsGrpcClient(grpc_client)
            self.tendermint = TendermintQueryGrpcClient(grpc_client)
        else:
            rest_client = RestClient(parsed_url.rest_url)

            self.wasm = CosmWasmRestClient(rest_client)  # type: ignore
            self.auth = AuthRestClient(rest_client)  # type: ignore
            self.txs = TxRestClient(rest_client)  # type: ignore
            self.bank = BankRestClient(rest_client)  # type: ignore
            self.staking = StakingRestClient(rest_client)  # type: ignore
            self.distribution = DistributionRestClient(rest_client)  # type: ignore
            self.params = ParamsRestClient(rest_client)  # type: ignore
            self.tendermint = TendermintRestClient(rest_client)  # type: ignore

    @property
    def network_config(self) -> NetworkConfig:
        """Get the network config.

        :return: network config
        """
        return self._network_config

    @property
    def gas_strategy(self) -> GasStrategy:
        """Get gas strategy.

        :return: gas strategy
        """
        return self._gas_strategy

    @gas_strategy.setter
    def gas_strategy(self, strategy: GasStrategy):
        """Set gas strategy.

        :param strategy: strategy
        :raises RuntimeError: Invalid strategy must implement GasStrategy interface
        """
        if not isinstance(strategy, GasStrategy):
            raise RuntimeError("Invalid strategy must implement GasStrategy interface")
        self._gas_strategy = strategy

    def query_account(self, address: Address) -> Account:
        """Query account.

        :param address: address
        :raises RuntimeError: Unexpected account type returned from query
        :return: account details
        """
        request = QueryAccountRequest(address=str(address))
        response = self.auth.Account(request)

        account = BaseAccount()
        if not response.account.Is(BaseAccount.DESCRIPTOR):
            raise RuntimeError("Unexpected account type returned from query")
        response.account.Unpack(account)

        return Account(
            address=address,
            number=account.account_number,
            sequence=account.sequence,
        )

    def query_params(self, subspace: str, key: str) -> Any:
        """Query Prams.

        :param subspace: subspace
        :param key: key
        :return: Query params
        """
        req = QueryParamsRequest(subspace=subspace, key=key)
        resp = self.params.Params(req)
        return json.loads(resp.param.value)

    def query_bank_balance(self, address: Address, denom: Optional[str] = None) -> int:
        """Query bank balance.

        :param address: address
        :param denom: denom, defaults to None
        :return: bank balance
        """
        denom = denom or self.network_config.fee_denomination

        req = QueryBalanceRequest(
            address=str(address),
            denom=denom,
        )

        resp = self.bank.Balance(req)
        assert resp.balance.denom == denom  # sanity check

        return int(resp.balance.amount)

    def query_bank_all_balances(self, address: Address) -> List[Coin]:
        """Query bank all balances.

        :param address: address
        :return: bank all balances
        """
        req = QueryAllBalancesRequest(address=str(address))
        resp = self.bank.AllBalances(req)

        return [Coin(amount=coin.amount, denom=coin.denom) for coin in resp.balances]

    def send_tokens(
        self,
        destination: Address,
        amount: int,
        denom: str,
        sender: Wallet,
        memo: Optional[str] = None,
        fee: Optional[TxFee] = None,
        timeout_height: Optional[int] = None,
    ) -> SubmittedTx:
        """Send tokens.

        :param destination: destination address
        :param amount: amount
        :param denom: denom
        :param sender: sender
        :param memo: memo, defaults to None
        :param fee: transaction fee, defaults to None
        :param timeout_height: timeout height, defaults to None
        :return: prepare and broadcast the transaction and transaction details
        """
        # build up the store transaction
        tx = Transaction()
        tx.add_message(
            create_bank_send_msg(sender.address(), destination, amount, denom)
        )

        return prepare_and_broadcast_basic_transaction(
            self,
            tx,
            sender,
            fee=fee,
            memo=memo,
            timeout_height=timeout_height,
        )

    def query_validators(
        self, status: Optional[ValidatorStatus] = None
    ) -> List[Validator]:
        """Query validators.

        :param status: validator status, defaults to None
        :return: List of validators
        """
        filtered_status = status or ValidatorStatus.BONDED

        req = QueryValidatorsRequest()
        if filtered_status != ValidatorStatus.UNSPECIFIED:
            req.status = filtered_status.value

        resp = self.staking.Validators(req)

        validators: List[Validator] = []
        for validator in resp.validators:
            validators.append(
                Validator(
                    address=Address(validator.operator_address),
                    tokens=cast_to_int(validator.tokens, False),
                    moniker=str(validator.description.moniker),
                    status=ValidatorStatus.from_proto(validator.status),
                )
            )
        return validators

    def query_staking_summary(self, address: Address) -> StakingSummary:
        """Query staking summary.

        :param address: address
        :return: staking summary
        """
        current_positions: List[StakingPosition] = []

        req = QueryDelegatorDelegationsRequest(delegator_addr=str(address))

        for resp in get_paginated(
            req, self.staking.DelegatorDelegations, per_page_limit=1
        ):
            for item in resp.delegation_responses:
                req = QueryDelegationRewardsRequest(
                    delegator_address=str(address),
                    validator_address=str(item.delegation.validator_address),
                )
                rewards_resp = self.distribution.DelegationRewards(req)

                stake_reward_dec = Decimal(0)
                stake_reward = 0
                for reward in rewards_resp.rewards:
                    if reward.denom == self.network_config.staking_denomination:
                        stake_reward_dec = Decimal(reward.amount)
                        stake_reward = cast_to_int(reward.amount, False)
                        break

                current_positions.append(
                    StakingPosition(
                        validator=Address(item.delegation.validator_address),
                        amount=cast_to_int(item.balance.amount, False),
                        reward=stake_reward,
                        reward_dec=stake_reward_dec,
                    )
                )

        unbonding_summary: Dict[str, int] = {}
        req = QueryDelegatorUnbondingDelegationsRequest(delegator_addr=str(address))

        for resp in get_paginated(req, self.staking.DelegatorUnbondingDelegations):
            for item in resp.unbonding_responses:
                validator = str(item.validator_address)
                total_unbonding = unbonding_summary.get(validator, 0)

                for entry in item.entries:
                    total_unbonding += cast_to_int(entry.balance, False)

                unbonding_summary[validator] = total_unbonding

        # build the final list of unbonding positions
        unbonding_positions: List[UnbondingPositions] = []
        for validator, total_unbonding in unbonding_summary.items():
            unbonding_positions.append(
                UnbondingPositions(
                    validator=Address(validator),
                    amount=total_unbonding,
                )
            )

        return StakingSummary(
            current_positions=current_positions, unbonding_positions=unbonding_positions
        )

    def delegate_tokens(
        self,
        validator: Address,
        amount: int,
        sender: Wallet,
        memo: Optional[str] = None,
        fee: Optional[TxFee] = None,
        timeout_height: Optional[int] = None,
    ) -> SubmittedTx:
        """Delegate tokens.

        :param validator: validator address
        :param amount: amount
        :param sender: sender
        :param memo: memo, defaults to None
        :param fee: transaction fee, defaults to None
        :param timeout_height: timeout height, defaults to None
        :return: prepare and broadcast the transaction and transaction details
        """
        tx = Transaction()
        tx.add_message(
            create_delegate_msg(
                sender.address(),
                validator,
                amount,
                self.network_config.staking_denomination,
            )
        )

        return prepare_and_broadcast_basic_transaction(
            self,
            tx,
            sender,
            fee=fee,
            memo=memo,
            timeout_height=timeout_height,
        )

    def redelegate_tokens(
        self,
        current_validator: Address,
        next_validator: Address,
        amount: int,
        sender: Wallet,
        memo: Optional[str] = None,
        fee: Optional[TxFee] = None,
        timeout_height: Optional[int] = None,
    ) -> SubmittedTx:
        """Redelegate tokens.

        :param current_validator: current validator address
        :param next_validator: next validator address
        :param amount: amount
        :param sender: sender
        :param memo: memo, defaults to None
        :param fee: transaction fee, defaults to None
        :param timeout_height: timeout height, defaults to None
        :return: prepare and broadcast the transaction and transaction details
        """
        tx = Transaction()
        tx.add_message(
            create_redelegate_msg(
                sender.address(),
                current_validator,
                next_validator,
                amount,
                self.network_config.staking_denomination,
            )
        )

        return prepare_and_broadcast_basic_transaction(
            self,
            tx,
            sender,
            fee=fee,
            memo=memo,
            timeout_height=timeout_height,
        )

    def undelegate_tokens(
        self,
        validator: Address,
        amount: int,
        sender: Wallet,
        memo: Optional[str] = None,
        fee: Optional[TxFee] = None,
        timeout_height: Optional[int] = None,
    ) -> SubmittedTx:
        """Undelegate tokens.

        :param validator: validator
        :param amount: amount
        :param sender: sender
        :param memo: memo, defaults to None
        :param fee: transaction fee, defaults to None
        :param timeout_height: timeout height, defaults to None
        :return: prepare and broadcast the transaction and transaction details
        """
        tx = Transaction()
        tx.add_message(
            create_undelegate_msg(
                sender.address(),
                validator,
                amount,
                self.network_config.staking_denomination,
            )
        )

        return prepare_and_broadcast_basic_transaction(
            self,
            tx,
            sender,
            fee=fee,
            memo=memo,
            timeout_height=timeout_height,
        )

    def claim_rewards(
        self,
        validator: Address,
        sender: Wallet,
        memo: Optional[str] = None,
        fee: Optional[TxFee] = None,
        timeout_height: Optional[int] = None,
    ) -> SubmittedTx:
        """claim rewards.

        :param validator: validator
        :param sender: sender
        :param memo: memo, defaults to None
        :param fee: transaction fee, defaults to None
        :param timeout_height: timeout height, defaults to None
        :return: prepare and broadcast the transaction and transaction details
        """
        tx = Transaction()
        tx.add_message(create_withdraw_delegator_reward(sender.address(), validator))

        return prepare_and_broadcast_basic_transaction(
            self,
            tx,
            sender,
            fee=fee,
            memo=memo,
            timeout_height=timeout_height,
        )

    def estimate_gas_for_tx(self, tx: Transaction) -> int:
        """Estimate gas for transaction.

        :param tx: transaction
        :return: Estimated gas for transaction
        """
        return self._gas_strategy.estimate_gas(tx)

    # NOTE(pb): We should come up with a mechanism how this method (or a new one) can return also `Coin`, resp. `Coins`.
    def estimate_fee_from_gas(self, gas_limit: int) -> str:
        """Estimate fee from gas.

        :param gas_limit: gas limit
        :return: Estimated fee for transaction
        """
        fee = math.ceil(gas_limit * self.network_config.fee_minimum_gas_price)
        return f"{fee}{self.network_config.fee_denomination}"

    # NOTE(pb): We should come up with a mechanism how this method (or a new one) can return also `Coin`, resp. `Coins`.
    def estimate_gas_and_fee_for_tx(self, tx: Transaction) -> Tuple[int, str]:
        """Estimate gas and fee for transaction.

        :param tx: transaction
        :return: estimate gas, fee for transaction
        """
        gas_estimate = self.estimate_gas_for_tx(tx)
        fee = self.estimate_fee_from_gas(gas_estimate)
        return gas_estimate, fee

    def wait_for_query_tx(
        self,
        tx_hash: str,
        timeout: Optional[timedelta] = None,
        poll_period: Optional[timedelta] = None,
    ) -> TxResponse:
        """Wait for query transaction.

        :param tx_hash: transaction hash
        :param timeout: timeout, defaults to None
        :param poll_period: poll_period, defaults to None

        :raises QueryTimeoutError: timeout

        :return: transaction response
        """
        timeout = (
            ensure_timedelta(timeout)
            if timeout
            else timedelta(seconds=self._query_timeout_secs)
        )
        poll_period = (
            ensure_timedelta(poll_period)
            if poll_period
            else timedelta(seconds=self._query_interval_secs)
        )

        start = datetime.now()
        while True:
            try:
                return self.query_tx(tx_hash)
            except NotFoundError:
                pass

            delta = datetime.now() - start
            if delta >= timeout:
                raise QueryTimeoutError()

            time.sleep(poll_period.total_seconds())

    def query_tx(self, tx_hash: str) -> TxResponse:
        """query transaction.

        :param tx_hash: transaction hash
        :raises NotFoundError: Tx details not found
        :raises grpc.RpcError: RPC connection issue
        :return: query response
        """
        req = GetTxRequest(hash=tx_hash)
        try:
            resp = self.txs.GetTx(req)
        except grpc.RpcError as e:
            details = e.details()
            if "not found" in details:
                raise NotFoundError() from e
            raise
        except RuntimeError as e:
            details = str(e)
            if "tx" in details and "not found" in details:
                raise NotFoundError() from e
            raise

        return self._parse_tx_response(resp.tx_response)

    @staticmethod
    def _parse_tx_response(tx_response: Any) -> TxResponse:
        # parse the transaction logs
        logs = []
        for log_data in tx_response.logs:
            events = {}
            for event in log_data.events:
                events[event.type] = {a.key: a.value for a in event.attributes}
            logs.append(
                MessageLog(
                    index=int(log_data.msg_index), log=log_data.msg_index, events=events
                )
            )

        # parse the transaction events
        events = {}
        for event in tx_response.events:
            event_data = events.get(event.type, {})
            for attribute in event.attributes:
                event_data[attribute.key.decode()] = attribute.value.decode()
            events[event.type] = event_data

        timestamp = None
        if tx_response.timestamp:
            timestamp = isoparse(tx_response.timestamp)

        return TxResponse(
            hash=str(tx_response.txhash),
            height=int(tx_response.height),
            code=int(tx_response.code),
            gas_wanted=int(tx_response.gas_wanted),
            gas_used=int(tx_response.gas_used),
            raw_log=str(tx_response.raw_log),
            logs=logs,
            events=events,
            timestamp=timestamp,
        )

    def simulate_tx(self, tx: Transaction) -> int:
        """simulate transaction.

        :param tx: transaction
        :raises RuntimeError: Unable to simulate non final transaction
        :return: gas used in transaction
        """
        if tx.state != TxState.Final:
            raise RuntimeError("Unable to simulate non final transaction")

        req = SimulateRequest(tx=tx.tx)
        resp = self.txs.Simulate(req)

        return int(resp.gas_info.gas_used)

    def broadcast_tx(self, tx: Transaction) -> SubmittedTx:
        """Broadcast transaction.

        :param tx: transaction
        :return: Submitted transaction
        """
        # create the broadcast request
        broadcast_req = BroadcastTxRequest(
            tx_bytes=tx.tx.SerializeToString(), mode=BroadcastMode.BROADCAST_MODE_SYNC
        )

        # broadcast the transaction
        resp = self.txs.BroadcastTx(broadcast_req)
        tx_digest = resp.tx_response.txhash

        # check that the response is successful
        initial_tx_response = self._parse_tx_response(resp.tx_response)
        initial_tx_response.ensure_successful()

        return SubmittedTx(self, tx_digest)

    def query_latest_block(self) -> Block:
        """Query the latest block.

        :return: latest block
        """
        req = GetLatestBlockRequest()
        resp = self.tendermint.GetLatestBlock(req)
        return Block.from_proto(resp.block)

    def query_block(self, height: int) -> Block:
        """Query the block.

        :param height: block height
        :return: block
        """
        req = GetBlockByHeightRequest(height=height)
        resp = self.tendermint.GetBlockByHeight(req)
        return Block.from_proto(resp.block)

    def query_height(self) -> int:
        """Query the latest block height.

        :return: latest block height
        """
        return self.query_latest_block().height

    def query_chain_id(self) -> str:
        """Query the chain id.

        :return: chain id
        """
        return self.query_latest_block().chain_id
