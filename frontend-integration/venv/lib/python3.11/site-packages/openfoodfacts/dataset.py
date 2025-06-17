import csv
from pathlib import Path
from typing import Optional

from .types import DatasetType, Environment, Flavor
from .utils import (
    URLBuilder,
    download_file,
    get_logger,
    get_open_fn,
    jsonl_iter,
    should_download_file,
)

logger = get_logger(__name__)

# Increase field_size to accommodate large fields.
# sys.maxsize will overflow on windows so using max 32-bit integer instead.
csv.field_size_limit(pow(2, 31) - 1)


DEFAULT_CACHE_DIR = Path("~/.cache/openfoodfacts/datasets").expanduser()
DATASET_FILE_NAMES = {
    Flavor.off: {
        DatasetType.jsonl: "openfoodfacts-products.jsonl.gz",
        DatasetType.csv: "en.openfoodfacts.org.products.csv.gz",
    },
    Flavor.obf: {
        DatasetType.jsonl: "openbeautyfacts-products.jsonl.gz",
        DatasetType.csv: "en.openbeautyfacts.org.products.csv",
    },
    Flavor.opff: {
        DatasetType.jsonl: "openpetfoodfacts-products.jsonl.gz",
        DatasetType.csv: "en.openpetfoodfacts.org.products.csv",
    },
    Flavor.opf: {
        DatasetType.jsonl: "openproductsfacts-products.jsonl.gz",
        DatasetType.csv: "en.openproductsfacts.org.products.csv",
    },
}


def get_dataset(
    flavor: Flavor = Flavor.off,
    dataset_type: DatasetType = DatasetType.jsonl,
    force_download: bool = False,
    download_newer: bool = False,
    cache_dir: Optional[Path] = None,
    obsolete: bool = False,
) -> Path:
    """Download (and cache) Open Food Facts dataset.

    The dataset is downloaded the first time and subsequently cached in
    `~/.cache/openfoodfacts/datasets`.

    :param flavor: The data source, defaults to Flavor.off
    :param dataset_type: The returned format, defaults to DatasetType.jsonl
    :param force_download: if True, (re)download the dataset even if it was
        cached, defaults to False
    :param download_newer: if True, download the dataset if a more recent
        version compared to the cached version is available (based on file
        Etag). This parameter if ignored if force_download is True, defaults
        to False.
    :param cache_dir: the cache directory to use, defaults to
        ~/.cache/openfoodfacts/taxonomy
    :param obsolete: if True, download the obsolete dataset, defaults to False
    :return: the path of the dataset
    """
    cache_dir = DEFAULT_CACHE_DIR if cache_dir is None else cache_dir
    file_name = DATASET_FILE_NAMES[flavor][dataset_type]
    if obsolete:
        file_name = file_name.replace(".jsonl.gz", "_obsolete.jsonl.gz")
    dataset_path = cache_dir / file_name
    url = f"{URLBuilder.static(flavor, Environment.org)}/data/{file_name}"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not should_download_file(url, dataset_path, force_download, download_newer):
        return dataset_path

    logger.info("Downloading dataset, saving it in %s", dataset_path)
    download_file(url, dataset_path)
    return dataset_path


class ProductDataset:
    def __init__(
        self,
        flavor: Flavor = Flavor.off,
        dataset_type: DatasetType = DatasetType.jsonl,
        dataset_path: Optional[Path] = None,
        obsolete: bool = False,
        **kwargs,
    ):
        """A product dataset.

        This class is used to iterate over the Open Food Facts dataset and
        to retrieve the information about products as dict.

        If dataset_path is None (default), the dataset is downloaded and
        cached in `~/.cache/openfoodfacts/datasets`.

        Otherwise, the dataset is loaded from the provided path.

        :param flavor: the dataset flavor to use (off, obf, opff or opf),
            defaults to Flavor.off. This parameter is ignored if dataset_path
            is provided.
        :param dataset_type: the dataset type to use (csv or jsonl), defaults
            to DatasetType.jsonl. This parameter is ignored if dataset_path is
            provided.
        :param dataset_path: the path of the dataset, defaults to None.
        :param obsolete: if True, download the obsolete dataset, defaults to
            False.
        :param kwargs: additional arguments passed to `get_dataset` when
            downloading the dataset
        """
        self.dataset_type = dataset_type

        if dataset_path is not None:
            self.dataset_path = dataset_path

            # We infer the dataset type from the file extension
            full_suffix = "".join(dataset_path.suffixes)
            if full_suffix in (".jsonl.gz", ".jsonl"):
                self.dataset_type = DatasetType.jsonl
            elif full_suffix in (".csv.gz", ".csv"):
                self.dataset_type = DatasetType.csv
            else:
                raise ValueError(f"Unknown dataset type: {full_suffix}")
        else:
            self.dataset_path = get_dataset(
                flavor, dataset_type, obsolete=obsolete, **kwargs
            )

    def __iter__(self):
        if self.dataset_type is DatasetType.jsonl:
            return jsonl_iter(self.dataset_path)
        else:
            return self._csv_iterator()

    def _csv_iterator(self):
        open_fn = get_open_fn(self.dataset_path)
        with open_fn(self.dataset_path, "rt", newline="") as csvfile:
            reader = csv.DictReader(csvfile, delimiter="\t")
            for row in reader:
                yield dict(row)

    def count(self) -> int:
        """Return the number of products in the dataset."""
        count = 0
        for _ in self:
            count += 1
        return count
