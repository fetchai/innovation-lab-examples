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

"""Transaction."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Union

from google.protobuf.any_pb2 import Any as ProtoAny

from cosmpy.aerial.coins import Coins, CoinsParamType
from cosmpy.crypto.address import Address
from cosmpy.crypto.interface import Signer
from cosmpy.crypto.keypairs import PublicKey
from cosmpy.protos.cosmos.crypto.secp256k1.keys_pb2 import PubKey as ProtoPubKey
from cosmpy.protos.cosmos.tx.signing.v1beta1.signing_pb2 import SignMode
from cosmpy.protos.cosmos.tx.v1beta1.tx_pb2 import (
    AuthInfo,
    Fee,
    ModeInfo,
    SignDoc,
    SignerInfo,
    Tx,
    TxBody,
)


@dataclass
class TxFee:
    """Cosmos SDK TxFee abstraction.

    Example::
    from cosmpy.aerial.tx import TxFee
    from cosmpy.aerial.coins import Coin, Coins

    fee = TxFee()
    fee = TxFee(amount="1000afet")
    fee = TxFee(amount=Coin(1000, "afet"))
    fee = TxFee(amount="100afet,10uatom")
    fee = TxFee(amount=[Coin(100, "afet"), Coin(10, "uatom")])
    """

    _amount: Optional[Coins] = field(init=False, default=None)
    gas_limit: Optional[int] = None
    granter: Optional[Address] = None
    payer: Optional[Address] = None

    def __init__(
        self,
        amount: Optional[CoinsParamType] = None,
        gas_limit: Optional[int] = None,
        granter: Optional[Address] = None,
        payer: Optional[Address] = None,
    ):
        """Initialize a TxFee object.

        :param amount: The transaction fee amount, as a Coin, list of Coins, or string (e.g., "100uatom").
        :param gas_limit: Optional gas limit for the transaction.
        :param granter: Optional address of the fee granter.
        :param payer: Optional address of the fee payer.
        """
        self.amount = amount  # type: ignore
        self.gas_limit = gas_limit
        self.granter = granter
        self.payer = payer

    @property
    def amount(self) -> Optional[Coins]:
        """Set the transaction fee amount.

        Accepts a string, Coin, or list of Coins and converts to a canonical list of Coin objects.

        :return: amount as Optional[List[Coin]]
        """
        return self._amount

    @amount.setter
    def amount(self, value: Optional[CoinsParamType]):
        """Set amount.

        Ensures conversion to expected resulting type Optional[Coins]
        :param value: The amount represented as one of the following types: str, Coins, List[Coin], List[CoinProto],
                      Coin or CoinProto.
        """
        if value is None:
            self._amount = None
        else:
            self._amount = Coins(value)

    def to_proto(self) -> Fee:
        """Return protobuf representation of TxFee.

        :raises RuntimeError: Gas limit must be set
        :return: Fee
        """
        if self.gas_limit is None:
            raise RuntimeError("Gas limit must be set")

        return Fee(
            amount=self.amount.to_proto() if self.amount else [],  # type: ignore
            gas_limit=self.gas_limit,
            granter=str(self.granter) if self.granter else None,
            payer=str(self.payer) if self.payer else None,
        )


class TxState(Enum):
    """Transaction state.

    :param Enum: Draft, Sealed, Final
    """

    Draft = 0
    Sealed = 1
    Final = 2


def _is_iterable(value) -> bool:
    try:
        iter(value)
        return True
    except TypeError:
        return False


def _wrap_in_proto_any(values: List[Any]) -> List[ProtoAny]:
    any_values = []
    for value in values:
        proto_any = ProtoAny()
        proto_any.Pack(value, type_url_prefix="/")  # type: ignore
        any_values.append(proto_any)
    return any_values


def _create_proto_public_key(public_key: PublicKey) -> ProtoAny:
    proto_public_key = ProtoAny()
    proto_public_key.Pack(
        ProtoPubKey(
            key=public_key.public_key_bytes,
        ),
        type_url_prefix="/",
    )
    return proto_public_key


class SigningMode(Enum):
    """Signing mode.

    :param Enum: Direct
    """

    Direct = 1


@dataclass
class SigningCfg:
    """Transaction signing configuration."""

    mode: SigningMode
    sequence_num: int
    public_key: PublicKey

    @staticmethod
    def direct(public_key: PublicKey, sequence_num: int) -> "SigningCfg":
        """Transaction signing configuration using direct mode.

        :param public_key: public key
        :param sequence_num: sequence number
        :return: Transaction signing configuration
        """
        return SigningCfg(
            mode=SigningMode.Direct,
            sequence_num=sequence_num,
            public_key=public_key,
        )


class Transaction:
    """Transaction."""

    def __init__(self):
        """Init the Transactions with transaction message, state, fee and body."""
        self._msgs: List[Any] = []
        self._state: TxState = TxState.Draft
        self._tx_body: Optional[TxBody] = None
        self._tx = None
        self._fee = None

    @property  # noqa
    def state(self) -> TxState:
        """Get the transaction state.

        :return: current state of the transaction
        """
        return self._state

    @property  # noqa
    def msgs(self):
        """Get the transaction messages.

        :return: transaction messages
        """
        return self._msgs

    @property
    def fee(self) -> Optional[Fee]:
        """Get the transaction fee.

        :return: transaction fee
        """
        return self._fee

    @property
    def tx(self):
        """Initialize.

        :raises RuntimeError: If the transaction has not been completed.
        :return: transaction
        """
        if self._state != TxState.Final:
            raise RuntimeError("The transaction has not been completed")
        return self._tx

    def add_message(self, msg: Any) -> "Transaction":
        """Initialize.

        :param msg: transaction message (memo)
        :raises RuntimeError: If the transaction is not in the draft state.
        :return: transaction with message added
        """
        if self._state != TxState.Draft:
            raise RuntimeError(
                "The transaction is not in the draft state. No further messages may be appended"
            )
        self._msgs.append(msg)
        return self

    def seal(
        self,
        signing_cfgs: Union[SigningCfg, List[SigningCfg]],
        fee: TxFee,
        memo: Optional[str] = None,
        timeout_height: Optional[int] = None,
    ) -> "Transaction":
        """Seal the transaction.

        :param signing_cfgs: signing configs
        :param fee: transaction fee class
        :param memo: transaction memo, defaults to None
        :param timeout_height: timeout height, defaults to None
        :return: sealed transaction.
        """
        self._state = TxState.Sealed

        input_signing_cfgs: List[SigningCfg] = (
            signing_cfgs if _is_iterable(signing_cfgs) else [signing_cfgs]  # type: ignore
        )

        signer_infos = []
        for signing_cfg in input_signing_cfgs:
            assert signing_cfg.mode == SigningMode.Direct

            signer_infos.append(
                SignerInfo(
                    public_key=_create_proto_public_key(signing_cfg.public_key),
                    mode_info=ModeInfo(
                        single=ModeInfo.Single(mode=SignMode.SIGN_MODE_DIRECT)
                    ),
                    sequence=signing_cfg.sequence_num,
                )
            )

        self._fee = fee

        auth_info = AuthInfo(
            signer_infos=signer_infos,
            fee=fee.to_proto(),
        )

        self._tx_body = TxBody()
        self._tx_body.memo = memo or ""
        if timeout_height:
            self._tx_body.timeout_height = timeout_height
        self._tx_body.messages.extend(
            _wrap_in_proto_any(self._msgs)
        )  # pylint: disable=E1101

        self._tx = Tx(body=self._tx_body, auth_info=auth_info)
        return self

    def sign(
        self,
        signer: Signer,
        chain_id: str,
        account_number: int,
        deterministic: bool = False,
    ) -> "Transaction":
        """Sign the transaction.

        :param signer: Signer
        :param chain_id: chain id
        :param account_number: account number
        :param deterministic: deterministic, defaults to False
        :raises RuntimeError: If transaction is not sealed
        :return: signed transaction
        """
        if self.state != TxState.Sealed:
            raise RuntimeError(
                "Transaction is not sealed. It must be sealed before signing is possible."
            )

        sd = SignDoc()
        sd.body_bytes = self._tx.body.SerializeToString()
        sd.auth_info_bytes = self._tx.auth_info.SerializeToString()
        sd.chain_id = chain_id
        sd.account_number = account_number

        data_for_signing = sd.SerializeToString()

        # Generating deterministic signature:
        signature = signer.sign(
            data_for_signing,
            deterministic=deterministic,
            canonicalise=True,
        )
        self._tx.signatures.extend([signature])
        return self

    def complete(self) -> "Transaction":
        """Update transaction state to Final.

        :return: transaction with  updated state
        """
        self._state = TxState.Final
        return self
