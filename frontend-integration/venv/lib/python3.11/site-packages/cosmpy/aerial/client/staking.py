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

"""Staking functionality."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import List

from cosmpy.crypto.address import Address
from cosmpy.protos.cosmos.base.v1beta1.coin_pb2 import Coin
from cosmpy.protos.cosmos.staking.v1beta1.tx_pb2 import (
    MsgBeginRedelegate,
    MsgDelegate,
    MsgUndelegate,
)


class ValidatorStatus(Enum):
    """Validator status."""

    UNSPECIFIED = "BOND_STATUS_UNSPECIFIED"
    BONDED = "BOND_STATUS_BONDED"
    UNBONDING = "BOND_STATUS_UNBONDING"
    UNBONDED = "BOND_STATUS_UNBONDED"

    @classmethod
    def from_proto(cls, value: int) -> "ValidatorStatus":
        """Get the validator status from proto.

        :param value: value
        :raises RuntimeError: Unable to decode validator status
        :return: Validator status
        """
        if value == 0:
            return cls.UNSPECIFIED
        if value == 1:
            return cls.UNBONDED
        if value == 2:
            return cls.UNBONDING
        if value == 3:
            return cls.BONDED
        raise RuntimeError(f"Unable to decode validator status: {value}")


@dataclass
class StakingPosition:
    """Staking positions."""

    validator: Address
    amount: int
    reward: int
    reward_dec: Decimal


@dataclass
class UnbondingPositions:
    """Unbonding positions."""

    validator: Address
    amount: int


@dataclass
class Validator:
    """Validator."""

    address: Address  # the operators address
    tokens: int  # The total amount of tokens for the validator
    moniker: str
    status: ValidatorStatus


@dataclass
class StakingSummary:
    """Get the staking summary."""

    current_positions: List[StakingPosition]
    unbonding_positions: List[UnbondingPositions]

    @property
    def total_staked(self) -> int:
        """Get the total staked amount."""
        return sum(map(lambda p: p.amount, self.current_positions))

    @property
    def total_rewards(self) -> int:
        """Get the total rewards."""
        return sum(map(lambda p: p.reward, self.current_positions))

    @property
    def total_unbonding(self) -> int:
        """total unbonding."""
        return sum(map(lambda p: p.amount, self.unbonding_positions))


def create_delegate_msg(
    delegator: Address, validator: Address, amount: int, denom: str
) -> MsgDelegate:
    """Create delegate message.

    :param delegator: delegator
    :param validator: validator
    :param amount: amount
    :param denom: denom
    :return: Delegate message
    """
    return MsgDelegate(
        delegator_address=str(delegator),
        validator_address=str(validator),
        amount=Coin(
            amount=str(amount),
            denom=denom,
        ),
    )


def create_redelegate_msg(
    delegator_address: Address,
    validator_src_address: Address,
    validator_dst_address: Address,
    amount: int,
    denom: str,
) -> MsgBeginRedelegate:
    """Create redelegate message.

    :param delegator_address: delegator address
    :param validator_src_address: source validation address
    :param validator_dst_address: destination validation address
    :param amount: amount
    :param denom: denom
    :return: Redelegate message
    """
    return MsgBeginRedelegate(
        delegator_address=str(delegator_address),
        validator_src_address=str(validator_src_address),
        validator_dst_address=str(validator_dst_address),
        amount=Coin(
            amount=str(amount),
            denom=denom,
        ),
    )


def create_undelegate_msg(
    delegator_address: Address, validator_address: Address, amount: int, denom: str
) -> MsgUndelegate:
    """Create undelegate message.

    :param delegator_address: delegator address
    :param validator_address: validator address
    :param amount: amount
    :param denom: denom
    :return: Undelegate message
    """
    return MsgUndelegate(
        delegator_address=str(delegator_address),
        validator_address=str(validator_address),
        amount=Coin(
            amount=str(amount),
            denom=denom,
        ),
    )
