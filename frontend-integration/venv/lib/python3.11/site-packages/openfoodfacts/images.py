import logging
from pathlib import Path
from typing import List, Optional, Tuple, Union
from urllib.parse import urlparse

import requests

from openfoodfacts.types import Environment, Flavor, JSONType
from openfoodfacts.utils import ImageDownloadItem, URLBuilder, get_image_from_url

logger = logging.getLogger(__name__)


# Base URL of the public Open Food Facts S3 bucket
AWS_S3_BASE_URL = "https://openfoodfacts-images.s3.eu-west-3.amazonaws.com/data"


_pillow_available = True
try:
    from PIL import Image
except ImportError:
    _pillow_available = False


def split_barcode(barcode: str) -> List[str]:
    """Split barcode in the same way as done by Product Opener to generate a
    product image folder.

    :param barcode: The barcode of the product. For the pro platform only,
        it must be prefixed with the org ID using the format
        `{ORG_ID}/{BARCODE}`
    :raises ValueError: raise a ValueError if `barcode` is invalid
    :return: a list containing the splitted barcode
    """
    org_id = None
    if "/" in barcode:
        # For the pro platform, `barcode` is expected to be in the format
        # `{ORG_ID}/{BARCODE}` (ex: `org-lea-nature/3307130803004`)
        org_id, barcode = barcode.split("/", maxsplit=1)

    if not barcode.isdigit():
        raise ValueError(f"unknown barcode format: {barcode}")

    # Pad the barcode with zeros to ensure it has 13 digits
    barcode = barcode.zfill(13)
    # Split the first 9 digits of the barcode into 3 groups of 3 digits to
    # get the first 3 folder names and use the rest of the barcode as the
    # last folder name
    splits = [barcode[0:3], barcode[3:6], barcode[6:9], barcode[9:]]

    if org_id is not None:
        # For the pro platform only, images and OCRs belonging to an org
        # are stored in a folder named after the org for all its products, ex:
        # https://images.pro.openfoodfacts.org/images/products/org-lea-nature/330/713/080/3004/1.jpg
        splits.insert(0, org_id)

    return splits


def _generate_file_path(code: str, image_id: str, suffix: str):
    splitted_barcode = split_barcode(code)
    return f"/{'/'.join(splitted_barcode)}/{image_id}{suffix}"


def generate_image_path(code: str, image_id: str) -> str:
    """Generate an image path.

    It's used to generate a unique identifier of an image for a product (and
    to generate an URL to fetch this image from the server).

    :param code: the product barcode
    :param image_id: the image ID (ex: `1`, `ingredients_fr.full`,...)
    :return: the full image path
    """
    return _generate_file_path(code, image_id, ".jpg")


def generate_json_ocr_path(code: str, image_id: str) -> str:
    """Generate a JSON OCR path.

    It's used to generate a unique identifier of an OCR results for a product
    (and to generate an URL to fetch this OCR JSON from the server).

    :param code: the product barcode
    :param image_id: the image ID (ex: `1`, `ingredients_fr.full`,...)
    :return: the full image path
    """
    return _generate_file_path(code, image_id, ".json")


def generate_json_ocr_url(
    code: str,
    image_id: str,
    flavor: Flavor = Flavor.off,
    environment: Environment = Environment.org,
) -> str:
    """Generate the OCR JSON URL for a specific product and
    image ID.

    :param code: the product barcode
    :param image_id: the image ID (ex: `1`, `2`,...)
    :param flavor: the project to use, defaults to Flavor.off
    :param environment: the environment (prod/staging), defaults to
        Environment.org
    :return: the generated JSON URL
    """
    return URLBuilder.image_url(
        flavor, environment, generate_json_ocr_path(code, image_id)
    )


def generate_image_url(
    code: str,
    image_id: str,
    flavor: Flavor = Flavor.off,
    environment: Environment = Environment.org,
) -> str:
    """Generate the image URL for a specific product and
    image ID.

    :param code: the product barcode
    :param image_id: the image ID (ex: `1`, `ingredients_fr.full`,...)
    :param flavor: the project to use, defaults to Flavor.off
    :param environment: the environment (prod/staging), defaults to
        Environment.org
    :return: the generated image URL
    """
    return URLBuilder.image_url(
        flavor, environment, generate_image_path(code, image_id)
    )


def extract_barcode_from_url(url: str) -> Optional[str]:
    """Extract a product barcode from an image/OCR URL.

    :param url: the URL
    :return: the extracted barcode
    """
    url_path = urlparse(url).path
    return extract_barcode_from_path(url_path)


def extract_barcode_from_path(path: str) -> Optional[str]:
    """Extract a product barcode from an image/OCR path.

    The barcode is normalized using the following rules:

    - all leading zeros are stripped
    - if the barcode is less than 8 digits, it is left-padded with zeros up to
      8 digits
    - if the barcode is more than 8 digits but less than 13 digits, it is
      left-padded with zeros up to 13 digits
    - if the barcode has 13 digits or more, it's returned as it
    """
    barcode = ""

    for parent in Path(path).parents:
        if parent.name.isdigit():
            barcode = parent.name + barcode
        else:
            break

    # Strip leading zeros
    barcode = barcode.lstrip("0")

    if not barcode:
        return None

    if len(barcode) <= 8:
        barcode = barcode.zfill(8)
        return barcode

    barcode = barcode.zfill(13)
    return barcode


def extract_source_from_url(url: str) -> str:
    """Extract source image from an image or OCR URL.

    The source image is a unique identifier of the image or OCR,
    and is the full path of the image or OCR file on the server
    (ex: `/008/009/637/2472/1.jpg`).

    :param url: the URL
    :return: the source image
    """
    url_path = urlparse(url).path

    if url_path.startswith("/images/products"):
        url_path = url_path[len("/images/products") :]

    if url_path.endswith(".json"):
        url_path = str(Path(url_path).with_suffix(".jpg"))

    # normalize windows path to unix path
    return url_path.replace("\\", "/")


