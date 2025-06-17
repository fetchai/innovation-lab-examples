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

"""Interface for the Staking functionality of CosmosSDK."""

from abc import ABC, abstractmethod

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


class Staking(ABC):
    """Staking abstract class."""

    @abstractmethod
    def Validators(self, request: QueryValidatorsRequest) -> QueryValidatorsResponse:
        """
        Query all validators that match the given status.

        :param request: QueryValidatorsRequest
        :return: QueryValidatorsResponse
        """

    @abstractmethod
    def Validator(self, request: QueryValidatorRequest) -> QueryValidatorResponse:
        """
        Query validator info for given validator address.

        :param request: QueryValidatorRequest
        :return: QueryValidatorResponse
        """

    @abstractmethod
    def ValidatorDelegations(
        self, request: QueryValidatorDelegationsRequest
    ) -> QueryValidatorDelegationsResponse:
        """
        Query delegate info for given validator.

        :param request: QueryValidatorDelegationsRequest
        :return: QueryValidatorDelegationsResponse
        """

    @abstractmethod
    def ValidatorUnbondingDelegations(
        self, request: QueryValidatorUnbondingDelegationsRequest
    ) -> QueryValidatorUnbondingDelegationsResponse:
        """
        Query unbonding delegations of a validator.

         :param request: ValidatorUnbondingDelegations
         :return: QueryValidatorUnbondingDelegationsResponse
        """

    @abstractmethod
    def Delegation(self, request: QueryDelegationRequest) -> QueryDelegationResponse:
        """
        Query delegate info for given validator delegator pair.

        :param request: QueryDelegationRequest
        :return: QueryDelegationResponse
        """

    @abstractmethod
    def UnbondingDelegation(
        self, request: QueryUnbondingDelegationRequest
    ) -> QueryUnbondingDelegationResponse:
        """
        UnbondingDelegation queries unbonding info for given validator delegator pair.

        :param request: QueryUnbondingDelegationRequest
        :return: QueryUnbondingDelegationResponse
        """

    @abstractmethod
    def DelegatorDelegations(
        self, request: QueryDelegatorDelegationsRequest
    ) -> QueryDelegatorDelegationsResponse:
        """
        DelegatorDelegations queries all delegations of a given delegator address.

        :param request: QueryDelegatorDelegationsRequest
        :return: QueryDelegatorDelegationsResponse
        """

    @abstractmethod
    def DelegatorUnbondingDelegations(
        self, request: QueryDelegatorUnbondingDelegationsRequest
    ) -> QueryDelegatorUnbondingDelegationsResponse:
        """
        DelegatorUnbondingDelegations queries all unbonding delegations of a given delegator address.

        :param request: QueryDelegatorUnbondingDelegationsRequest
        :return: QueryDelegatorUnbondingDelegationsResponse
        """

    @abstractmethod
    def Redelegations(
        self, request: QueryRedelegationsRequest
    ) -> QueryRedelegationsResponse:
        """
        Redelegations queries redelegations of given address.

        :param request: QueryRedelegationsRequest
        :return: QueryRedelegationsResponse
        """

    @abstractmethod
    def DelegatorValidators(
        self, request: QueryDelegatorValidatorsRequest
    ) -> QueryDelegatorValidatorsResponse:
        """
        DelegatorValidators queries all validators info for given delegator address.

        :param request: QueryDelegatorValidatorsRequest
        :return: QueryDelegatorValidatorsRequest
        """

    @abstractmethod
    def DelegatorValidator(
        self, request: QueryDelegatorValidatorRequest
    ) -> QueryDelegatorValidatorResponse:
        """
        DelegatorValidator queries validator info for given delegator validator pair.

        :param request: QueryDelegatorValidatorRequest
        :return: QueryDelegatorValidatorResponse
        """

    @abstractmethod
    def HistoricalInfo(
        self, request: QueryHistoricalInfoRequest
    ) -> QueryHistoricalInfoResponse:
        """
        HistoricalInfo queries the historical info for given height.

        :param request: QueryHistoricalInfoRequest
        :return: QueryHistoricalInfoResponse
        """

    @abstractmethod
    def Pool(self, request: QueryPoolRequest) -> QueryPoolResponse:
        """
        Pool queries the pool info.

        :param request: QueryPoolRequest
        :return: QueryPoolResponse
        """

    @abstractmethod
    def Params(self, request: QueryParamsRequest) -> QueryParamsResponse:
        """
        Parameters queries the staking parameters.

        :param request: QueryParamsRequest
        :return: QueryParamsResponse
        """
