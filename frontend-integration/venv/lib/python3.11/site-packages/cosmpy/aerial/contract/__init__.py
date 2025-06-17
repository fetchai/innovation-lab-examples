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

"""cosmwasm contract functionality."""

import json
import os
from collections import UserString
from datetime import datetime
from typing import Any, Dict, Optional

from jsonschema import validate

from cosmpy.aerial.client import (
    LedgerClient,
    TxFee,
    prepare_and_broadcast_basic_transaction,
)
from cosmpy.aerial.contract.cosmwasm import (
    create_cosmwasm_clear_admin_msg,
    create_cosmwasm_execute_msg,
    create_cosmwasm_instantiate_msg,
    create_cosmwasm_migrate_msg,
    create_cosmwasm_store_code_msg,
    create_cosmwasm_update_admin_msg,
)
from cosmpy.aerial.tx import Transaction
from cosmpy.aerial.tx_helpers import SubmittedTx
from cosmpy.aerial.wallet import Wallet
from cosmpy.common.utils import json_encode
from cosmpy.crypto.address import Address
from cosmpy.crypto.hashfuncs import sha256
from cosmpy.protos.cosmos.base.query.v1beta1.pagination_pb2 import PageRequest
from cosmpy.protos.cosmwasm.wasm.v1.query_pb2 import (
    QueryCodesRequest,
    QuerySmartContractStateRequest,
)


def _compute_digest(path: str) -> bytes:
    with open(path, "rb") as input_file:
        return sha256(input_file.read())


def _generate_label(digest: bytes) -> str:
    now = datetime.utcnow()
    return f"{digest.hex()[:14]}-{now.strftime('%Y%m%d%H%M%S')}"


def _load_contract_schema(schema_path: str) -> Optional[Dict[Any, Any]]:
    if not os.path.isdir(schema_path):
        return None

    schema = {}
    for filename in os.listdir(schema_path):
        if filename.endswith(".json"):
            msg_name = os.path.splitext(os.path.basename(filename))[0]
            full_path = os.path.join(schema_path, filename)
            with open(full_path, "r", encoding="utf-8") as msg_schema_file:
                msg_schema = json.load(msg_schema_file)
            schema[msg_name] = msg_schema
    return schema


