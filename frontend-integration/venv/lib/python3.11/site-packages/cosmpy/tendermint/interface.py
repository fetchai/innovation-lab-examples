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
"""Interface for the Cosmos Base Tendermint functionality of CosmosSDK."""

from abc import ABC, abstractmethod

from cosmpy.protos.cosmos.base.tendermint.v1beta1.query_pb2 import (
    GetBlockByHeightRequest,
    GetBlockByHeightResponse,
    GetLatestBlockRequest,
    GetLatestBlockResponse,
    GetLatestValidatorSetRequest,
    GetLatestValidatorSetResponse,
    GetNodeInfoRequest,
    GetNodeInfoResponse,
    GetSyncingRequest,
    GetSyncingResponse,
    GetValidatorSetByHeightRequest,
    GetValidatorSetByHeightResponse,
)


class CosmosBaseTendermint(ABC):
    """Cosmos Base Tendermint abstract class."""

    @abstractmethod
    def GetNodeInfo(self, request: GetNodeInfoRequest) -> GetNodeInfoResponse:
        """
        GetNodeInfo queries the current node info.

        :param request: GetNodeInfoRequest
        :return: GetNodeInfoResponse
        """

    @abstractmethod
    def GetSyncing(self, request: GetSyncingRequest) -> GetSyncingResponse:
        """
        GetSyncing queries node syncing.

        :param request: GetSyncingRequest
        :return: GetSyncingResponse
        """

    @abstractmethod
    def GetLatestBlock(self, request: GetLatestBlockRequest) -> GetLatestBlockResponse:
        """
        GetLatestBlock returns the latest block.

        :param request: GetLatestBlockRequest
        :return: GetLatestBlockResponse
        """

    @abstractmethod
    def GetBlockByHeight(
        self, request: GetBlockByHeightRequest
    ) -> GetBlockByHeightResponse:
        """
        GetBlockByHeight queries block for given height.

        :param request: GetBlockByHeightRequest
        :return: GetBlockByHeightResponse
        """

    @abstractmethod
    def GetLatestValidatorSet(
        self, request: GetLatestValidatorSetRequest
    ) -> GetLatestValidatorSetResponse:
        """
        GetLatestValidatorSet queries latest validator-set.

        :param request: GetLatestValidatorSetRequest
        :return: GetLatestValidatorSetResponse
        """

    @abstractmethod
    def GetValidatorSetByHeight(
        self, request: GetValidatorSetByHeightRequest
    ) -> GetValidatorSetByHeightResponse:
        """
        GetValidatorSetByHeight queries validator-set at a given height.

        :param request: GetValidatorSetByHeightRequest
        :return: GetValidatorSetByHeightResponse
        """
