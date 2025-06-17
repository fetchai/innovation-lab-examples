import logging
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import requests

from .types import APIConfig, APIVersion, Country, Environment, Facet, Flavor, JSONType
from .utils import URLBuilder, http_session

logger = logging.getLogger(__name__)


def get_http_auth(environment: Environment) -> Optional[Tuple[str, str]]:
    return ("off", "off") if environment is Environment.net else None


def send_get_request(
    url: str,
    api_config: APIConfig,
    params: Optional[Dict[str, Any]] = None,
    return_none_on_404: bool = False,
    auth: Optional[Tuple[str, str]] = None,
) -> Optional[JSONType]:
    """Send a GET request to the given URL.

    :param url: the URL to send the request to
    :param api_config: the API configuration
    :param params: the query parameters, defaults to None
    :param return_none_on_404: if True, None is returned if the response
        status code is 404, defaults to False
    :return: the API response
    """
    r = http_session.get(
        url,
        params=params,
        headers={"User-Agent": api_config.user_agent},
        timeout=api_config.timeout,
        auth=auth,
    )
    if r.status_code == 404 and return_none_on_404:
        return None
    r.raise_for_status()
    return r.json()


def send_form_urlencoded_post_request(
    url: str, body: Dict[str, Any], api_config: APIConfig
) -> requests.Response:
    cookies = None
    if api_config.username and api_config.password:
        body["user_id"] = api_config.username
        body["password"] = api_config.password
    elif api_config.session_cookie:
        cookies = {
            "session": api_config.session_cookie,
        }
    r = http_session.post(
        url,
        data=body,
        headers={"User-Agent": api_config.user_agent},
        timeout=api_config.timeout,
        auth=get_http_auth(api_config.environment),
        cookies=cookies,
    )
    r.raise_for_status()
    return r


class RobotoffResource:
    def __init__(self, api_config: APIConfig):
        self.api_config = api_config
        self.base_url = URLBuilder.robotoff(environment=api_config.environment)

    def predict_lang(self, text: str, k: int = 10, threshold: float = 0.01) -> JSONType:
        """Predict the language of a text.

        :param text: the text to predict the language of
        :param k: the number of predictions to return, defaults to 10
        :param threshold: the minimum probability for a prediction to be
            returned, defaults to 0.01
        :return: the API response
        """
        return http_session.post(
            url=f"{self.base_url}/api/v1/predict/lang",
            data={"text": text, "k": k, "threshold": threshold},
        ).json()


class FacetResource:
    def __init__(self, api_config: APIConfig):
        self.api_config = api_config
        self.base_url = URLBuilder.country(
            self.api_config.flavor,
            environment=api_config.environment,
            country_code=self.api_config.country.name,
        )

    def get(self, facet_name: Union[Facet, str]) -> JSONType:
        facet = Facet.from_str_or_enum(facet_name)
        facet_plural = facet.value.replace("_", "-")
        resp = send_get_request(
            url=f"{self.base_url}/{facet_plural}",
            params={"json": "1"},
            api_config=self.api_config,
            auth=get_http_auth(self.api_config.environment),
        )
        resp = cast(JSONType, resp)
        return resp

    def get_products(
        self,
        facet_name: Union[Facet, str],
        facet_value: str,
        page: int = 1,
        page_size: int = 25,
        fields: Optional[List[str]] = None,
    ) -> JSONType:
        """Return products for a given facet value.

        :param facet_name: the facet name, e.g. "labels"
        :param facet_value: the facet value, e.g. "en:organic"
        :param page: the page number, defaults to 1
        :param page_size: the number of items per page, defaults to 25
        :param fields: a list of fields to return. If None, all fields are
            returned.
        :return: the API response
        """
        facet = Facet.from_str_or_enum(facet_name)
        facet_singular = facet.name.replace("_", "-")
        params: JSONType = {"page": page, "page_size": page_size}
        if fields is not None:
            params["fields"] = ",".join(fields)

        resp = send_get_request(
            url=f"{self.base_url}/{facet_singular}/{facet_value}.json",
            params=params,
            api_config=self.api_config,
            auth=get_http_auth(self.api_config.environment),
        )
        resp = cast(JSONType, resp)
        return resp


