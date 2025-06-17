# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2018-2021 Fetch.AI Limited
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""Cosmpy aerial module."""


def cast_to_int(value: str, verify_decimal_part: bool = True, base: int = 10) -> int:
    """Casts string representing a number to python native integer type.

    :param value: The string representation of a number. The string value can represent
        a number in fixed point format (e.g. "1.234" or "0.000456", however, the scientific
        floating point format with "e" or "E" (e.g. "1.234e2" or "7.841E-10") is **NOT** supported.
    :param verify_decimal_part: If true, the function will verify whether part of the number *AFTER*
        the point is valid (= whether it is convertible to an integer using the given
        `base` value.
        For example, if the `value` is "123.456789" and `base` is 10, then the
        function will verify whether the "456789" string is convertible to
        integer using in base 10 numeric system.
    :param base: The number represents the base of the `value` numeric system.
        For example, the binary system will have base=2, the decimal system will have base=10,
        the hexadecimal system will have base=16.
    :return: The integer representation of the value number.

    :raises ValueError: If `value` is not a valid number.
    """
    parts = value.split(".")
    len_parts = len(parts)

    if not 0 < len_parts < 3:
        raise ValueError(
            f'invalid string literal for casting to int with base {base}: "{value}"'
        )

    if verify_decimal_part and len_parts > 1:
        # Verify convertibility of the number *behind* the decimal point
        _ = int(parts[1], base)

    integral_part_str = parts[0]

    if integral_part_str == "":
        return 0

    return int(integral_part_str, base)
