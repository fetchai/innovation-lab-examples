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

"""Implementation of Staking interface using REST."""

from google.protobuf.json_format import Parse

from cosmpy.common.rest_client import RestClient
from cosmpy.protos.cosmos.staking.v1beta1.query_pb2 import (
    QueryDelegationRequest,
    QueryDelegationResponse,
    QueryDelegatorDelegationsRequest,
    QueryDelegatorDelegationsResponse,
    QueryDelegatorUnbondingDelegationsRequest,
    QueryDelegatorUnbondingDelegationsResponse,
    QueryDelegatorValidatorRequest,
    QueryDelegatorValidatorResponse,
    QueryDelegatorValidatorsRequest,
    QueryDelegatorValidatorsResponse,
    QueryHistoricalInfoRequest,
    QueryHistoricalInfoResponse,
    QueryParamsRequest,
    QueryParamsResponse,
    QueryPoolRequest,
    QueryPoolResponse,
    QueryRedelegationsRequest,
    QueryRedelegationsResponse,
    QueryUnbondingDelegationRequest,
    QueryUnbondingDelegationResponse,
    QueryValidatorDelegationsRequest,
    QueryValidatorDelegationsResponse,
    QueryValidatorRequest,
    QueryValidatorResponse,
    QueryValidatorUnbondingDelegationsRequest,
    QueryValidatorUnbondingDelegationsResponse,
    QueryValidatorsRequest,
    QueryValidatorsResponse,
)
from cosmpy.staking.interface import Staking


