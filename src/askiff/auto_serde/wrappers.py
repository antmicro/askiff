from __future__ import annotations

import logging
from collections.abc import Generator
from enum import Enum
from types import UnionType
from typing import Generic, TypeVar, get_args, get_origin

from askiff.sexpr import Sexpr

log = logging.getLogger()


class AutoSerdeEnum(Enum):
    """Class for definition of enums, comparing to `enum.Enum` class it allows storing arbitrary values
    (to allow new options that KiCad may add in future)
    Inherit also from sexpr.Qstr to serialize as quoted string
    """

    @classmethod
    def _missing_(cls, value):  # type: ignore  # noqa: ANN001, ANN206
        # Handle unknown enum fields that may be added in future KiCad versions
        # dynamically create a pseudo-member
        log.warning(f"Unknown option: {value}", extra={"amodule": cls.__name__})
        obj = str.__new__(cls, value)
        obj._name_ = None
        obj._value_ = value
        return obj


T = TypeVar("T")


class AutoSerdeAgg(Generic[T], list[T]):
    """Wrapper around list, used to aggregate few types in one list

    Generic can be either:
    * Union of classes with `_askiff_key: ClassVar[str]`
    * Class with `__askiff_childs: ClassVar[dict[str, type]]`

    It handles unrecognized variants transparently
    (they are skipped during iteration but serialized back during serialization)
    """

    @classmethod
    def __askiff_aggregator(cls, inner: type) -> dict[str, type]:
        inner_origin, inner_args = get_origin(inner), get_args(inner)
        if inner_origin is UnionType:
            ret = {}
            for typ in inner_args:
                askiff_key = getattr(typ, "_askiff_key", None)
                if askiff_key is None:
                    raise Exception(
                        f"{cls.__name__}: Aggregated type is {inner}, but {typ.__name__} has no `_askiff_key"
                    )
                ret[askiff_key] = typ
            return ret

        askiff_childs = getattr(inner, f"_{inner.__name__}__askiff_childs", None)
        if askiff_childs is None:
            raise Exception(f"{cls.__name__}: Aggregated type is {inner}, but it has no `__askiff_childs")
        return {k: v for (k, v) in askiff_childs.items() if issubclass(v, inner)}

    def __iter__(self) -> Generator:
        sexpr = Sexpr
        for item in super().__iter__():
            if not isinstance(item, sexpr):
                yield item
