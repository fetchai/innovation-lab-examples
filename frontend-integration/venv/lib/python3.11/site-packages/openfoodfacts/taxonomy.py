from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Union

import requests

from openfoodfacts.utils.text import get_tag, replace_lang_prefix

from .types import Environment, Flavor, JSONType, TaxonomyType
from .utils import (
    URLBuilder,
    download_file,
    get_logger,
    http_session,
    load_json,
    should_download_file,
)

logger = get_logger(__name__)


DEFAULT_CACHE_DIR = Path("~/.cache/openfoodfacts/taxonomy").expanduser()


# Only available for Open Food Facts for now (not other flavors)
TAXONOMY_URLS = {
    TaxonomyType.category: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/categories.full.json",
    TaxonomyType.ingredient: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/ingredients.full.json",
    TaxonomyType.label: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/labels.full.json",
    TaxonomyType.brand: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/brands.full.json",
    TaxonomyType.packaging_shape: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/packaging_shapes.full.json",
    TaxonomyType.packaging_material: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/packaging_materials.full.json",
    TaxonomyType.packaging_recycling: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/packaging_recycling.full.json",
    TaxonomyType.country: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/countries.full.json",
    TaxonomyType.additive: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/additives.full.json",
    TaxonomyType.vitamin: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/vitamins.full.json",
    TaxonomyType.mineral: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/minerals.full.json",
    TaxonomyType.amino_acid: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/amino_acids.full.json",
    TaxonomyType.nucleotide: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/nucleotides.full.json",
    TaxonomyType.allergen: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/allergens.full.json",
    TaxonomyType.state: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/states.full.json",
    TaxonomyType.origin: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/origins.full.json",
    TaxonomyType.language: URLBuilder.static(Flavor.off, Environment.org)
    + "/data/taxonomies/languages.full.json",
    TaxonomyType.other_nutritional_substance: URLBuilder.static(
        Flavor.off, Environment.org
    )
    + "/data/taxonomies/other_nutritional_substances.full.json",
}


class TaxonomyNode:
    """A taxonomy element.

    Each node has 0+ parents and 0+ children. Each node has the following
    attributes:

    - `id`: the node identifier, it starts with a language prefix (ex: `en:`)
    - `names`: a dict mapping language 2-letter code to the node name for this
      language
    - `parents`: the list of the node parents
    - `children`: the list of the node children
    - `properties`: additional properties of the node (taxonomy-dependent)
    - `synonyms`: a dict mapping language 2-letter code to a list of synonyms
      for this language
    """

    __slots__ = ("id", "names", "parents", "children", "synonyms", "properties")

    def __init__(
        self,
        identifier: str,
        names: Dict[str, str],
        synonyms: Optional[Dict[str, List[str]]],
        properties: Optional[Dict[str, Any]] = None,
    ):
        self.id: str = identifier
        self.names: Dict[str, str] = names
        self.parents: List["TaxonomyNode"] = []
        self.children: List["TaxonomyNode"] = []
        self.properties = properties or {}

        if synonyms:
            self.synonyms = synonyms
        else:
            self.synonyms = {}

    def is_child_of(self, item: "TaxonomyNode") -> bool:
        """Return True if `item` is a child of `self` in the taxonomy."""
        if not self.parents:
            return False

        if item in self.parents:
            return True

        for parent in self.parents:
            is_parent = parent.is_child_of(item)

            if is_parent:
                return True

        return False

    def is_parent_of(self, candidate: "TaxonomyNode") -> bool:
        """Return True if `self` is parent of `candidate`, False otherwise.

        :param candidate: a TaxonomyNode of the same Taxonomy
        """
        return candidate.is_child_of(self)

    def is_parent_of_any(self, candidates: Iterable["TaxonomyNode"]) -> bool:
        """Return True if `self` is a parent of any of `candidates`, False
        otherwise.

        :param candidates: an iterable of TaxonomyNodes of the same Taxonomy
        """
        for candidate in candidates:
            if candidate.is_child_of(self):
                return True

        return False

    def get_parents_hierarchy(self) -> List["TaxonomyNode"]:
        """Return the list of all parent nodes (direct and indirect)."""
        all_parents = []
        seen: Set[str] = set()

        if not self.parents:
            return []

        for self_parent in self.parents:
            if self_parent.id not in seen:
                all_parents.append(self_parent)
                seen.add(self_parent.id)

            for parent_parent in self_parent.get_parents_hierarchy():
                if parent_parent.id not in seen:
                    all_parents.append(parent_parent)
                    seen.add(parent_parent.id)

        return all_parents

    def get_localized_name(self, lang: str) -> str:
        """Return the localized name of the node.

        We first check if there is an entry in `names` under the provided
        `lang`. Otherwise, we check the existence of an international name
        (`xx`). We eventually return the node ID if none of the previous
        checks were successful.

        :param lang: the language code
        """
        if lang in self.names:
            return self.names[lang]

        if "xx" in self.names:
            # Return international name if it exists
            return self.names["xx"]

        return self.id

    def get_synonyms(self, lang: str) -> List[str]:
        return self.synonyms.get(lang, [])

    def add_parents(self, parents: Iterable["TaxonomyNode"]):
        for parent in parents:
            if parent not in self.parents:
                self.parents.append(parent)
                parent.children.append(self)

    def to_dict(self) -> JSONType:
        return {"name": self.names, "parents": [p.id for p in self.parents]}

    def __repr__(self):
        return "<TaxonomyNode %s>" % self.id