class LedgerContract(UserString):
    """Ledger contract."""

    def __init__(
        self,
        path: Optional[str],
        client: LedgerClient,
        address: Optional[Address] = None,
        digest: Optional[bytes] = None,
        schema_path: Optional[str] = None,
        code_id: Optional[int] = None,
    ):
        """Initialize the Ledger contract.

        :param path: Path
        :param client: Ledger client
        :param address: address, defaults to None
        :param digest: digest, defaults to None
        :param schema_path: path to contract schema, defaults to None
        :param code_id: optional int. code id of the contract stored
        """
        # pylint: disable=super-init-not-called
        self._path = path
        self._client = client
        self._address = address

        # load contract schema if path is provided
        self._load_schema(schema_path)

        # select the digest either by computing it from the provided contract or by the value specified by
        # the user
        self._digest: Optional[bytes] = digest
        if path is not None:
            self._digest = _compute_digest(str(self._path))

        # attempt to look up the code id from the network by digest
        if not code_id and self._digest is not None:
            self._code_id = self._find_contract_id_by_digest(self._digest)
        else:
            self._code_id = code_id

    @property
    def path(self) -> Optional[str]:
        """Get contract path.

        :return: contract path
        """
        return self._path

    @property
    def digest(self) -> Optional[bytes]:
        """Get the contract digest.

        :return: contract digest
        """
        return self._digest

    @property
    def code_id(self) -> Optional[int]:
        """Get the code id.

        :return: code id
        """
        return self._code_id

    @property
    def address(self) -> Optional[Address]:
        """Get the contract address.

        :return: contract address
        """
        return self._address

    def store(
        self,
        sender: Wallet,
        fee: Optional[TxFee] = None,
        memo: Optional[str] = None,
        timeout_height: Optional[int] = None,
    ) -> int:
        """Store the contract.

        :param sender: sender wallet address
        :param fee: transaction fee, defaults to None
        :param memo: transaction memo, defaults to None
        :param timeout_height: timeout height, defaults to None
        :raises RuntimeError: Runtime error
        :return: code id
        """
        if self._path is None:
            raise RuntimeError("Unable to upload code, no contract provided")

        # build up the store transaction
        tx = Transaction()
        tx.add_message(create_cosmwasm_store_code_msg(self._path, sender.address()))

        submitted_tx = prepare_and_broadcast_basic_transaction(
            self._client,
            tx,
            sender,
            fee=fee,
            memo=memo,
            timeout_height=timeout_height,
        ).wait_to_complete()

        # extract the code id
        self._code_id = submitted_tx.contract_code_id
        if self._code_id is None:
            raise RuntimeError("Unable to extract contract code id")

        return self._code_id

    def instantiate(
        self,
        args: Any,
        sender: Wallet,
        label: Optional[str] = None,
        fee: Optional[TxFee] = None,
        admin_address: Optional[Address] = None,
        funds: Optional[str] = None,
        timeout_height: Optional[int] = None,
    ) -> Address:
        """Instantiate the contract.

        :param args: args
        :param sender: sender wallet address
        :param label: label, defaults to None
        :param fee: transaction fee, defaults to None
        :param admin_address: admin address, defaults to None
        :param funds: funds, defaults to None
        :param timeout_height: timeout height, defaults to None
        :raises RuntimeError: Unable to extract contract code id

        :return: contract address
        """
        assert self._code_id, RuntimeError("Code id was not set.")

        if self._instantiate_schema is not None:
            validate(args, self._instantiate_schema)

        if label is None:
            if self._digest:
                label = _generate_label(bytes(self._digest))
            elif self._code_id:
                label = _generate_label(bytes(f"{self._code_id}", encoding="utf-8"))
            else:
                raise RuntimeError(
                    "Failed to get label. No code_id or digest provided."
                )

        # build up the store transaction
        instatiate_msg = create_cosmwasm_instantiate_msg(
            self._code_id,
            args,
            label,
            sender.address(),
            admin_address=admin_address,
            funds=funds,
        )
        tx = Transaction()
        tx.add_message(instatiate_msg)

        submitted_tx = prepare_and_broadcast_basic_transaction(
            self._client,
            tx,
            sender,
            fee=fee,
            timeout_height=timeout_height,
        ).wait_to_complete()

        # store the contract address
        self._address = submitted_tx.contract_address
        if self._address is None:
            raise RuntimeError("Unable to extract contract code id")

        return self._address

    def upgrade(
        self,
        args: Any,
        sender: Wallet,
        new_path: str,
        fee: Optional[TxFee] = None,
        timeout_height: Optional[int] = None,
    ) -> SubmittedTx:
        """Store new contract code and migrate the current contract address.

        :param args: args
        :param sender: sender wallet address
        :param new_path: path to new contract
        :param fee: transaction fee, defaults to None
        :param timeout_height: timeout height, defaults to None

        :return: transaction details broadcast
        """
        assert self._address, RuntimeError("Address was not set.")

        if self._migrate_schema is not None:
            validate(args, self._migrate_schema)

        self._path = new_path
        new_code_id = self.store(sender, fee)

        return self.migrate(
            args,
            sender,
            new_code_id,
            fee=fee,
            timeout_height=timeout_height,
        )

    def migrate(
        self,
        args: Any,
        sender: Wallet,
        new_code_id: int,
        fee: Optional[TxFee] = None,
        timeout_height: Optional[int] = None,
    ) -> SubmittedTx:
        """Migrate the current contract address to new code id.

        :param args: args
        :param sender: sender wallet address
        :param new_code_id: Code id of the newly deployed contract
        :param fee: transaction fee, defaults to None
        :param timeout_height: timeout height, defaults to None

        :return: transaction details broadcast
        """
        assert self._address, RuntimeError("Address was not set.")

        if self._migrate_schema is not None:
            validate(args, self._migrate_schema)

        # build up the migrate transaction
        migrate_msg = create_cosmwasm_migrate_msg(
            new_code_id,
            args,
            self._address,
            sender.address(),
        )
        tx = Transaction()
        tx.add_message(migrate_msg)

        return prepare_and_broadcast_basic_transaction(
            self._client,
            tx,
            sender,
            fee=fee,
            timeout_height=timeout_height,
        ).wait_to_complete()

    def update_admin(
        self,
        sender: Wallet,
        new_admin: Optional[Address],
        fee: Optional[TxFee] = None,
        timeout_height: Optional[int] = None,
    ) -> SubmittedTx:
        """Update/clear the admin of the contract.

        :param sender: sender wallet address
        :param new_admin: New admin address, None for clear admin
        :param fee: transaction fee, defaults to None
        :param timeout_height: timeout height, defaults to None

        :return: transaction details broadcast
        """
        assert self._address, RuntimeError("Address was not set.")

        # build up the update/clear admin transaction
        if new_admin is None:
            msg = create_cosmwasm_clear_admin_msg(
                sender.address(),
                self._address,
            )
        else:
            msg = create_cosmwasm_update_admin_msg(
                sender.address(), self._address, new_admin
            )

        tx = Transaction()
        tx.add_message(msg)

        return prepare_and_broadcast_basic_transaction(
            self._client,
            tx,
            sender,
            fee=fee,
            timeout_height=timeout_height,
        ).wait_to_complete()

    def deploy(
        self,
        args: Any,
        sender: Wallet,
        label: Optional[str] = None,
        store_fee: Optional[TxFee] = None,
        instantiate_fee: Optional[TxFee] = None,
        admin_address: Optional[Address] = None,
        funds: Optional[str] = None,
        timeout_height: Optional[int] = None,
    ) -> Address:
        """Deploy the contract.

        :param args: args
        :param sender: sender address
        :param label: label, defaults to None
        :param store_fee: Store transaction fee, defaults to None
        :param instantiate_fee: instantiate Transaction fee, defaults to None
        :param admin_address: admin address, defaults to None
        :param funds: funds, defaults to None
        :param timeout_height: timeout height, defaults to None
        :return: instantiate contract details
        """
        # in the case where the contract is already deployed
        if self._address is not None and self._code_id is not None:
            return self._address

        assert self._address is None

        if self._code_id is None:
            self.store(sender, fee=store_fee)

        assert self._code_id is not None

        return self.instantiate(
            args,
            sender,
            label=label,
            fee=instantiate_fee,
            admin_address=admin_address,
            funds=funds,
            timeout_height=timeout_height,
        )

    def execute(
        self,
        args: Any,
        sender: Wallet,
        fee: Optional[TxFee] = None,
        funds: Optional[str] = None,
        timeout_height: Optional[int] = None,
    ) -> SubmittedTx:
        """execute the contract.

        :param args: args
        :param sender: sender address
        :param fee: transaction fee, defaults to None
        :param funds: funds, defaults to None
        :param timeout_height: timeout height, defaults to None
        :raises RuntimeError: Contract appears not to be deployed currently
        :return: transaction details broadcast
        """
        if self._address is None:
            raise RuntimeError("Contract appears not to be deployed currently")

        if self._execute_schema is not None:
            validate(args, self._execute_schema)

        # build up the execute transaction
        tx = Transaction()
        tx.add_message(
            create_cosmwasm_execute_msg(
                sender.address(),
                self._address,
                args,
                funds=funds,
            )
        )

        return prepare_and_broadcast_basic_transaction(
            self._client,
            tx,
            sender,
            fee=fee,
            timeout_height=timeout_height,
        )

    def query(self, args: Any) -> Any:
        """Query on contract.

        :param args: args
        :raises RuntimeError: Contract appears not to be deployed currently
        :return: query result
        """
        if self._address is None:
            raise RuntimeError("Contract appears not to be deployed currently")

        if self._query_schema is not None:
            validate(args, self._query_schema)

        req = QuerySmartContractStateRequest(
            address=str(self._address), query_data=json_encode(args).encode("UTF8")
        )
        resp = self._client.wasm.SmartContractState(req)
        return json.loads(resp.data)

    def _find_contract_id_by_digest(self, digest: bytes) -> Optional[int]:
        code_id = None

        pagination = None
        while True:
            req = QueryCodesRequest(pagination=pagination)
            resp = self._client.wasm.Codes(req)
            for code_info in resp.code_infos:
                if code_info.data_hash == digest:
                    code_id = int(code_info.code_id)
                    break

            # exit the search loop if we have successfully found our code id
            if code_id is not None:
                break

            # exit the search loop when we can't iterate any further
            if len(resp.pagination.next_key) == 0:
                break

            # proceed to the next page
            pagination = PageRequest(key=resp.pagination.next_key)

        return code_id

    def _load_schema(self, schema_path: Optional[str]):
        self._schema: Optional[Dict[str, Any]] = None
        self._instantiate_schema: Optional[Dict[str, Any]] = None
        self._query_schema: Optional[Dict[str, Any]] = None
        self._execute_schema: Optional[Dict[str, Any]] = None
        self._migrate_schema: Optional[Dict[str, Any]] = None

        if schema_path is None:
            return

        self._schema = _load_contract_schema(schema_path)
        if self._schema is None:
            return

        for msg_type, schema in self._schema.items():
            if "instantiate" in msg_type:
                self._instantiate_schema = schema
            elif "query" in msg_type:
                self._query_schema = schema
            elif "execute" in msg_type:
                self._execute_schema = schema
            elif "migrate" in msg_type:
                self._migrate_schema = schema

    @property
    def data(self):
        """Get the contract address.

        :return: contract address
        """
        return self.address

    def __json__(self):
        """Get the contract details in json.

        :return: contract details in json
        """
        return str(self)
