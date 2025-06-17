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
"""Interface for the Gov functionality of CosmosSDK."""

from abc import ABC, abstractmethod

from cosmpy.protos.cosmos.gov.v1beta1.query_pb2 import (
    QueryDepositRequest,
    QueryDepositResponse,
    QueryDepositsRequest,
    QueryDepositsResponse,
    QueryParamsRequest,
    QueryParamsResponse,
    QueryProposalRequest,
    QueryProposalResponse,
    QueryProposalsRequest,
    QueryProposalsResponse,
    QueryTallyResultRequest,
    QueryTallyResultResponse,
    QueryVoteRequest,
    QueryVoteResponse,
    QueryVotesRequest,
    QueryVotesResponse,
)


class Gov(ABC):
    """Gov abstract class."""

    @abstractmethod
    def Proposal(self, request: QueryProposalRequest) -> QueryProposalResponse:
        """
        Proposal queries proposal details based on ProposalID.

        :param request: QueryProposalRequest with proposal id

        :return: QueryProposalResponse
        """

    @abstractmethod
    def Proposals(self, request: QueryProposalsRequest) -> QueryProposalsResponse:
        """
        Proposals queries all proposals based on given status.

        :param request: QueryProposalsRequest

        :return: QueryProposalsResponse
        """

    @abstractmethod
    def Vote(self, request: QueryVoteRequest) -> QueryVoteResponse:
        """
        Vote queries voted information based on proposalID, voterAddr.

        :param request: QueryVoteRequest with voter and proposal id

        :return: QueryVoteResponse
        """

    @abstractmethod
    def Votes(self, request: QueryVotesRequest) -> QueryVotesResponse:
        """
        Votes queries votes of a given proposal.

        :param request: QueryVotesResponse with proposal id

        :return: QueryVotesResponse
        """

    @abstractmethod
    def Params(self, request: QueryParamsRequest) -> QueryParamsResponse:
        """
        Params queries all parameters of the gov module.

        :param request: QueryParamsRequest with params_type

        :return: QueryParamsResponse
        """

    @abstractmethod
    def Deposit(self, request: QueryDepositRequest) -> QueryDepositResponse:
        """
        Deposit queries single deposit information based proposalID, depositAddr.

        :param request: QueryDepositRequest with depositor and proposal_id

        :return: QueryDepositResponse
        """

    @abstractmethod
    def Deposits(self, request: QueryDepositsRequest) -> QueryDepositsResponse:
        """Deposits queries all deposits of a single proposal.

        :param request: QueryDepositsRequest with proposal_id

        :return: QueryDepositsResponse
        """

    @abstractmethod
    def TallyResult(self, request: QueryTallyResultRequest) -> QueryTallyResultResponse:
        """
        Tally Result queries the tally of a proposal vote.

        :param request: QueryTallyResultRequest with proposal_id

        :return: QueryTallyResultResponse
        """
