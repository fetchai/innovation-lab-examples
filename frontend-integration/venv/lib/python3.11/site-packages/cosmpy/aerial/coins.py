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

"""Parse the coins."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Optional, Union

from sortedcontainers import SortedDict

from cosmpy.protos.cosmos.base.v1beta1.coin_pb2 import Coin as CoinProto


denom_regex = re.compile("^[a-zA-Z][a-zA-Z0-9/-]{2,127}$")


@dataclass
class Coin:
    """Coins.

    This class does not implicitly ensure that its value represents a valid coin based on Cosmos-SDK requirements.
    This is by design to enable operations with the coin instance which might need to pass Coin instance as
    by-reference and change coin value the way which will make it invalid from Cosmos-SDK requirements perspective.
    For example, mathematical calculations/operations which might need to use Coin to store a relative rather than
    an absolute amount value, what might result in to negative coin amount value.
    This is to enable flexibility, rather than fail immediately when setting amount or denom values

    The implication is that the validation needs to be executed explicitly by calling the `validate()` method.
    """

    amount: int
    denom: str

    def __repr__(self) -> str:
        """Return Cosmos-SDK string representation of the coin this (self) instance holds."""
        return f"{self.amount}{self.denom}"

    def to_proto(self) -> CoinProto:
        """Convert this type to protobuf schema Coin type."""
        return CoinProto(amount=str(self.amount), denom=self.denom)

    def validate(self):
        """Validate Coin instance based on Cosmos-SDK requirements.

        Throws ValueError exception if coin instance is invalid based on Cosmos-SDK requirements.
        """
        self.validate_amount()
        self.validate_denom()

    def validate_amount(self):
        """Validate coin amount value based on Cosmos-SDK requirements.

        :raises ValueError: If coin amount value does not conform to cosmos-sdk requirement.
        """
        if not self.is_amount_valid():
            raise ValueError(f"Coin amount {self.amount} must be greater than zero")

    def validate_denom(self):
        """Validate coin denom value based on Cosmos-SDK requirements.

        :raises ValueError: If coin denom value does not conform to cosmos-sdk requirement.
        """
        if not self.is_denom_valid():
            raise ValueError(
                f'Coin denom "{self.denom}" does not conform to Cosmos-SDK requirements.'
            )

    def is_valid(self) -> bool:
        """Validate Coin instance based on Cosmos-SDK requirements.

        :return: True if the Coin instance conforms to cosmos-sdk requirement for Coin, False otherwise.
        """
        return self.is_amount_valid() and self.is_denom_valid()

    def is_amount_valid(self) -> bool:
        """Validate amount value based on Cosmos-SDK requirements.

        :return: True if the amount conforms to cosmos-sdk requirement for Coin amount (when it is greater than
                 or equal to zero). False otherwise.
        """
        return is_coin_amount_valid(self.amount)

    def is_denom_valid(self) -> bool:
        """Validate denom value based on Cosmos-SDK requirements.

        :return: True if denom conforms to cosmos-sdk requirement for denomination, False otherwise.
        """
        return is_denom_valid(self.denom)


CoinsParamType = Union[
    str, "Coins", Iterable[Coin], Iterable[CoinProto], Coin, CoinProto
]


class OnCollision(Enum):
    """OnCollision Enum."""

    Fail = 0
    Override = 1


class Coins:
    """This class implements the behaviour of Coins as defined by Cosmos-SDK.

    Implementation of this class guarantees, that the value it represents/holds is *always* valid (= conforms to
    Cosmos-SDK requirements), and all its methods ensure that the value always remains valid, or they fail with
    an exception.
    """

    def __init__(
        self,
        coins: Optional[CoinsParamType] = None,
    ):
        """Instantiate Coins from any of the supported coin(s) representation types."""
        self._amounts: SortedDict[str, int] = SortedDict()
        self.assign(coins)

    def __repr__(self) -> str:
        """Return cosmos-sdk string representation of Coins.

        :return: cosmos-sdk formatted string representation of Coins.

        Example::
        from cosmpy.aerial.client.coins import Coin, Coins

        coins = Coins([Coin(1,"afet"), Coin(2,"uatom"), Coin(3,"nanomobx")])
        assert repr(coins) == "1afet,2uatom,3nanomobx"
        assert str(coins) == repr(coins)
        """
        return ",".join([repr(c) for c in self])

    def __hash__(self) -> int:
        """Hash."""
        return hash(self._amounts)

    def __len__(self) -> int:
        """Get number of coins."""
        return len(self._amounts)

    def __eq__(self, right) -> bool:
        """Compare if two instances of Coins are equal."""
        if not isinstance(right, Coins):
            right = Coins(right)

        return self._amounts == right._amounts

    def __getitem__(self, denom: str) -> Coin:
        """Coins safe getter that prevents modifying of the reference."""
        amount = self._amounts[denom]
        return Coin(amount, denom)

    def __contains__(self, denom: str) -> bool:
        """Return true if denom is present."""
        return denom in self._amounts

    def __delitem__(self, denom: str):
        """Remove denom."""
        del self._amounts[denom]

    def __iter__(self):
        """Get coins iterator."""
        for denom, amount in self._amounts.items():
            yield Coin(amount, denom)

    def __add__(self, other):
        """Perform algebraic vector addition of two coin lists."""
        result = Coins(self)
        for (left, right) in self._math_operation(other, result_inout=result):
            left.amount += right.amount

        return result

    def __sub__(self, other):
        """Perform algebraic vector subtraction of two coin lists, ensuring no coin has negative value."""
        result = Coins(self)
        for (left, right) in self._math_operation(other, result_inout=result):
            if left.amount < right.amount:
                raise RuntimeError(
                    f"Subtracting {left} - {right} would result to negative value"
                )
            left.amount -= right.amount

        return result

    def __iadd__(self, other):
        """Perform *in-place* algebraic vector subtraction of two coin lists."""
        result = self
        for (left, right) in self._math_operation(other, result_inout=result):
            left.amount += right.amount

        return result

    def __isub__(self, other):
        """Perform *in-place* algebraic vector subtraction of two coin lists, ensuring no coin has negative value."""
        result = self
        for (left, right) in self._math_operation(other, result_inout=result):
            if left.amount < right.amount:
                raise RuntimeError(
                    f"Subtracting {left} - {right} would result to negative value"
                )
            left.amount -= right.amount

        return result

    def clear(self) -> "Coins":
        """Delete all coins."""
        self._amounts.clear()
        return self

    def denoms(self) -> Iterable[str]:
        """Return denominations of the coins in this(self) instance in ordered ascending alphabetically.

        :return: iterable of denominations
        """
        return self._amounts.keys()

    def assign(
        self,
        coins: Optional[CoinsParamType] = None,
    ) -> "Coins":
        """Assign passed in `coins` *in to* this ('self') instance.

        This means that the current value of this ('self') instance will be completely *replaced* with the value
        carried by the input `coins` parameter.

        :param coins: Input coins in any of the supported types.

        :raises TypeError: If coins or coin in a list has unexpected type

        :return: self
        """
        self.clear()

        if coins is None:
            return self

        if isinstance(coins, str):
            self._from_string(coins)
        elif isinstance(coins, Coins):
            self._from_coins_list(coins)
        elif isinstance(coins, (Coin, CoinProto)):
            self._from_coins_list([coins])
        elif isinstance(coins, list):
            if len(coins) == 0:
                pass
            elif isinstance(coins[0], (Coin, CoinProto)):
                self._from_coins_list(coins)
            else:
                raise TypeError(f"Invalid type {type(coins)}")
        else:
            raise TypeError(f"Invalid type {type(coins)}")

        return self

    def merge_from(
        self,
        coins: CoinsParamType,
        on_collision: OnCollision = OnCollision.Fail,
    ) -> "Coins":
        """Merge passed in coins in to this ('self') coins instance.

        :param coins: Input coins in any of the supported types.
        :param on_collision: Instructs what to do in the case of a denom collision = if this (self) already contains
                             one or more the denomination in the `coins` value:
                             - if `OnCollision.Override`: then the colliding coin amount in this (self) object will be
                               *overridden* with the colliding amount value from the `coins` parameter.
                             - if `OnCollision.Fail`: then the merge will *fail* with the `ValueError` exception when
                               the first collision is detected

        :return: The `self` instance containing merged coins
        """
        cs = Coins(coins)

        for c in cs:
            self._merge_coin(c, on_collision)

        return self

    def delete(self, denominations: Iterable[str]) -> "Coins":
        """Delete coins from this ('self') instance for each denom listed in `denominations` argument.

        :param denominations: collection of denominations to drop
        :return: deleted Coins
        """
        removed_coins = Coins()
        for denom in denominations:
            if denom in self:
                removed_coins.merge_from(self[denom])

        for c in removed_coins:
            del self[c.denom]

        return self

    def get(self, denom: str, default_amount: int) -> Coin:
        """Return Coin instance for the given `denom`.

        If coin with the given `denom` is not present, the `default` will be returned.

        Runtime complexity: `O(log(n))`

        This method poses the same risk to validity of the Coins value as the `__getitem__(...)` method,
        since at the moment it returns Coin instance *by-reference* what allows to change the `Coin.amount` value
        from external context and so potentially invalidate the value represented by the `Coins` class/container.

        :param denom: denomination of the coin to query.
        :param default_amount: default amount used to construct returned Coin instance if there is *no* coin with
                               the given `denom` present in this coins instance.
        :return: coin instance for the given `denom`, or the `default` value.

        Example::
        >>> from cosmpy.aerial.coins import Coin, Coins
        >>> cs = Coins("1aaa,2baa,3caa")
        >>> cs.get("baa", 0)
        2baa
        >>> cs.get("ggg", 0)
        0ggg
        """
        amount = self._amounts[denom] if denom in self._amounts else default_amount
        return Coin(amount, denom)

    def get_by_index(self, index: int) -> Coin:
        """Return Coin instance at given `index`.

        If the `index` is out of range, raises :exc:`IndexError`.

        Runtime complexity: `O(log(n))`

        This method poses the same risk to validity of the Coins value as the `__getitem__(...)` method,
        since at the moment it returns Coin instance *by-reference* what allows to change the `Coin.amount` value
        from external context and so potentially invalidate the value represented by the `Coins` class/container.

        Example::
        >>> from cosmpy.aerial.coins import Coin, Coins
        >>> cs = Coins("1aaa,2baa,3caa")
        >>> cs.get_by_index(0)
        1aaa
        >>> cs.get_by_index(2)
        3caa
        >>> cs.get_by_index(3)
        Traceback (most recent call last):
          ...
        IndexError: list index out of range

        :param index: int index of item (default -1)
        :return: key and value pair
        """
        denom, amount = self._amounts.peekitem(index)
        return Coin(amount, denom)

    def to_proto(self) -> List[CoinProto]:
        """Convert this type to *protobuf schema* Coins type."""
        return [c.to_proto() for c in self]

    def _merge_coin(self, coin: Coin, on_collision: OnCollision = OnCollision.Fail):
        """Merge singular aerial Coin in to this object.

        :param coin: input coin to merged.
        :param on_collision: If OnCollision.Override then the coin instance in this (self) object will be overridden
                             if it already contains the denomination, if OnCollision.Fail the merge will fail with
                             an exception.
        :raises ValueError: If there is denom collision and the `on_collision` is set to `OnCollision.Fail`,
                            or if the `on_collision` has unknown enum value.
        """
        if on_collision == OnCollision.Override:
            fail_on_collision = False
        elif on_collision == OnCollision.Fail:
            fail_on_collision = True
        else:
            raise ValueError(f"Unknown on_collision value: {on_collision}")

        is_already_present = coin.denom in self

        if coin.amount == 0:
            if not fail_on_collision and is_already_present:
                del self._amounts[coin.denom]

            # Skipping if amount is zero
            return

        if fail_on_collision and is_already_present:
            raise ValueError(
                f'Attempt to merge a coin with the "{coin.denom}" denomination which already exists in the receiving coins instance'
            )

        coin.validate()
        self._amounts[coin.denom] = coin.amount

    def _from_coins_list(self, coins: Iterable[Union[Coin, CoinProto]]):
        """Create aerial Coins from List of CoinProto objects."".

        :param coins: input list of coins
        """
        for c in coins:
            self._merge_coin(Coin(int(c.amount), c.denom))

    def _from_string(self, value: str):
        """Parse the coins string and merge it to self.

        :param value: coins
        """
        for coin in from_string(value):
            self._merge_coin(coin)

    @staticmethod
    def _math_operation(other: CoinsParamType, result_inout: "Coins"):
        res: Coins = result_inout

        if not isinstance(other, Coins):
            other = Coins(other)

        for c in other:
            left: Coin = res.get(c.denom, 0)
            yield left, c
            res._merge_coin(  # pylint: disable=protected-access
                left, on_collision=OnCollision.Override
            )


def parse_coins(value: str) -> List[CoinProto]:
    """Parse the coins.

    :param value: coins encoded in cosmos-sdk string format
    :return: List of CoinProto objects
    """
    return Coins(value).to_proto()


def from_string(value: str):
    """Parse the coins string and yields individual coins as Coin instances in order of their definition in input `value`.

    :param value: coins

    :yields: Coin objects one by one in the order they are specified in the input `value` string, where validation of
             the yielded Coin instance is intentionally *NOT* executed => yielded coin instance might *NOT* be valid
             when judged based on cosmos-sdk requirements.
             This is by-design to enable just basic parsing focused exclusively on the format of the coins string value.
             This leaves a degree of freedom for a caller on how the resulting/parsed coins should be used/consumed,
             rather than forcing any checks/validation for individual coins instances, or coins collection as a whole,
             here.

    :raises RuntimeError: If unable to parse the value
    """
    parts = re.split(r",\s*", value)
    for part in parts:
        part = part.strip()
        if part == "":
            continue

        match = re.match(r"^(\d+)(.+)$", part)
        if match is None:
            raise RuntimeError(f"Unable to parse value {part}")

        amount, denom = match.groups()
        yield Coin(int(amount), denom)


def is_coin_amount_valid(amount: int) -> bool:
    """Check if amount value conforms to Cosmos-SDK requirements.

    :param amount: amount to be checked
    :return: True if the amount conforms to cosmos-sdk requirement for Coin amount (when it is greater than zero),
             False otherwise.
    """
    return amount > 0


def is_denom_valid(denom: str) -> bool:
    """Check if denom value conforms to Cosmos-SDK requirements.

    :param denom: Denom to be checked
    :return: True if the denom conforms to cosmos-sdk requirement
    """
    return denom_regex.match(denom) is not None


def is_coins_sorted(
    coins: Union[str, Coins, Iterable[Coin], Iterable[CoinProto]]
) -> bool:
    """Return true if given coins representation is sorted in ascending order of denom.

    :param coins: Any type representing coins
    :return: bool is_sorted
    """
    if coins is None:
        return False

    if not coins:
        return True

    if isinstance(coins, str):
        coins = from_string(coins)

    itr = iter(coins)
    coin = next(itr, None)

    if coin is None:
        return True

    last_denom = coin.denom
    coin = next(itr, None)

    while coin is not None:
        if last_denom >= coin.denom:
            return False

        last_denom = coin.denom
        coin = next(itr, None)

    return True


def validate_coins(coins: Union[str, Coins, Iterable[Coin], Iterable[CoinProto]]):
    """Return true if given coins representation is valid.

    raises ValueError if there are multiple coins with the same denom

    :param coins: Any type representing coins
    :return: True if valid, False otherwise
    """
    if not coins:
        return

    if isinstance(coins, Coins):
        # Strictly speaking, this is not necessary, since API of the Coins class implicitly ensures validity of
        # the value it holds.
        for coin in coins:
            coin.validate()
    else:
        # Conversion to Coins will verify everything, no need to do anything else:
        _ = Coins(coins)
