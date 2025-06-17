# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2018-2022 Fetch.AI Limited
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

"""Ledger faucet API interface."""

import time
from collections import namedtuple
from typing import Optional, Union

import requests

from cosmpy.aerial.config import NetworkConfig
from cosmpy.crypto.address import Address


CosmosFaucetStatus = namedtuple("CosmosFaucetStatus", ["tx_digest", "status"])
DEFAULT_TIMEOUT = 60.0


class FaucetApi:
    """Faucet API."""

    MAX_RETRY_ATTEMPTS = 30
    POLL_INTERVAL = 2
    FINAL_WAIT_INTERVAL = 5

    FAUCET_STATUS_PENDING = "pending"  # noqa: F841
    FAUCET_STATUS_PROCESSING = "processing"  # noqa: F841
    FAUCET_STATUS_COMPLETED = "complete"  # noqa: F841
    FAUCET_STATUS_FAILED = "failed"  # noqa: F841

    def __init__(self, net_config: NetworkConfig):
        """
        Init faucet API.

        :param net_config: Ledger network configuration.
        :raises ValueError: Network config has no faucet url set
        """
        if net_config.faucet_url is None:
            raise ValueError("Network config has no faucet url set!")  # pragma: nocover
        self._net_config = net_config

    def _claim_url(self) -> str:
        """
        Get claim url.

        :return: url string
        """
        return f"{self._net_config.faucet_url}/api/v3/claims"

    def _status_uri(self, uid: str) -> str:
        """
        Generate the status URI derived .

        :param uid: claim uid.
        :return: url string
        """
        return f"{self._claim_url()}/{uid}"

    def _try_create_faucet_claim(self, address: str) -> Optional[str]:
        """
        Create a token faucet claim request.

        :param address: the address to request funds
        :return: None on failure, otherwise the request uid
        :raises ValueError: key `uid` not found in response
        """
        uri = self._claim_url()
        response = requests.post(
            url=uri, json={"address": address}, timeout=DEFAULT_TIMEOUT
        )
        uid = None
        if response.status_code == 200:
            try:
                uid = response.json()["uuid"]
            except KeyError as error:  # pragma: nocover
                raise ValueError(
                    f"key `uid` not found in response_json={response.json()}"
                ) from error

        return uid

    def _try_check_faucet_claim(self, uid: str) -> Optional[CosmosFaucetStatus]:
        """
        Check the status of a faucet request.

        :param uid: The request uid to be checked
        :return: None on failure otherwise a CosmosFaucetStatus for the specified uid
        """
        response = requests.get(self._status_uri(uid), timeout=DEFAULT_TIMEOUT)
        if response.status_code != 200:  # pragma: nocover
            return None

        # parse the response
        data = response.json()
        tx_digest = None
        if "txStatus" in data["claim"]:
            tx_digest = data["claim"]["txStatus"]["hash"]

        return CosmosFaucetStatus(
            tx_digest=tx_digest,
            status=data["claim"]["status"],
        )

    def get_wealth(self, address: Union[Address, str]) -> None:
        """
        Get wealth from the faucet for the provided address.

        :param address: the address.
        :raises RuntimeError: Unable to create faucet claim
        :raises RuntimeError: Failed to check faucet claim status
        :raises RuntimeError: Failed to get wealth for address
        :raises ValueError: Faucet claim check timed out
        """
        address = str(address)
        uid = self._try_create_faucet_claim(address)
        if uid is None:  # pragma: nocover
            raise RuntimeError("Unable to create faucet claim")

        retry_attempts = self.MAX_RETRY_ATTEMPTS
        while retry_attempts > 0:
            retry_attempts -= 1

            # lookup status form the claim uid
            status = self._try_check_faucet_claim(uid)
            if status is None:  # pragma: nocover
                raise RuntimeError("Failed to check faucet claim status")

            # if the status is complete
            if status.status == self.FAUCET_STATUS_COMPLETED:
                break

            # if the status is failure
            if status.status not in (
                self.FAUCET_STATUS_PENDING,
                self.FAUCET_STATUS_PROCESSING,
            ):  # pragma: nocover
                raise RuntimeError(f"Failed to get wealth for {address}")

            # if the status is incomplete
            time.sleep(self.POLL_INTERVAL)
        if retry_attempts == 0:
            raise ValueError("Faucet claim check timed out!")  # pragma: nocover
        # Wait to ensure that balance is increased on chain
        time.sleep(self.FINAL_WAIT_INTERVAL)
