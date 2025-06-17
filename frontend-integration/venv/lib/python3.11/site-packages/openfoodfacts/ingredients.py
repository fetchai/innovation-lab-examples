from openfoodfacts.taxonomy import Taxonomy
from openfoodfacts.types import JSONType


def add_ingredient_in_taxonomy_field(
    parsed_ingredients: list[JSONType], ingredient_taxonomy: Taxonomy
) -> tuple[int, int]:
    """Add the `in_taxonomy` field to each ingredient in `parsed_ingredients`.

    This function is called recursively to add the `in_taxonomy` field to each
    sub-ingredient. It returns the total number of ingredients and the number
    of known ingredients (including sub-ingredients).

    :param parsed_ingredients: a list of parsed ingredients, in Product Opener
        format
    :param ingredient_taxonomy: the ingredient taxonomy
    :return: a (total_ingredients_n, known_ingredients_n) tuple
    """
    ingredients_n = 0
    known_ingredients_n = 0
    for ingredient_data in parsed_ingredients:
        ingredient_id = ingredient_data["id"]
        in_taxonomy = ingredient_id in ingredient_taxonomy
        ingredient_data["in_taxonomy"] = in_taxonomy
        known_ingredients_n += int(in_taxonomy)
        ingredients_n += 1

        if "ingredients" in ingredient_data:
            (
                sub_ingredients_n,
                known_sub_ingredients_n,
            ) = add_ingredient_in_taxonomy_field(
                ingredient_data["ingredients"], ingredient_taxonomy
            )
            ingredients_n += sub_ingredients_n
            known_ingredients_n += known_sub_ingredients_n

    return ingredients_n, known_ingredients_n
