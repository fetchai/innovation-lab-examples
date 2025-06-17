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

"""Interface for the Mint functionality of CosmosSDK."""

from abc import ABC, abstractmethod

from cosmpy.protos.cosmos.mint.v1beta1.query_pb2 import (
    QueryAnnualProvisionsResponse,
    QueryInflationResponse,
    QueryParamsResponse,
)


class Mint(ABC):
    """Mint abstract class."""

    @abstractmethod
    def AnnualProvisions(self) -> QueryAnnualProvisionsResponse:
        """
        AnnualProvisions current minting annual provisions value.

        :return: a QueryAnnualProvisionsResponse instance
        """

    @abstractmethod
    def Inflation(self) -> QueryInflationResponse:
        """
        Inflation returns the current minting inflation value.

        :return: a QueryInflationResponse instance
        """

    @abstractmethod
    def Params(self) -> QueryParamsResponse:
        """
        Params returns the total set of minting parameters.

        :return: QueryParamsResponse
        """
