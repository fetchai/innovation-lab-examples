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

"""Implementation of Wasm interface using REST."""

import base64
import json

from google.protobuf.json_format import Parse, ParseDict

from cosmpy.common.rest_client import RestClient
from cosmpy.common.types import JSONLike
from cosmpy.common.utils import json_encode
from cosmpy.cosmwasm.interface import CosmWasm
from cosmpy.protos.cosmwasm.wasm.v1.query_pb2 import (
    QueryAllContractStateRequest,
    QueryAllContractStateResponse,
    QueryCodeRequest,
    QueryCodeResponse,
    QueryCodesRequest,
    QueryCodesResponse,
    QueryContractHistoryRequest,
    QueryContractHistoryResponse,
    QueryContractInfoRequest,
    QueryContractInfoResponse,
    QueryContractsByCodeRequest,
    QueryContractsByCodeResponse,
    QueryRawContractStateRequest,
    QueryRawContractStateResponse,
    QuerySmartContractStateRequest,
    QuerySmartContractStateResponse,
)
from cosmpy.protos.cosmwasm.wasm.v1.types_pb2 import AccessType


class CosmWasmRestClient(CosmWasm):
    """Wasm REST client."""

    API_URL = "/cosmwasm/wasm/v1"

    def __init__(self, rest_api: RestClient):
        """
        Create CosmWasm rest client.

        :param rest_api: RestClient api
        """
        self._rest_api = rest_api

    def ContractInfo(
        self, request: QueryContractInfoRequest
    ) -> QueryContractInfoResponse:
        """
        Get the contract meta data.

        :param request: QueryContractInfoRequest

        :return: QueryContractInfoResponse
        """
        response = self._rest_api.get(
            f"{self.API_URL}/contract/{request.address}", request, ["address"]
        )
        return Parse(response, QueryContractInfoResponse())

    def ContractHistory(
        self, request: QueryContractHistoryRequest
    ) -> QueryContractHistoryResponse:
        """
        Get the contract code history.

        :param request: QueryContractHistoryRequest

        :return: QueryContractHistoryResponse
        """
        response = self._rest_api.get(
            f"{self.API_URL}/contract/{request.address}/history", request, ["address"]
        )

        return ParseDict(
            self._fix_history_response(response), QueryContractHistoryResponse()
        )

    def ContractsByCode(
        self, request: QueryContractsByCodeRequest
    ) -> QueryContractsByCodeResponse:
        """
        List all smart contracts for a code id.

        :param request: QueryContractsByCodeRequest

        :return: QueryContractsByCodeResponse
        """
        response = self._rest_api.get(
            f"{self.API_URL}/code/{request.code_id}/contracts", request, ["codeId"]
        )
        return Parse(response, QueryContractsByCodeResponse())

    def AllContractState(
        self, request: QueryAllContractStateRequest
    ) -> QueryAllContractStateResponse:
        """
        Get all raw store data for a single contract.

        :param request: QueryAllContractStateRequest

        :return: QueryAllContractStateResponse
        """
        response = self._rest_api.get(
            f"{self.API_URL}/contract/{request.address}/state", request, ["address"]
        )
        return Parse(response, QueryAllContractStateResponse())

    def RawContractState(
        self, request: QueryRawContractStateRequest
    ) -> QueryRawContractStateResponse:
        """
        Get single key from the raw store data of a contract.

        :param request: QueryRawContractStateRequest

        :return: QueryRawContractStateResponse
        """
        # Convert request.query_data dict to base64 encoded string
        query_data = base64.b64encode(request.query_data).decode()

        response = self._rest_api.get(
            f"{self.API_URL}/contract/{request.address}/raw/{query_data}",
            request,
            ["address", "queryData"],
        )

        return ParseDict(
            self._fix_state_response(response), QueryRawContractStateResponse()
        )

    def SmartContractState(
        self, request: QuerySmartContractStateRequest
    ) -> QuerySmartContractStateResponse:
        """
        Get smart query result from the contract.

        :param request: QuerySmartContractStateRequest

        :return: QuerySmartContractStateResponse
        """
        query_data = base64.b64encode(request.query_data).decode()
        response = self._rest_api.get(
            f"{self.API_URL}/contract/{request.address}/smart/{query_data}",
            request,
            ["address", "queryData"],
        )

        return ParseDict(
            self._fix_state_response(response), QuerySmartContractStateResponse()
        )

    def Code(self, request: QueryCodeRequest) -> QueryCodeResponse:
        """
        Get the binary code and metadata for a single wasm code.

        :param request: QueryCodeRequest

        :return: QueryCodeResponse
        """
        response = self._rest_api.get(
            f"{self.API_URL}/code/{request.code_id}", request, ["codeId"]
        )

        return Parse(response, QueryCodeResponse())

    def Codes(self, request: QueryCodesRequest) -> QueryCodesResponse:
        """
        Get the metadata for all stored wasm codes.

        :param request: QueryCodesRequest

        :return: QueryCodesResponse
        """
        response = self._rest_api.get(f"{self.API_URL}/code", request)
        responses_json = json.loads(response)
        for code_info in responses_json["code_infos"]:
            if "instantiate_permission" not in code_info:
                continue
            code_info["instantiate_permission"]["permission"] = self._fix_permission(
                code_info["instantiate_permission"]["permission"]
            )
        response = json.dumps(responses_json).encode("utf-8")
        return Parse(response, QueryCodesResponse())

    def _fix_permission(self, permission_name):
        permission_map = {
            "Nobody": AccessType.Value("ACCESS_TYPE_NOBODY"),
            "OnlyAddress": AccessType.Value("ACCESS_TYPE_ONLY_ADDRESS"),
            "Everybody": AccessType.Value("ACCESS_TYPE_EVERYBODY"),
            "Unspecified": AccessType.Value("ACCESS_TYPE_UNSPECIFIED"),
        }
        return permission_map.get(
            permission_name, AccessType.Value("ACCESS_TYPE_UNSPECIFIED")
        )

    @staticmethod
    def _fix_state_response(response: bytes) -> JSONLike:
        """
        Fix raw/smart contract state response to be parsable to protobuf object.

        - Converts dict to base64 encoded string

        :param response: raw/smart contract state response
        :return: Fixed response in form of dict
        """
        dict_response = json.loads(response)
        dict_response["data"] = base64.b64encode(
            json_encode(dict_response["data"]).encode("UTF8")
        ).decode()
        return dict_response

    @staticmethod
    def _fix_history_response(response: bytes) -> JSONLike:
        """
        Fix contract history response to be parsable to protobuf object.

        - Converts dict to base64 encoded string

        :param response: raw/smart contract state response
        :return: Fixed response in form of dict
        """
        dict_response = json.loads(response)
        for entry in dict_response["entries"]:
            entry["msg"] = base64.b64encode(
                json_encode(entry["msg"]).encode("UTF8")
            ).decode()
        return dict_response
