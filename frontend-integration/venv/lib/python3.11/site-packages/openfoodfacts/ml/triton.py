import functools
import struct

import grpc
import numpy as np
from tritonclient.grpc import service_pb2, service_pb2_grpc
from tritonclient.grpc.service_pb2_grpc import GRPCInferenceServiceStub


@functools.cache
def get_triton_inference_stub(triton_uri: str) -> GRPCInferenceServiceStub:
    """Return a gRPC stub for Triton Inference Server.

    :param triton_uri: URI of the Triton Inference Server
    :return: gRPC stub for Triton Inference Server
    """
    channel = grpc.insecure_channel(triton_uri)
    return service_pb2_grpc.GRPCInferenceServiceStub(channel)


def deserialize_byte_tensor(data: bytes) -> list[str]:
    """Deserialize a byte tensor into a list of string.

    This is used to deserialize string array outputs from Triton models.
    """
    offset = 0
    # 4 bytes are used to encode string length
    int_byte_len = 4
    array = []
    while len(data) >= offset + int_byte_len:
        str_length = struct.unpack("<I", data[offset : offset + int_byte_len])[0]
        offset += int_byte_len
        string_data = data[offset : offset + str_length].decode("utf-8")
        offset += str_length
        array.append(string_data)
    return array


# Copied from triton client repository
def serialize_byte_tensor(input_tensor):
    """
    Serializes a bytes tensor into a flat numpy array of length prepended
    bytes. The numpy array should use dtype of np.object_. For np.bytes_,
    numpy will remove trailing zeros at the end of byte sequence and because
    of this it should be avoided.
    Parameters
    ----------
    input_tensor : np.array
        The bytes tensor to serialize.
    Returns
    -------
    serialized_bytes_tensor : np.array
        The 1-D numpy array of type uint8 containing the serialized bytes in
        'C' order.
    Raises
    ------
    InferenceServerException
        If unable to serialize the given tensor.
    """

    if input_tensor.size == 0:
        return ()

    # If the input is a tensor of string/bytes objects, then must flatten those
    # into a 1-dimensional array containing the 4-byte byte size followed by
    # the actual element bytes. All elements are concatenated together in "C"
    # order.
    if (input_tensor.dtype == np.object_) or (input_tensor.dtype.type == np.bytes_):
        flattened_ls = []
        for obj in np.nditer(input_tensor, flags=["refs_ok"], order="C"):
            # If directly passing bytes to BYTES type,
            # don't convert it to str as Python will encode the
            # bytes which may distort the meaning
            if input_tensor.dtype == np.object_:
                if type(obj.item()) == bytes:
                    s = obj.item()
                else:
                    s = str(obj.item()).encode("utf-8")
            else:
                s = obj.item()
            flattened_ls.append(struct.pack("<I", len(s)))
            flattened_ls.append(s)
        flattened = b"".join(flattened_ls)
        return flattened
    return None


def add_triton_infer_input_tensor(request, name: str, data: np.ndarray, datatype: str):
    """Create and add an input tensor to a Triton gRPC Inference request.

    :param request: the Triton Inference request
    :param name: the name of the input tensor
    :param data: the input tensor data
    :param datatype: the datatype of the input tensor (e.g. "FP32")
    """
    input_tensor = service_pb2.ModelInferRequest().InferInputTensor()
    input_tensor.name = name
    input_tensor.datatype = datatype
    input_tensor.shape.extend(data.shape)
    request.inputs.extend([input_tensor])
    request.raw_input_contents.extend([data.tobytes()])