class Taxonomy:
    """A class representing a taxonomy.

    For more information about taxonomy, see
    https://wiki.openfoodfacts.org/Global_taxonomies.

    A Taxonomy instance has only a single `nodes` attribute, that maps the
    node identifier to a `TaxonomyNode`.
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, TaxonomyNode] = {}

    def add(self, key: str, node: TaxonomyNode) -> None:
        """Add a node to the taxonomy under the id `key`.

        :param key: The node id
        :param node: the TaxonomyNode
        """
        self.nodes[key] = node

    def __contains__(self, item: str):
        """Return True if `item` (a taxonomy id) is in the taxonomy, False
        otherwise."""
        return item in self.nodes

    def __getitem__(self, item: str):
        return self.nodes.get(item)

    def __len__(self) -> int:
        """Return the number of items in the taxonomy."""
        return len(self.nodes)

    def iter_nodes(self) -> Iterable[TaxonomyNode]:
        """Iterate over the nodes of the taxonomy."""
        return iter(self.nodes.values())

    def keys(self) -> Iterable[str]:
        """Return all node IDs from the taxonomy."""
        return self.nodes.keys()

    def find_deepest_nodes(self, nodes: List[TaxonomyNode]) -> List[TaxonomyNode]:
        """Given a list of nodes, returns the list of nodes where all the
        parents within the list have been removed.

        For example, for a taxonomy, 'fish' -> 'salmon' -> 'smoked-salmon':

        ['fish', 'salmon'] -> ['salmon'] ['fish', 'smoked-salmon'] ->
        [smoked-salmon']
        """
        excluded: Set[str] = set()

        for node in nodes:
            for second_node in (
                n for n in nodes if n.id not in excluded and n.id != node.id
            ):
                if node.is_child_of(second_node):
                    excluded.add(second_node.id)

        return [node for node in nodes if node.id not in excluded]

    def is_parent_of_any(
        self, item: str, candidates: Iterable[str], raises: bool = True
    ) -> bool:
        """Return True if `item` is parent of any candidate, False otherwise.

        If the item is not in the taxonomy and raises is False, return False.

        :param item: The item to compare
        :param candidates: A list of candidates
        :param raises: if True, raises a ValueError if item is not in the
        taxonomy, defaults to True.
        """
        node: TaxonomyNode = self[item]

        if node is None:
            if raises:
                raise ValueError("unknown id in taxonomy: %s", node)
            else:
                return False

        to_check_nodes: Set[TaxonomyNode] = set()

        for candidate in candidates:
            candidate_node = self[candidate]

            if candidate_node is not None:
                to_check_nodes.add(candidate_node)

        return node.is_parent_of_any(to_check_nodes)

    def get_localized_name(self, key: str, lang: str) -> str:
        """Return the name of a taxonomy element in a given language.

        If `key` is not in the taxonomy or if no name is available for the
        requested language, return `key`.

        :param key: the taxonomy element id
        :param lang: the 2-letter language code
        :return: the localized name
        """
        if key not in self.nodes:
            return key

        return self.nodes[key].get_localized_name(lang)

    def to_dict(self) -> JSONType:
        """Generate a dict from the Taxonomy."""
        export = {}

        for key, node in self.nodes.items():
            export[key] = node.to_dict()

        return export

    @classmethod
    def from_dict(cls, data: JSONType) -> "Taxonomy":
        """Create a Taxonomy from `data`.

        :param data: the taxonomy as a dict
        :return: a Taxonomy
        """
        taxonomy = Taxonomy()

        for key, key_data in data.items():
            if key not in taxonomy:
                node = TaxonomyNode(
                    identifier=key,
                    names=key_data.get("name", {}),
                    synonyms=key_data.get("synonyms", None),
                    properties={
                        k: v
                        for k, v in key_data.items()
                        if k not in {"parents", "name", "synonyms", "children"}
                    },
                )
                taxonomy.add(key, node)

        for key, key_data in data.items():
            node = taxonomy[key]
            parents = [taxonomy[ref] for ref in key_data.get("parents", [])]
            node.add_parents(parents)

        return taxonomy

    @classmethod
    def from_path(cls, file_path: Union[str, Path]) -> "Taxonomy":
        """Create a Taxonomy from a JSON file.

        :param file_path: a JSON file, gzipped (.json.gz) files are supported
        :return: a Taxonomy
        """
        return cls.from_dict(load_json(file_path))  # type: ignore

    @classmethod
    def from_url(
        cls, url: str, session: Optional[requests.Session] = None, timeout: int = 120
    ) -> "Taxonomy":
        """Create a Taxonomy from a taxonomy file hosted at `url`.

        :param url: the URL of the taxonomy
        :param session: the requests session, use a default session if None
        :param timeout: the request timeout, defaults to 120
        :return: a Taxonomy
        """
        session = http_session if session is None else session
        r = session.get(url, timeout=timeout)
        data = r.json()
        return cls.from_dict(data)

    @classmethod
    def from_type(cls, taxonomy_type: TaxonomyType) -> "Taxonomy":
        """Create a Taxonomy from a taxonomy file hosted online from a
        taxonomy type.

        :param taxonomy_type: the taxonomy type
        :return: a Taxonomy
        """
        url = TAXONOMY_URLS[TaxonomyType[taxonomy_type]]
        return cls.from_url(url)


def get_taxonomy(
    taxonomy_type: Union[TaxonomyType, str],
    force_download: bool = False,
    download_newer: bool = False,
    cache_dir: Optional[Path] = None,
) -> Taxonomy:
    """Return the taxonomy of the provided type.

    The taxonomy file is downloaded and cached locally.

    :param taxonomy_type: the requested taxonomy type
    :param force_download: if True, (re)download the taxonomy even if it was
        cached, defaults to False
    :param download_newer: if True, download the taxonomy if a more recent
        version compared to the cached version is available (based on file
        Etag). This parameter if ignored if force_download is True, defaults
        to False.
    :param cache_dir: the cache directory to use, defaults to
        ~/.cache/openfoodfacts/taxonomy
    :return: a Taxonomy
    """
    taxonomy_type = TaxonomyType[taxonomy_type]
    filename = f"{taxonomy_type.name}.json"

    cache_dir = DEFAULT_CACHE_DIR if cache_dir is None else cache_dir
    taxonomy_path = cache_dir / filename
    url = TAXONOMY_URLS[taxonomy_type]

    if not should_download_file(url, taxonomy_path, force_download, download_newer):
        return Taxonomy.from_path(taxonomy_path)

    cache_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading taxonomy, saving it in %s", taxonomy_path)
    download_file(url, taxonomy_path)
    return Taxonomy.from_path(taxonomy_path)


def create_taxonomy_mapping(taxonomy: Taxonomy) -> Dict[str, str]:
    """From a taxonomy, create a mapping of tags to taxonomy node ids.

    The mapping is created by iterating over the nodes of the taxonomy and
    creating a tag from the name and synonyms of each node.

    The taxonomy mapping has the following format:
    {
        "fr:noix": "en:nuts",
        "en:nuts": "en:nuts",
        ...
    }

    :param taxonomy: the taxonomy to use
    :return: a dict mapping tags (with language prefix) to taxonomy node ids
    """
    mapping = {}
    for node in taxonomy.iter_nodes():
        for lang, name in node.names.items():
            tag = get_tag(name)
            tag_id = f"{lang}:{tag}".lower()
            mapping[tag_id] = node.id

        for lang, synonyms in node.synonyms.items():
            for synonym in synonyms:
                tag = get_tag(synonym)
                tag_id = f"{lang}:{tag}".lower()
                mapping[tag_id] = node.id
    return mapping


def is_prefixed_value(value: str) -> bool:
    """Return True if the given value has a language prefix (en:, fr:,...),
    False otherwise."""
    return len(value) > 3 and value[2] == ":"


def create_brand_taxonomy_mapping(taxonomy: Taxonomy) -> Dict[str, str]:
    """From a brand taxonomy, create a mapping of tags to taxonomy brand names.

    The mapping generated is different than the mapping generated by the
    `create_taxonomy_mapping` function, as it maps an unprefixed value
    (ex: `nestle`) to a brand name, with capitalization and accents
    (ex: `Nestlé`).

    The taxonomy mapping has the following format:
    {
        "alva": "Alva",
        "benecop": "Bénécop",
        ...
    }

    :param taxonomy: the taxonomy to use (brand taxonomy)
    :return: a dict mapping tags (*without* language prefix) to brand values
        (capitalized)
    """
    mapping = {}
    for node in taxonomy.iter_nodes():
        unprefixed_key = node.id
        if is_prefixed_value(node.id):
            prefix = node.id[:2]
            unprefixed_key = node.id[3:]
        mapping[unprefixed_key] = node.names.get(
            "xx", node.names.get("en", node.names.get(prefix, unprefixed_key))
        )
    return mapping


def map_to_canonical_id(
    taxonomy_mapping: Dict[str, str], values: List[str]
) -> Dict[str, str]:
    """Map a list of values to their canonical taxonomy id.

    Each value should be a tag in the form `lang:tag`. If a value is not found
    in the taxonomy mapping, it is returned as is, in its tag form.

    :param taxonomy_mapping: a mapping of tags to taxonomy node ids, generated
        by `create_taxonomy_mapping`
    :param values: a list of string values
    :return: a dict mapping values to their canonical taxonomy id
    """
    for value in values:
        if len(value) < 3 or value[2] != ":":
            raise ValueError(
                f"Invalid value: '{value}', expected value to be in 'lang:tag' format"
            )

    output = {}
    for value in values:
        tag = get_tag(value)
        output[value] = (
            # Look for a direct match first
            taxonomy_mapping.get(tag)
            # Then look for a match with the xx prefix (language-independent
            # entry)
            or taxonomy_mapping.get(replace_lang_prefix(tag, "xx"))
            # If no match is found, return the original taggified value
            or tag
        )

    return output
