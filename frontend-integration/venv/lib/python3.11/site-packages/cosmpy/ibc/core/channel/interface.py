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
"""Interface for the IBC Core Channel functionality of CosmosSDK."""

from abc import ABC, abstractmethod

from cosmpy.protos.ibc.core.channel.v1.query_pb2 import (
    QueryChannelClientStateRequest,
    QueryChannelClientStateResponse,
    QueryChannelConsensusStateRequest,
    QueryChannelConsensusStateResponse,
    QueryChannelRequest,
    QueryChannelResponse,
    QueryChannelsRequest,
    QueryChannelsResponse,
    QueryConnectionChannelsRequest,
    QueryConnectionChannelsResponse,
    QueryNextSequenceReceiveRequest,
    QueryNextSequenceReceiveResponse,
    QueryPacketAcknowledgementRequest,
    QueryPacketAcknowledgementResponse,
    QueryPacketAcknowledgementsRequest,
    QueryPacketAcknowledgementsResponse,
    QueryPacketCommitmentRequest,
    QueryPacketCommitmentResponse,
    QueryPacketCommitmentsRequest,
    QueryPacketCommitmentsResponse,
    QueryPacketReceiptRequest,
    QueryPacketReceiptResponse,
    QueryUnreceivedAcksRequest,
    QueryUnreceivedAcksResponse,
    QueryUnreceivedPacketsRequest,
    QueryUnreceivedPacketsResponse,
)


class IBCCoreChannel(ABC):
    """IBC Core Channel abstract class."""

    @abstractmethod
    def Channel(self, request: QueryChannelRequest) -> QueryChannelResponse:
        """
        Channel queries an IBC Channel.

        :param request: QueryChannelRequest
        :return: QueryChannelResponse
        """

    @abstractmethod
    def Channels(self, request: QueryChannelsRequest) -> QueryChannelsResponse:
        """
        Channels queries all the IBC channels of a chain.

        :param request: QueryChannelsRequest
        :return: QueryChannelsResponse
        """

    @abstractmethod
    def ConnectionChannels(
        self, request: QueryConnectionChannelsRequest
    ) -> QueryConnectionChannelsResponse:
        """
        ConnectionChannels queries all the channels associated with a connection.

        :param request: QueryConnectionChannelsRequest
        :return: QueryConnectionChannelsResponse
        """

    @abstractmethod
    def ChannelClientState(
        self, request: QueryChannelClientStateRequest
    ) -> QueryChannelClientStateResponse:
        """
        ChannelClientState queries for the client state for the channel associated with the provided channel identifiers.

        :param request: QueryChannelClientStateRequest
        :return: QueryChannelClientStateResponse
        """

    @abstractmethod
    def ChannelConsensusState(
        self, request: QueryChannelConsensusStateRequest
    ) -> QueryChannelConsensusStateResponse:
        """
        ChannelConsensusState queries for the consensus state for the channel associated with the provided channel identifiers.

        :param request: QueryChannelConsensusStateRequest
        :return: QueryChannelConsensusStateResponse
        """

    @abstractmethod
    def PacketCommitment(
        self, request: QueryPacketCommitmentRequest
    ) -> QueryPacketCommitmentResponse:
        """
        PacketCommitment queries a stored packet commitment hash.

        :param request: QueryPacketCommitmentRequest
        :return: QueryPacketCommitmentResponse
        """

    @abstractmethod
    def PacketCommitments(
        self, request: QueryPacketCommitmentsRequest
    ) -> QueryPacketCommitmentsResponse:
        """
        PacketCommitments returns all the packet commitments hashes associated with a channel.

        :param request: QueryPacketCommitmentsRequest
        :return: QueryPacketCommitmentsResponse
        """

    @abstractmethod
    def PacketReceipt(
        self, request: QueryPacketReceiptRequest
    ) -> QueryPacketReceiptResponse:
        """
        PacketReceipt queries if a given packet sequence has been received on the queried chain.

        :param request: QueryPacketReceiptRequest
        :return: QueryPacketReceiptResponse
        """

    @abstractmethod
    def PacketAcknowledgement(
        self, request: QueryPacketAcknowledgementRequest
    ) -> QueryPacketAcknowledgementResponse:
        """
        PacketAcknowledgement queries a stored packet acknowledgment hash.

        :param request: QueryPacketAcknowledgementRequest
        :return: QueryPacketAcknowledgementResponse
        """

    @abstractmethod
    def PacketAcknowledgements(
        self, request: QueryPacketAcknowledgementsRequest
    ) -> QueryPacketAcknowledgementsResponse:
        """
        PacketAcknowledgements returns all the packet acknowledgments associated with a channel.

        :param request: QueryPacketAcknowledgementsRequest
        :return: QueryPacketAcknowledgementsResponse
        """

    @abstractmethod
    def UnreceivedPackets(
        self, request: QueryUnreceivedPacketsRequest
    ) -> QueryUnreceivedPacketsResponse:
        """
        UnreceivedPackets returns all the unreceived IBC packets associated with a channel and sequences.

        :param request: QueryUnreceivedPacketsRequest
        :return: QueryUnreceivedPacketsResponse
        """

    @abstractmethod
    def UnreceivedAcks(
        self, request: QueryUnreceivedAcksRequest
    ) -> QueryUnreceivedAcksResponse:
        """
        UnreceivedAcks returns all the unreceived IBC acknowledgments associated with a channel and sequences.

        :param request: QueryUnreceivedAcksRequest
        :return: QueryUnreceivedAcksResponse
        """

    @abstractmethod
    def NextSequenceReceive(
        self, request: QueryNextSequenceReceiveRequest
    ) -> QueryNextSequenceReceiveResponse:
        """
        NextSequenceReceive returns the next receive sequence for a given channel.

        :param request: QueryNextSequenceReceiveRequest
        :return: QueryNextSequenceReceiveResponse
        """
