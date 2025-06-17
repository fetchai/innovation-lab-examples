import numpy as np
from PIL import Image


def convert_image_to_array(image: Image.Image) -> np.ndarray:
    """Convert a PIL Image into a numpy array.

    The image is converted to RGB if needed before generating the array.

    :param image: the input image.
    :return: the generated numpy array of shape (width, height, 3)
    """
    if image.mode != "RGB":
        image = image.convert("RGB")

    (im_width, im_height) = image.size

    return np.array(image.getdata(), dtype=np.uint8).reshape((im_height, im_width, 3))


def resize_image(image: Image.Image, max_size: tuple[int, int]) -> Image.Image:
    """Resize an image to fit within the specified dimensions.

    :param image: the input image
    :param max_size: the maximum width and height as a tuple
    :return: the resized image, or the original image if it fits within the
        specified dimensions
    """
    width, height = image.size
    max_width, max_height = max_size

    if width > max_width or height > max_height:
        new_image = image.copy()
        new_image.thumbnail((max_width, max_height))
        return new_image

    return image
