import dataclasses
import logging
import time
from typing import Optional

import numpy as np
from cv2 import dnn
from PIL import Image
from tritonclient.grpc import service_pb2

from openfoodfacts.ml.utils import convert_image_to_array
from openfoodfacts.types import JSONType

from .triton import add_triton_infer_input_tensor, get_triton_inference_stub

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ObjectDetectionRawResult:
    num_detections: int
    detection_boxes: np.ndarray
    detection_scores: np.ndarray
    detection_classes: np.ndarray
    label_names: list[str]

    def to_list(self) -> list[JSONType]:
        """Convert the detection results to a JSON serializable format."""
        results = []
        for bounding_box, score, label in zip(
            self.detection_boxes, self.detection_scores, self.detection_classes
        ):
            label_int = int(label)
            label_str = self.label_names[label_int]
            if label_str is not None:
                result = {
                    "bounding_box": tuple(bounding_box.tolist()),  # type: ignore
                    "score": float(score),
                    "label": label_str,
                }
                results.append(result)
        return results


class ObjectDetector:
    def __init__(self, model_name: str, label_names: list[str], image_size: int = 640):
        """An object detection detector based on Yolo models.

        We support models trained with Yolov8, v9, v10 and v11.

        :param model_name: the name of the model, as registered in Triton
        :param label_names: the list of label names
        :param image_size: the size of the input image for the model
        """
        self.model_name: str = model_name
        self.label_names = label_names
        self.image_size = image_size

    def detect_from_image(
        self,
        image: Image.Image,
        triton_uri: str,
        threshold: float = 0.5,
        model_version: Optional[str] = None,
    ) -> ObjectDetectionRawResult:
        """Run an object detection model on an image.

        The model must have been trained with Ultralytics library.

        :param image: the input Pillow image
        :param triton_uri: URI of the Triton Inference Server, defaults to
            None. If not provided, the default value from settings is used.
        :param threshold: the minimum score for a detection to be considered,
            defaults to 0.5.
        :param model_version: the version of the model to use, defaults to
            None (latest).
        :return: the detection result
        """
        image_array, scale_x, scale_y = self.preprocess(image)
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
        response = self.postprocess(
            response, threshold=threshold, scale_x=scale_x, scale_y=scale_y
        )
        latency = time.monotonic() - start_time
        logger.debug("Post-processing time for %s: %s", self.model_name, latency)
        return response

    def preprocess(self, image: Image.Image) -> tuple[np.ndarray, float, float]:
        # Yolo object detection models expect a specific image dimension
        width, height = image.size
        # Prepare a square image for inference
        max_size = max(height, width)
        # We paste the original image into a larger square image,
        # in the upper-left corner, on a black background.
        squared_image = Image.new("RGB", (max_size, max_size), color="black")
        squared_image.paste(image, (0, 0))
        resized_image = squared_image.resize((self.image_size, self.image_size))

        # As we don't process the original image but a modified version of it,
        # we need to compute the scale factor for the x and y axis.
        image_ratio = width / height
        scale_x: float
        scale_y: float
        if image_ratio < 1:  # portrait, height > width
            scale_x = self.image_size * image_ratio
            scale_y = self.image_size
        else:  # landscape, width > height
            scale_x = self.image_size
            scale_y = self.image_size / image_ratio

        # Preprocess the image and prepare blob for model
        image_array = (
            convert_image_to_array(resized_image)
            .transpose((2, 0, 1))
            .astype(np.float32)
        )
        image_array = image_array / 255.0
        image_array = np.expand_dims(image_array, axis=0)
        return image_array, scale_x, scale_y

    def postprocess(
        self, response, threshold: float, scale_x: float, scale_y: float
    ) -> ObjectDetectionRawResult:
        if len(response.outputs) != 1:
            raise ValueError(f"expected 1 output, got {len(response.outputs)}")

        if len(response.raw_output_contents) != 1:
            raise ValueError(
                f"expected 1 raw output content, got {len(response.raw_output_contents)}"
            )

        output_index = {output.name: i for i, output in enumerate(response.outputs)}
        output = np.frombuffer(
            response.raw_output_contents[output_index["output0"]],
            dtype=np.float32,
        ).reshape((1, len(self.label_names) + 4, -1))[0]

        # output is of shape (num_classes + 4, num_detections)
        rows = output.shape[1]
        raw_detection_classes = np.zeros(rows, dtype=int)
        raw_detection_scores = np.zeros(rows, dtype=np.float32)
        raw_detection_boxes = np.zeros((rows, 4), dtype=np.float32)

        for i in range(rows):
            classes_scores = output[4:, i]
            max_cls_idx = np.argmax(classes_scores)
            max_score = classes_scores[max_cls_idx]
            if max_score < threshold:
                continue
            raw_detection_classes[i] = max_cls_idx
            raw_detection_scores[i] = max_score

            # The bounding box is in the format (x, y, width, height) in
            # relative coordinates
            # x and y are the coordinates of the center of the bounding box
            bbox_width = output[2, i]
            bbox_height = output[3, i]
            x_min = output[0, i] - 0.5 * bbox_width
            y_min = output[1, i] - 0.5 * bbox_height
            x_max = x_min + bbox_width
            y_max = y_min + bbox_height

            # We save the bounding box in the format
            # (y_min, x_min, y_max, x_max) in relative coordinates
            # Scale the bounding boxes back to the original image size
            raw_detection_boxes[i, 0] = max(0.0, min(1.0, y_min / scale_y))
            raw_detection_boxes[i, 1] = max(0.0, min(1.0, x_min / scale_x))
            raw_detection_boxes[i, 2] = max(0.0, min(1.0, y_max / scale_y))
            raw_detection_boxes[i, 3] = max(0.0, min(1.0, x_max / scale_x))

        # Perform NMS (Non Maximum Suppression)
        detection_box_indices = dnn.NMSBoxes(
            raw_detection_boxes,  # type: ignore
            raw_detection_scores,  # type: ignore
            score_threshold=threshold,
            # the following values are copied from Ultralytics settings
            nms_threshold=0.45,
            eta=0.5,
        )
        detection_classes = np.zeros(len(detection_box_indices), dtype=int)
        detection_scores = np.zeros(len(detection_box_indices), dtype=np.float32)
        detection_boxes = np.zeros((len(detection_box_indices), 4), dtype=np.float32)

        for i, idx in enumerate(detection_box_indices):
            detection_classes[i] = raw_detection_classes[idx]
            detection_scores[i] = raw_detection_scores[idx]
            detection_boxes[i] = raw_detection_boxes[idx]

        result = ObjectDetectionRawResult(
            num_detections=rows,
            detection_classes=detection_classes,
            detection_boxes=detection_boxes,
            detection_scores=detection_scores,
            label_names=self.label_names,
        )
        return result
