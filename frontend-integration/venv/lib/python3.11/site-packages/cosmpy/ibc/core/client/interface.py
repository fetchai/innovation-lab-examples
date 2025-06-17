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
"""Interface for the IBC Core Client functionality of CosmosSDK."""

from abc import ABC, abstractmethod

from cosmpy.protos.ibc.core.client.v1.query_pb2 import (
    QueryClientParamsRequest,
    QueryClientParamsResponse,
    QueryClientStateRequest,
    QueryClientStateResponse,
    QueryClientStatesRequest,
    QueryClientStatesResponse,
    QueryConsensusStateRequest,
    QueryConsensusStateResponse,
    QueryConsensusStatesRequest,
    QueryConsensusStatesResponse,
)


class IBCCoreClient(ABC):
    """IBC Core Client abstract class."""

    @abstractmethod
    def ClientState(self, request: QueryClientStateRequest) -> QueryClientStateResponse:
        """
        ClientState queries an IBC light client.

        :param request: QueryClientStateRequest
        :return: QueryClientStateResponse
        """

    @abstractmethod
    def ClientStates(
        self, request: QueryClientStatesRequest
    ) -> QueryClientStatesResponse:
        """
        ClientStates queries all the IBC light clients of a chain.

        :param request: QueryClientStatesRequest
        :return: QueryClientStatesResponse
        """

    @abstractmethod
    def ConsensusState(
        self, request: QueryConsensusStateRequest
    ) -> QueryConsensusStateResponse:
        """
        ConsensusState queries a consensus state associated with a client state at a given height.

        :param request: QueryConsensusStateRequest
        :return: QueryConsensusStateResponse
        """

    @abstractmethod
    def ConsensusStates(
        self, request: QueryConsensusStatesRequest
    ) -> QueryConsensusStatesResponse:
        """
        ConsensusStates queries all the consensus states associated with a given client.

        :param request: QueryConsensusStatesRequest
        :return: QueryConsensusStatesResponse
        """

    @abstractmethod
    def ClientParams(
        self, request: QueryClientParamsRequest
    ) -> QueryClientParamsResponse:
        """
        ClientParams queries all parameters of the IBC client.

        :param request: QueryClientParamsRequest
        :return: QueryClientParamsResponse
        """
