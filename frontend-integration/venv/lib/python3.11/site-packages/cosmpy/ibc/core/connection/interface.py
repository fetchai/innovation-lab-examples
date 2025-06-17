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
"""Interface for the IBC Core Connection functionality of CosmosSDK."""

from abc import ABC, abstractmethod

from cosmpy.protos.ibc.core.connection.v1.query_pb2 import (
    QueryClientConnectionsRequest,
    QueryClientConnectionsResponse,
    QueryConnectionClientStateRequest,
    QueryConnectionClientStateResponse,
    QueryConnectionConsensusStateRequest,
    QueryConnectionConsensusStateResponse,
    QueryConnectionRequest,
    QueryConnectionResponse,
    QueryConnectionsRequest,
    QueryConnectionsResponse,
)


class IBCCoreConnection(ABC):
    """IBC Core Connection abstract class."""

    @abstractmethod
    def Connection(self, request: QueryConnectionRequest) -> QueryConnectionResponse:
        """
        Connection queries an IBC connection end.

        :param request: QueryConnectionRequest
        :return: QueryConnectionResponse
        """  # noqa: D401

    @abstractmethod
    def Connections(self, request: QueryConnectionsRequest) -> QueryConnectionsResponse:
        """
        Connection queries all the IBC connections of a chain.

        :param request: QueryConnectionsRequest
        :return: QueryConnectionsResponse
        """  # noqa: D401

    @abstractmethod
    def ClientConnections(
        self, request: QueryClientConnectionsRequest
    ) -> QueryClientConnectionsResponse:
        """
        ClientConnection queries the connection paths associated with a client state.

        :param request: QueryClientConnectionsRequest
        :return: QueryClientConnectionsResponse
        """

    @abstractmethod
    def ConnectionClientState(
        self, request: QueryConnectionClientStateRequest
    ) -> QueryConnectionClientStateResponse:
        """
        ConnectionClientState queries the client state associated with the connection.

        :param request: QueryConnectionClientStateRequest
        :return: QueryConnectionClientStateResponse
        """

    @abstractmethod
    def ConnectionConsensusState(
        self, request: QueryConnectionConsensusStateRequest
    ) -> QueryConnectionConsensusStateResponse:
        """
        ConnectionConsensusState queries the consensus state associated with the connection.

        :param request: QueryConnectionConsensusStateRequest
        :return: QueryConnectionConsensusStateResponse
        """