def download_image(
    image: Union[str, Tuple[str, str]],
    use_cache: bool = True,
    error_raise: bool = True,
    session: Optional[requests.Session] = None,
    return_struct: bool = False,
) -> Union[None, "Image.Image", ImageDownloadItem]:
    """Download an Open Food Facts image.

    :param image: the image URL or a tuple containing the barcode and the
        image ID
    :param use_cache: whether to use the S3 dataset cache, defaults to True
    :param error_raise: whether to raise an error if the download fails,
        defaults to True
    :param session: the requests session to use, defaults to None
    :param return_struct: if True, return a `ImageDownloadItem` object
        containing the image, image bytes and the response object.
    :return: the downloaded image, or an `ImageDownloadItem` object if
        `return_struct` is True.

    >>> download_image("https://images.openfoodfacts.org/images/products/324/227/210/2359/4.jpg")  # noqa
    <PIL.JpegImagePlugin.JpegImageFile image mode=RGB size=1244x1500>

    >>> download_image(("3242272102359", "4"))
    <PIL.JpegImagePlugin.JpegImageFile image mode=RGB size=1244x1500>
    """
    if not _pillow_available:
        raise ImportError("Pillow is required to use this function")

    if isinstance(image, str):
        if use_cache:
            image_path = extract_source_from_url(image)
            image_url = f"{AWS_S3_BASE_URL}{image_path}"

            if requests.head(image_url).status_code != 200:
                logger.debug(f"Image not found in cache: {image_url}")
                image_url = image
        else:
            image_url = image

    if isinstance(image, tuple):
        if use_cache:
            image_path = generate_image_path(*image)
            image_url = f"{AWS_S3_BASE_URL}{image_path}"

            if requests.head(image_url).status_code != 200:
                logger.debug(f"Image not found in cache: {image_url}")
                image_url = generate_image_url(*image)
        else:
            image_url = generate_image_url(*image)

    logger.debug(f"Downloading image from {image_url}")
    return get_image_from_url(
        image_url,
        error_raise=error_raise,
        session=session,
        return_struct=return_struct,
    )


def convert_to_legacy_schema(images: JSONType) -> JSONType:
    """Convert the images dictionary to the legacy schema.

    We've improved the schema of the `images` field, but the new
    schema is not compatible with the legacy schema. This function
    converts the new schema to the legacy schema.

    It can be used while migrating the existing Python codebase to the
    new schema.

    The new `images` schema is the following:

    - the `images` field contains the uploaded images under the `uploaded`
        key and the selected images under the `selected` key
    - `uploaded` contains the images that are uploaded, and maps the
        image ID to the detail about the image:
        - `uploaded_t`: the upload timestamp
        - `uploader`: the username of the uploader
        - `sizes`: dictionary mapping image size (`100`, `200`, `400`, `full`)
            to the information about each resized image:
            - `h`: the height of the image
            - `w`: the width of the image
            - `url`: the URL of the image
    - `selected` contains the images that are selected, and maps the
        image key (`nutrition`, `ingredients`, `packaging`, or `front`) to
        a dictionary mapping the language to the selected image details.
        The selected image details are the following fields:
        - `imgid`: the image ID
        - `rev`: the revision ID
        - `sizes`: dictionary mapping image size (`100`, `200`, `400`, `full`)
            to the information about each resized image:
            - `h`: the height of the image
            - `w`: the width of the image
            - `url`: the URL of the image
        - `generation`: information about how to generate the selected image
            from the uploaded image:
            - `geometry`
            - `x1`, `y1`, `x2`, `y2`: the coordinates of the crop
            - `angle`: the rotation angle of the selected image
            - `coordinates_image_size`: 400 or "full", indicates if the
                geometry coordinates are relative to the full image, or to a
                resized version (max width and max height=400)
            - `normalize`: indicates if colors should be normalized
            - `white_magic`: indicates if the background is white and should
                be removed (e.g. photo on a white sheet of paper)

    See https://github.com/openfoodfacts/openfoodfacts-server/pull/11818
    for more details.
    """

    if not is_new_image_schema(images):
        return images

    images_with_legacy_schema = {}

    for image_id, image_data in images.get("uploaded", {}).items():
        images_with_legacy_schema[image_id] = {
            "sizes": {
                # remove URL field
                size: {k: v for k, v in image_size_data.items() if k != "url"}
                for size, image_size_data in image_data["sizes"].items()
            },
            "uploaded_t": image_data["uploaded_t"],
            "uploader": image_data["uploader"],
        }

    for selected_key, image_by_lang in images.get("selected", {}).items():
        for lang, image_data in image_by_lang.items():
            new_image_data = {
                "imgid": image_data["imgid"],
                "rev": image_data["rev"],
                "sizes": {
                    # remove URL field
                    size: {k: v for k, v in image_size_data.items() if k != "url"}
                    for size, image_size_data in image_data["sizes"].items()
                },
                **(image_data.get("generation", {})),
            }
            images_with_legacy_schema[f"{selected_key}_{lang}"] = new_image_data

    return images_with_legacy_schema


def is_new_image_schema(images_data: JSONType) -> bool:
    """Return True if the `images` dictionary follows the new Product Opener
    images schema.

    See https://github.com/openfoodfacts/openfoodfacts-server/pull/11818 for
    more information about this new schema.
    """
    if not images_data:
        return False

    return "selected" in images_data or "uploaded" in images_data
