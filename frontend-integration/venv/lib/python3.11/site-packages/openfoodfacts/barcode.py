def normalize_barcode(barcode: str) -> str:
    """Normalize the barcode.

    First, we remove leading zeros, then we pad the barcode with zeros to
    reach 8 digits.

    If the barcode is longer than 8 digits, we pad it to 13 digits.

    :param barcode: the barcode to normalize
    :return: the normalized barcode
    """
    barcode = barcode.lstrip("0").zfill(8)

    if len(barcode) > 8:
        barcode = barcode.zfill(13)

    return barcode


def has_valid_check_digit(gtin: str) -> bool:
    """Check if the GTIN has a valid check-digit.

    The full GTIN (with the check-digit) is passed as an argument.
    The function returns True if the check-digit is valid, False otherwise.
    """
    if len(gtin) < 2:
        raise ValueError(f"invalid gtin: '{gtin}'")
    return calculate_check_digit(gtin) == gtin[-1]


def calculate_check_digit(gtin: str) -> str:
    """This function computes the check-digit from a raw GTIN.

    The full GTIN (with the check-digit) is passed as an argument.
    The computed check-digit is returned as a string.

    The check-digit is computed from the preceding digits by multiplying the
    sum of every 2nd digit *from right to left* by 3, adding that to the sum
    of all the other digits (1st, 3rd, etc.), modulating the result by 10
    (find the remainder after dividing by 10), and subtracting *that*
    result *from* 10.
    """
    # Remove the last digit (checksum)
    gtin = gtin[:-1]
    # Reverse the digits
    digits = tuple(d for d in reversed(gtin))
    return str(
        10
        - (  # From 10 we substract
            (
                (
                    sum(int(d) for d in digits[::2]) * 3
                )  # The sum of every 2nd digit, multiplied by 3
                + (
                    sum(int(d) for d in digits[1::2])
                )  # The sum of every 2nd digit, offset by 1
            )
            % 10  # Modulo 10 (the remainder after dividing by 10)
        )
    )[-1]
