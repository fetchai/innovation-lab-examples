import logging
import math
import time
import typing
from typing import Optional

import numpy as np
from PIL import Image, ImageOps
from tritonclient.grpc import service_pb2

from openfoodfacts.ml.triton import (
    add_triton_infer_input_tensor,
    get_triton_inference_stub,
)

logger = logging.getLogger(__name__)


def classify_transforms(
    img: Image.Image,
    size: int = 224,
    mean: tuple[float, float, float] = (0.0, 0.0, 0.0),
    std: tuple[float, float, float] = (1.0, 1.0, 1.0),
    interpolation: Image.Resampling = Image.Resampling.BILINEAR,
    crop_fraction: float = 1.0,
) -> np.ndarray:
    """
    Applies a series of image transformations including resizing, center
    cropping, normalization, and conversion to a NumPy array.

    Transformation steps is based on the one used in the Ultralytics library:
    https://github.com/ultralytics/ultralytics/blob/main/ultralytics/data/augment.py#L2319

    :param img: Input Pillow image.
    :param size: The target size for the transformed image (shortest edge).
    :param mean: Mean values for each RGB channel used in normalization.
    :param std: Standard deviation values for each RGB channel used in
        normalization.
    :param interpolation: Interpolation method from PIL (
    Image.Resampling.NEAREST, Image.Resampling.BILINEAR,
    Image.Resampling.BICUBIC).
    :param crop_fraction: Fraction of the image to be cropped.
    :return: The transformed image as a NumPy array.
    """
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Rotate the image based on the EXIF orientation if needed
    img = typing.cast(Image.Image, ImageOps.exif_transpose(img))

    # Step 1: Resize while preserving the aspect ratio
    width, height = img.size

    # Calculate scale size while preserving aspect ratio
    scale_size = math.floor(size / crop_fraction)

    aspect_ratio = width / height
    if width < height:
        new_width = scale_size
        new_height = int(new_width / aspect_ratio)
    else:
        new_height = scale_size
        new_width = int(new_height * aspect_ratio)

    img = img.resize((new_width, new_height), interpolation)

    # Step 2: Center crop
    left = (new_width - size) // 2
    top = (new_height - size) // 2
    right = left + size
    bottom = top + size
    img = img.crop((left, top, right, bottom))

    # Step 3: Convert the image to a NumPy array and scale pixel values to
    # [0, 1]
    img_array = np.array(img).astype(np.float32) / 255.0

    # Step 4: Normalize the image
    mean_np = np.array(mean, dtype=np.float32).reshape(1, 1, 3)
    std_np = np.array(std, dtype=np.float32).reshape(1, 1, 3)
    img_array = (img_array - mean_np) / std_np

    # Step 5: Change the order of dimensions from (H, W, C) to (C, H, W)
    img_array = np.transpose(img_array, (2, 0, 1))
    return img_array


class ImageClassifier:
    def __init__(self, model_name: str, label_names: list[str], image_size: int = 224):
        """An image classifier based on Yolo models.

        We support models trained with Yolov8, v9, v10 and v11.

        :param model_name: the name of the model, as registered in Triton
        :param label_names: the list of label names
        :param image_size: the size of the input image for the model
        """
        self.model_name: str = model_name
        self.label_names = label_names
        self.image_size = image_size

    def predict(
        self,
        image: Image.Image,
        triton_uri: str,
        model_version: Optional[str] = None,
    ) -> list[tuple[str, float]]:
        """Run an image classification model on an image.

        The model is expected to have been trained with Ultralytics library
        (Yolov8).

        :param image: the input Pillow image
        :param triton_uri: URI of the Triton Inference Server, defaults to
            None. If not provided, the default value from settings is used.
        :return: the prediction results as a list of tuples (label, confidence)
        """
        image_array = self.preprocess(image)

        grpc_stub = get_triton_inference_stub(triton_uri)
        request = service_pb2.ModelInferRequest()
        request.model_name = self.model_name
        if model_version:
            request.model_version = model_version
        add_triton_infer_input_tensor(
            request, name="images", data=image_array, datatype="FP32"
        )
        start_time = time.monotonic()
        response = grpc_stub.ModelInfer(request)
        latency = time.monotonic() - start_time
        logger.debug("Inference time for %s: %s", self.model_name, latency)

        start_time = time.monotonic()
        result = self.postprocess(response)
        latency = time.monotonic() - start_time
        logger.debug("Post-processing time for %s: %s", self.model_name, latency)
        return result

    def preprocess(self, image: Image.Image) -> np.ndarray:
        """Preprocess an image for object detection.

        :param image: the input Pillow image
        :return: the preprocessed image as a NumPy array
        """
        image_array = classify_transforms(image, size=self.image_size)
        return np.expand_dims(image_array, axis=0)

    def postprocess(
        self, response: service_pb2.ModelInferResponse
    ) -> list[tuple[str, float]]:
        """Postprocess the inference result.

        :param response: the inference response
        """
        if len(response.outputs) != 1:
            raise Exception(f"expected 1 output, got {len(response.outputs)}")

        if len(response.raw_output_contents) != 1:
            raise Exception(
                f"expected 1 raw output content, got {len(response.raw_output_contents)}"
            )

        output_index = {output.name: i for i, output in enumerate(response.outputs)}
        output = np.frombuffer(
            response.raw_output_contents[output_index["output0"]],
            dtype=np.float32,
        ).reshape((1, len(self.label_names)))[0]

        score_indices = np.argsort(-output)
        return [(self.label_names[i], float(output[i])) for i in score_indices]
