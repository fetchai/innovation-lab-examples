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
"""Interface for the Slashing functionality of CosmosSDK."""

from abc import ABC, abstractmethod

from cosmpy.protos.cosmos.slashing.v1beta1.query_pb2 import (
    QueryParamsResponse,
    QuerySigningInfoRequest,
    QuerySigningInfoResponse,
    QuerySigningInfosRequest,
    QuerySigningInfosResponse,
)


class Slashing(ABC):
    """Slashing abstract class."""

    @abstractmethod
    def Params(self) -> QueryParamsResponse:
        """
        Params queries the parameters of slashing module.

        :return: QueryParamsResponse
        """

    @abstractmethod
    def SigningInfo(self, request: QuerySigningInfoRequest) -> QuerySigningInfoResponse:
        """
        SigningInfo queries the signing info of given cons address.

        :param request: QuerySigningInfoRequest

        :return: QuerySigningInfoResponse
        """

    @abstractmethod
    def SigningInfos(
        self, request: QuerySigningInfosRequest
    ) -> QuerySigningInfosResponse:
        """
        SigningInfos queries signing info of all validators.

        :param request: QuerySigningInfosRequest

        :return: QuerySigningInfosResponse
        """
