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

"""Interface for the Auth functionality of CosmosSDK."""

from abc import ABC, abstractmethod

from cosmpy.protos.cosmos.auth.v1beta1.query_pb2 import (
    QueryAccountRequest,
    QueryAccountResponse,
    QueryParamsRequest,
    QueryParamsResponse,
)


class Auth(ABC):
    """Auth abstract class."""

    @abstractmethod
    def Account(self, request: QueryAccountRequest) -> QueryAccountResponse:
        """
        Query account data - sequence, account_id, etc.

        :param request: QueryAccountRequest that contains account address

        :return: QueryAccountResponse
        """

    @abstractmethod
    def Params(self, request: QueryParamsRequest) -> QueryParamsResponse:
        """
        Query all parameters.

        :param request: QueryParamsRequest

        :return: QueryParamsResponse
        """
