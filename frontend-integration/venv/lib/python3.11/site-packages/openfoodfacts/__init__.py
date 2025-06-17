from openfoodfacts.barcode import normalize_barcode

from .api import API
from .dataset import ProductDataset, get_dataset
from .ocr import OCRResult
from .types import (
    APIConfig,
    APIVersion,
    Country,
    DatasetType,
    Environment,
    Facet,
    Flavor,
    Lang,
)

__all__ = [
    "API",
    "APIConfig",
    "APIVersion",
    "Country",
    "DatasetType",
    "Facet",
    "Flavor",
    "Environment",
    "Lang",
    "OCRResult",
    "ProductDataset",
    "get_dataset",
    "normalize_barcode",
]

__version__ = "2.6.1"
