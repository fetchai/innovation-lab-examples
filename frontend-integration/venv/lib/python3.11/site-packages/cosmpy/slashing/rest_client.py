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
"""Implementation of Slashing interface using REST."""

from google.protobuf.json_format import Parse

from cosmpy.common.rest_client import RestClient
from cosmpy.protos.cosmos.slashing.v1beta1.query_pb2 import (
    QueryParamsResponse,
    QuerySigningInfoRequest,
    QuerySigningInfoResponse,
    QuerySigningInfosRequest,
    QuerySigningInfosResponse,
)
from cosmpy.slashing.interface import Slashing


class SlashingRestClient(Slashing):
    """Slashing REST client."""

    API_URL = "/cosmos/slashing/v1beta1"

    def __init__(self, rest_api: RestClient) -> None:
        """
        Initialize.

        :param rest_api: RestClient api
        """
        self._rest_api = rest_api

    def Params(self) -> QueryParamsResponse:
        """
        Params queries the parameters of slashing module.

        :return: QueryParamsResponse
        """
        json_response = self._rest_api.get(
            f"{self.API_URL}/params",
        )
        return Parse(json_response, QueryParamsResponse())

    def SigningInfo(self, request: QuerySigningInfoRequest) -> QuerySigningInfoResponse:
        """
        SigningInfo queries the signing info of given cons address.

        :param request: QuerySigningInfoRequest

        :return: QuerySigningInfoResponse
        """
        json_response = self._rest_api.get(
            f"{self.API_URL}/signing_infos/{request.cons_address}",
        )
        return Parse(json_response, QuerySigningInfoResponse())

    def SigningInfos(
        self, request: QuerySigningInfosRequest
    ) -> QuerySigningInfosResponse:
        """
        SigningInfos queries signing info of all validators.

        :param request: QuerySigningInfosRequest

        :return: QuerySigningInfosResponse
        """
        json_response = self._rest_api.get(f"{self.API_URL}/signing_infos", request)
        return Parse(json_response, QuerySigningInfosResponse())
