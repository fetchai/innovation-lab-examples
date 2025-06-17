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
"""Implementation of IBC Applications Transfer  interface using REST."""
from google.protobuf.json_format import Parse

from cosmpy.common.rest_client import RestClient
from cosmpy.ibc.applications.transfer.interface import (  # type: ignore
    IBCApplicationsTransfer,
)
from cosmpy.protos.ibc.applications.transfer.v1.query_pb2 import (
    QueryDenomTraceRequest,
    QueryDenomTraceResponse,
    QueryDenomTracesRequest,
    QueryDenomTracesResponse,
    QueryParamsRequest,
    QueryParamsResponse,
)


class IBCApplicationsTransferRestClient(IBCApplicationsTransfer):
    """IBC Applications Transfer REST client."""

    API_URL = "/ibc/applications/transfer/v1beta1"

    def __init__(self, rest_api: RestClient) -> None:
        """
        Initialize.

        :param rest_api: RestClient api
        """
        self._rest_api = rest_api

    def DenomTrace(self, request: QueryDenomTraceRequest) -> QueryDenomTraceResponse:
        """
        DenomTrace queries a denomination trace information.

        :param request: QueryDenomTraceRequest
        :return: QueryDenomTraceResponse
        """
        json_response = self._rest_api.get(
            f"{self.API_URL}/denom_traces/{request.hash}"
        )
        return Parse(json_response, QueryDenomTraceResponse())

    def DenomTraces(self, request: QueryDenomTracesRequest) -> QueryDenomTracesResponse:
        """
        DenomTraces queries all denomination traces.

        :param request: QueryDenomTracesRequest
        :return: QueryDenomTracesResponse
        """
        json_response = self._rest_api.get(f"{self.API_URL}/denom_traces", request)
        return Parse(json_response, QueryDenomTracesResponse())

    def Params(self, request: QueryParamsRequest) -> QueryParamsResponse:
        """
        Params queries all parameters of the ibc-transfer module.

        :param request: QueryParamsRequest
        :return: QueryParamsResponse
        """
        json_response = self._rest_api.get(f"{self.API_URL}/params")
        return Parse(json_response, QueryParamsResponse())