class ProductResource:
    def __init__(self, api_config: APIConfig):
        self.api_config = api_config
        self.base_url = URLBuilder.country(
            self.api_config.flavor,
            environment=api_config.environment,
            country_code=self.api_config.country.name,
        )

    def get(
        self,
        code: str,
        fields: Optional[List[str]] = None,
        raise_if_invalid: bool = False,
    ) -> Optional[JSONType]:
        """Return a product.

        If the product does not exist, None is returned.

        :param code: barcode of the product
        :param fields: a list of fields to return. If None, all fields are
            returned.
        :param raise_if_invalid: if True, a ValueError is raised if the
            barcode is invalid, defaults to False.
        :return: the API response
        """
        if len(code) == 0:
            raise ValueError("code must be a non-empty string")

        fields = fields or []
        url = f"{self.base_url}/api/{self.api_config.version.value}/product/{code}"

        if fields:
            # requests escape comma in URLs, as expected, but openfoodfacts
            # server does not recognize escaped commas.
            # See
            # https://github.com/openfoodfacts/openfoodfacts-server/issues/1607
            url += "?fields={}".format(",".join(fields))

        resp = send_get_request(
            url=url, api_config=self.api_config, return_none_on_404=True
        )

        if resp is None:
            # product not found
            return None

        if resp["status"] == 0:
            # invalid barcode
            if raise_if_invalid:
                raise ValueError(f"invalid barcode: {code}")
            return None

        return resp["product"] if resp is not None else None

    def text_search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
        sort_by: Optional[str] = None,
    ):
        """Search products using a textual query.

        :param query: the search query
        :param page: requested page (starts at 1), defaults to 1
        :param page_size: number of items per page, defaults to 20
        :param sort_by: result sorting key, defaults to None (no sorting)
        :return: the search results
        """
        # We force usage of v2 of API
        params = {
            "search_terms": query,
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "json": "1",
        }

        if sort_by is not None:
            params["sort_by"] = sort_by

        return send_get_request(
            url=f"{self.base_url}/cgi/search.pl",
            api_config=self.api_config,
            params=params,
            auth=get_http_auth(self.api_config.environment),
        )

    def update(self, body: Dict[str, Any]):
        """Create a new product or update an existing one."""
        if not body.get("code"):
            raise ValueError("missing code from body")

        url = f"{self.base_url}/cgi/product_jqm2.pl"
        return send_form_urlencoded_post_request(url, body, self.api_config)

    def select_image(
        self,
        code: str,
        image_id: str,
        image_key: str,
        rotate: Optional[int] = None,
        crop_bounding_box: Optional[tuple[float, float, float, float]] = None,
    ):
        """Select an image (front/ingredients/nutrition/packaging) for a
        product.

        It's possible to rotate and crop the selection.

        :param code: the product barcode
        :param image_id: the raw image ID, it must be a digit (ex: 1, 2, 3, 4)
        :param image_key: the image field name (one of `front`, `ingredients`,
            `nutrition`, `packaging`) and the language code, separated by a
            `_`. Example: `front_fr`, `ingredients_en`, `nutrition_es`, etc.
        :param rotate: rotation angle in degrees (90, 180, 270), defaults to
            None (no rotation)
        :param crop_bounding_box: a tuple of 4 floats
            (y_min, x_min, y_max, x_max) that defines the bounding box of the
            crop, defaults to None (no crop)
        :raises ValueError: if the rotation angle is invalid or if no password
            or session cookie is provided
        :return: the API response
        """
        url = f"{self.base_url}/cgi/product_image_crop.pl"
        params: JSONType = {
            "code": code,
            "imgid": image_id,
            # We need to tell Product Opener that the bounding box coordinates
            # are related to the full image
            "coordinates_image_size": "full",
        }

        if rotate is not None and rotate != 0:
            if rotate not in (90, 180, 270):
                raise ValueError(f"invalid value for rotation angle: {rotate}")
            params["angle"] = str(rotate)

        if crop_bounding_box is not None:
            y_min, x_min, y_max, x_max = crop_bounding_box
            params["x1"] = x_min
            params["y1"] = y_min
            params["x2"] = x_max
            params["y2"] = y_max

        if image_key is not None:
            params["id"] = image_key

        cookies = None
        if self.api_config.session_cookie:
            cookies = {
                "session": self.api_config.session_cookie,
            }
        elif self.api_config.username:
            params["user_id"] = self.api_config.username
            params["password"] = self.api_config.password

        if cookies is None and not params.get("password"):
            raise ValueError(
                "a password or a session cookie is required to select an image"
            )

        r = http_session.post(
            url,
            data=params,
            headers={"User-Agent": self.api_config.user_agent},
            timeout=self.api_config.timeout,
            auth=get_http_auth(self.api_config.environment),
            cookies=cookies,
        )

        r.raise_for_status()
        return r

    def parse_ingredients(
        self, text: str, lang: str, timeout: int = 10
    ) -> list[JSONType]:
        """Parse ingredients text using Product Opener API.

        It is only available for `off` flavor (food).

        The result is a list of ingredients, each ingredient is a dict with the
        following keys:

        - id: the ingredient ID. Having an ID does not means that the
            ingredient is recognized, you must check if it exists in the
            taxonomy.
        - text: the ingredient text (as it appears in the input ingredients
            list)
        - percent_min: the minimum percentage of the ingredient in the product
        - percent_max: the maximum percentage of the ingredient in the product
        - percent_estimate: the estimated percentage of the ingredient in the
            product
        - vegan (bool): optional key indicating if the ingredient is vegan
        - vegetarian (bool): optional key indicating if the ingredient is
            vegetarian

        :param server_type: the server type (project) to use
        :param text: the ingredients text to parse
        :param lang: the language of the text (used for parsing) as a 2-letter
            code
        :param timeout: the request timeout in seconds, defaults to 10s
        :raises RuntimeError: a RuntimeError is raised if the parsing fails
        :return: the list of parsed ingredients
        """
        if self.api_config.flavor != Flavor.off:
            raise ValueError("ingredient parsing is only available for food")

        if self.api_config.version != APIVersion.v3:
            logger.warning(
                "ingredient parsing is only available in v3 of the API (here: %s), using v3",
                self.api_config.version,
            )
        # by using "test" as code, we don't save any information to database
        # This endpoint is specifically designed for testing purposes
        url = f"{self.base_url}/api/v3/product/test"

        if len(text) == 0:
            raise ValueError("text must be a non-empty string")

        try:
            r = http_session.patch(
                url,
                auth=get_http_auth(self.api_config.environment),
                json={
                    "fields": "ingredients",
                    "lc": lang,
                    "tags_lc": lang,
                    "product": {
                        "lang": lang,
                        f"ingredients_text_{lang}": text,
                    },
                },
                timeout=timeout,
            )
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.SSLError,
            requests.exceptions.Timeout,
        ) as e:
            raise RuntimeError(
                f"Unable to parse ingredients: error during HTTP request: {e}"
            )

        if not r.ok:
            raise RuntimeError(
                f"Unable to parse ingredients (non-200 status code): {r.status_code}, {r.text}"
            )

        response_data = r.json()

        if response_data.get("status") != "success":
            raise RuntimeError(f"Unable to parse ingredients: {response_data}")

        return response_data["product"].get("ingredients", [])


