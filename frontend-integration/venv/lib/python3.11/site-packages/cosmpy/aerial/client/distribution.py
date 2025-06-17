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
"""Distribution."""

from cosmpy.crypto.address import Address
from cosmpy.protos.cosmos.distribution.v1beta1.tx_pb2 import MsgWithdrawDelegatorReward


def create_withdraw_delegator_reward(delegator: Address, validator: Address):
    """Create withdraw delegator reward.

    :param delegator: delegator address
    :param validator: validator address
    :return: withdraw delegator reward message
    """
    return MsgWithdrawDelegatorReward(
        delegator_address=str(delegator),
        validator_address=str(validator),
    )