class StakingRestClient(Staking):
    """Staking REST client."""

    API_URL = "/cosmos/staking/v1beta1"

    def __init__(self, rest_api: RestClient) -> None:
        """
        Initialize.

        :param rest_api: RestClient api
        """
        self._rest_api = rest_api

    def Validators(self, request: QueryValidatorsRequest) -> QueryValidatorsResponse:
        """
        Query all validators that match the given status.

        :param request: QueryValidatorsRequest
        :return: QueryValidatorsResponse
        """
        json_response = self._rest_api.get(f"{self.API_URL}/validators", request)
        return Parse(json_response, QueryValidatorsResponse())

    def Validator(self, request: QueryValidatorRequest) -> QueryValidatorResponse:
        """
        Query validator info for given validator address.

        :param request: QueryValidatorRequest
        :return: QueryValidatorResponse
        """
        json_response = self._rest_api.get(
            f"{self.API_URL}/validators/{request.validator_addr}",
        )
        return Parse(json_response, QueryValidatorResponse())

    def ValidatorDelegations(
        self, request: QueryValidatorDelegationsRequest
    ) -> QueryValidatorDelegationsResponse:
        """
        ValidatorDelegations queries delegate info for given validator.

        :param request: QueryValidatorDelegationsRequest
        :return: QueryValidatorDelegationsResponse
        """
        json_response = self._rest_api.get(
            f"{self.API_URL}/validators/{request.validator_addr}/delegations",
            request,
            ["validatorAddr"],
        )
        return Parse(json_response, QueryValidatorDelegationsResponse())

    def ValidatorUnbondingDelegations(
        self, request: QueryValidatorUnbondingDelegationsRequest
    ) -> QueryValidatorUnbondingDelegationsResponse:
        """
        ValidatorUnbondingDelegations queries unbonding delegations of a validator.

        :param request: ValidatorUnbondingDelegations
        :return: QueryValidatorUnbondingDelegationsResponse
        """
        json_response = self._rest_api.get(
            f"{self.API_URL}/validators/{request.validator_addr}/unbonding_delegations",
            request,
            ["validatorAddr"],
        )
        return Parse(json_response, QueryValidatorUnbondingDelegationsResponse())

    def Delegation(self, request: QueryDelegationRequest) -> QueryDelegationResponse:
        """
        Query delegate info for given validator delegator pair.

        :param request: QueryDelegationRequest
        :return: QueryDelegationResponse
        """
        json_response = self._rest_api.get(
            f"{self.API_URL}/validators/{request.validator_addr}/delegations/{request.delegator_addr}",
        )
        return Parse(json_response, QueryDelegationResponse())

    def UnbondingDelegation(
        self, request: QueryUnbondingDelegationRequest
    ) -> QueryUnbondingDelegationResponse:
        """
        UnbondingDelegation queries unbonding info for given validator delegator pair.

        :param request: QueryUnbondingDelegationRequest
        :return: QueryUnbondingDelegationResponse
        """
        json_response = self._rest_api.get(
            f"{self.API_URL}/validators/{request.validator_addr}/delegations/{request.delegator_addr}/unbonding_delegation",
        )
        return Parse(json_response, QueryUnbondingDelegationResponse())

    def DelegatorDelegations(
        self, request: QueryDelegatorDelegationsRequest
    ) -> QueryDelegatorDelegationsResponse:
        """
        DelegatorDelegations queries all delegations of a given delegator address.

        :param request: QueryDelegatorDelegationsRequest
        :return: QueryDelegatorDelegationsResponse
        """
        json_response = self._rest_api.get(
            f"{self.API_URL}/delegations/{request.delegator_addr}",
            request,
            ["delegatorAddr"],
        )
        return Parse(json_response, QueryDelegatorDelegationsResponse())

    def DelegatorUnbondingDelegations(
        self, request: QueryDelegatorUnbondingDelegationsRequest
    ) -> QueryDelegatorUnbondingDelegationsResponse:
        """
        DelegatorUnbondingDelegations queries all unbonding delegations of a given delegator address.

        :param request: QueryDelegatorUnbondingDelegationsRequest
        :return: QueryDelegatorUnbondingDelegationsResponse
        """
        json_response = self._rest_api.get(
            f"{self.API_URL}/delegators/{request.delegator_addr}/unbonding_delegations",
            request,
            ["delegatorAddr"],
        )
        return Parse(json_response, QueryDelegatorUnbondingDelegationsResponse())

    def Redelegations(
        self, request: QueryRedelegationsRequest
    ) -> QueryRedelegationsResponse:
        """
        Redelegations queries redelegations of given address.

        :param request: QueryRedelegationsRequest
        :return: QueryRedelegationsResponse
        """
        json_response = self._rest_api.get(
            f"{self.API_URL}/delegators/{request.delegator_addr}/redelegations",
            request,
            ["delegatorAddr"],
        )
        return Parse(json_response, QueryRedelegationsResponse())

    def DelegatorValidators(
        self, request: QueryDelegatorValidatorsRequest
    ) -> QueryDelegatorValidatorsResponse:
        """
        DelegatorValidators queries all validators info for given delegator address.

        :param request: QueryDelegatorValidatorsRequest
        :return: QueryDelegatorValidatorsRequest
        """
        json_response = self._rest_api.get(
            f"{self.API_URL}/delegators/{request.delegator_addr}/validators",
            request,
            ["delegatorAddr"],
        )
        return Parse(json_response, QueryDelegatorValidatorsResponse())

    def DelegatorValidator(
        self, request: QueryDelegatorValidatorRequest
    ) -> QueryDelegatorValidatorResponse:
        """
        DelegatorValidator queries validator info for given delegator validator pair.

        :param request: QueryDelegatorValidatorRequest
        :return: QueryDelegatorValidatorResponse
        """
        json_response = self._rest_api.get(
            f"{self.API_URL}/delegators/{request.delegator_addr}/validators/{request.validator_addr}",
        )
        return Parse(json_response, QueryDelegatorValidatorResponse())

    def HistoricalInfo(
        self, request: QueryHistoricalInfoRequest
    ) -> QueryHistoricalInfoResponse:
        """
        HistoricalInfo queries the historical info for given height.

        :param request: QueryHistoricalInfoRequest
        :return: QueryHistoricalInfoResponse
        """
        json_response = self._rest_api.get(
            f"{self.API_URL}/historical_info/{request.height}"
        )
        return Parse(json_response, QueryHistoricalInfoResponse())

    def Pool(self, request: QueryPoolRequest) -> QueryPoolResponse:
        """
        Pool queries the pool info.

        :param request: QueryPoolRequest
        :return: QueryPoolResponse
        """
        json_response = self._rest_api.get(f"{self.API_URL}/pool")
        return Parse(json_response, QueryPoolResponse())

    def Params(self, request: QueryParamsRequest) -> QueryParamsResponse:
        """
        Parameters queries the staking parameters.

        :param request: QueryParamsRequest
        :return: QueryParamsResponse
        """
        json_response = self._rest_api.get(f"{self.API_URL}/params")
        return Parse(json_response, QueryParamsResponse())
