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

"""Bank send message."""

from cosmpy.crypto.address import Address
from cosmpy.protos.cosmos.bank.v1beta1.tx_pb2 import MsgSend
from cosmpy.protos.cosmos.base.v1beta1.coin_pb2 import Coin


def create_bank_send_msg(
    from_address: Address, to_address: Address, amount: int, denom: str
) -> MsgSend:
    """Create bank send message.

    :param from_address: from address
    :param to_address: to address
    :param amount: amount
    :param denom: denom
    :return: bank send message
    """
    msg = MsgSend(
        from_address=str(from_address),
        to_address=str(to_address),
        amount=[Coin(amount=str(amount), denom=denom)],
    )

    return msg
