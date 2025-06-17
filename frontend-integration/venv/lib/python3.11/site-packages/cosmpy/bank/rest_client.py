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

"""Implementation of Bank interface using REST."""

from google.protobuf.json_format import Parse

from cosmpy.bank.interface import Bank
from cosmpy.common.rest_client import RestClient
from cosmpy.protos.cosmos.bank.v1beta1.query_pb2 import (
    QueryAllBalancesRequest,
    QueryAllBalancesResponse,
    QueryBalanceRequest,
    QueryBalanceResponse,
    QueryDenomMetadataRequest,
    QueryDenomMetadataResponse,
    QueryDenomsMetadataRequest,
    QueryDenomsMetadataResponse,
    QueryParamsRequest,
    QueryParamsResponse,
    QuerySupplyOfRequest,
    QuerySupplyOfResponse,
    QueryTotalSupplyRequest,
    QueryTotalSupplyResponse,
)


class BankRestClient(Bank):
    """Bank REST client."""

    API_URL = "/cosmos/bank/v1beta1"

    def __init__(self, rest_api: RestClient):
        """
        Create bank rest client.

        :param rest_api: RestClient api
        """
        self._rest_api = rest_api

    def Balance(self, request: QueryBalanceRequest) -> QueryBalanceResponse:
        """
        Query balance of selected denomination from specific account.

        :param request: QueryBalanceRequest with address and denomination

        :return: QueryBalanceResponse
        """
        response = self._rest_api.get(
            f"{self.API_URL}/balances/{request.address}/by_denom?denom={request.denom}",
            request,
            ["address", "denom"],
        )
        return Parse(response, QueryBalanceResponse())

    def AllBalances(self, request: QueryAllBalancesRequest) -> QueryAllBalancesResponse:
        """
        Query balance of all denominations from specific account.

        :param request: QueryAllBalancesRequest with account address

        :return: QueryAllBalancesResponse
        """
        response = self._rest_api.get(
            f"{self.API_URL}/balances/{request.address}", request, ["address"]
        )
        return Parse(response, QueryAllBalancesResponse())

    def TotalSupply(self, request: QueryTotalSupplyRequest) -> QueryTotalSupplyResponse:
        """
        Query total supply of all denominations.

        :param request: QueryTotalSupplyRequest

        :return: QueryTotalSupplyResponse
        """
        response = self._rest_api.get(f"{self.API_URL}/supply", request)
        return Parse(response, QueryTotalSupplyResponse())

    def SupplyOf(self, request: QuerySupplyOfRequest) -> QuerySupplyOfResponse:
        """
        Query total supply of specific denomination.

        :param request: QuerySupplyOfRequest with denomination

        :return: QuerySupplyOfResponse
        """
        response = self._rest_api.get(f"{self.API_URL}/supply/{request.denom}")
        return Parse(response, QuerySupplyOfResponse())

    def Params(self, request: QueryParamsRequest) -> QueryParamsResponse:
        """
        Query the parameters of bank module.

        :param request: QueryParamsRequest

        :return: QueryParamsResponse
        """
        response = self._rest_api.get(f"{self.API_URL}/params")
        return Parse(response, QueryParamsResponse())

    def DenomMetadata(
        self, request: QueryDenomMetadataRequest
    ) -> QueryDenomMetadataResponse:
        """
        Query the client metadata for all registered coin denominations.

        :param request: QueryDenomMetadataRequest with denomination

        :return: QueryDenomMetadataResponse
        """
        response = self._rest_api.get(f"{self.API_URL}/denoms_metadata/{request.denom}")
        return Parse(response, QueryDenomMetadataResponse())

    def DenomsMetadata(
        self, request: QueryDenomsMetadataRequest
    ) -> QueryDenomsMetadataResponse:
        """
        Query the client metadata of a given coin denomination.

        :param request: QueryDenomsMetadataRequest

        :return: QueryDenomsMetadataResponse
        """
        response = self._rest_api.get(f"{self.API_URL}/denoms_metadata", request)
        return Parse(response, QueryDenomsMetadataResponse())