class API:
    def __init__(
        self,
        user_agent: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        country: Union[Country, str] = Country.world,
        flavor: Union[Flavor, str] = Flavor.off,
        version: Union[APIVersion, str] = APIVersion.v2,
        environment: Union[Environment, str] = Environment.org,
        session_cookie: Optional[str] = None,
        timeout: int = 10,
    ) -> None:
        """Initialize the API instance.

        :param user_agent: the user agent to use for HTTP requests, this is
            mandatory. Give a meaningful user agent that describes your
            app/script.
        :param username: user username, only used for write requests, defaults
            to None
        :param password: user password, only used for write requests, defaults
            to None
        :param country: the country, has an effect on the default display
            language and when uploading products, defaults to Country.world
        :param flavor: which O*F project to use, defaults to Flavor.off (Open
            Food Facts)
        :param version: the API version to use, defaults to APIVersion.v2
        :param environment: what environment (prod/staging) to use, defaults
            to Environment.org
        :param session_cookie: a session cookie, only used for write requests,
            defaults to None
        :param timeout: the timeout for HTTP requests, defaults to 10 seconds
        """
        if not isinstance(country, Country):
            country = Country[country]

        self.api_config = APIConfig(
            user_agent=user_agent,
            country=country,
            flavor=Flavor[flavor],
            version=APIVersion[version],
            environment=Environment[environment],
            username=username,
            password=password,
            session_cookie=session_cookie,
            timeout=timeout,
        )
        self.password = password
        self.country = country
        self.product = ProductResource(self.api_config)
        self.facet = FacetResource(self.api_config)
        self.robotoff = RobotoffResource(self.api_config)


def parse_ingredients(text: str, lang: str, api_config: APIConfig) -> list[JSONType]:
    """Parse ingredients text using Product Opener API.

    It is only available for `off` flavor (food).

    The result is a list of ingredients, each ingredient is a dict with the
    following keys:

    - id: the ingredient ID. Having an ID does not means that the ingredient
        is recognized, you must check if it exists in the taxonomy.
    - text: the ingredient text (as it appears in the input ingredients list)
    - percent_min: the minimum percentage of the ingredient in the product
    - percent_max: the maximum percentage of the ingredient in the product
    - percent_estimate: the estimated percentage of the ingredient in the
        product
    - vegan (bool): optional key indicating if the ingredient is vegan
    - vegetarian (bool): optional key indicating if the ingredient is
        vegetarian


    :param text: the ingredients text to parse
    :param lang: the language of the text (used for parsing) as a 2-letter code
    :param api_config: the API configuration
    :raises RuntimeError: a RuntimeError is raised if the parsing fails
    :return: the list of parsed ingredients
    """
    base_url = URLBuilder.country(
        Flavor.off,
        environment=api_config.environment,
        country_code=api_config.country.name,
    )
    # by using "test" as code, we don't save any information to database
    # This endpoint is specifically designed for testing purposes
    url = f"{base_url}/api/v3/product/test"

    if len(text) == 0:
        raise ValueError("text must be a non-empty string")

    try:
        r = http_session.patch(
            url,
            auth=get_http_auth(api_config.environment),
            json={
                "fields": "ingredients",
                "lc": lang,
                "tags_lc": lang,
                "product": {
                    "lang": lang,
                    f"ingredients_text_{lang}": text,
                },
            },
            timeout=api_config.timeout,
        )
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.SSLError,
        requests.exceptions.Timeout,
    ) as e:
        raise RuntimeError(
            f"Unable to parse ingredients: error during HTTP request: {e}"
        )

    if not r.ok:
        raise RuntimeError(
            f"Unable to parse ingredients (non-200 status code): {r.status_code}, {r.text}"
        )

    response_data = r.json()

    if response_data.get("status") != "success":
        raise RuntimeError(f"Unable to parse ingredients: {response_data}")

    return response_data["product"]["ingredients"]
