from __future__ import annotations

import builtins
import logging
from abc import abstractmethod
from collections.abc import Generator, Sequence
from enum import Enum
from types import UnionType
from typing import ClassVar, Final, Generic, Self, TypeVar, Unpack, get_args, get_origin

from askiff.sexpr import GeneralizedSexpr, Sexpr

from .base_class import AutoSerde
from .helpers import F, SerdeOpt

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


class AutoSerdeDownCasting(AutoSerde):
    __askiff_childs: ClassVar[dict[str, builtins.type[Self]]]

    type: Final[str] = F()

    @property
    @abstractmethod
    def __downcast_field(self) -> str | int:
        pass

    @classmethod
    def __init_subclass__(cls, **kwargs: Unpack[SerdeOpt]) -> None:  # type: ignore
        super().__init_subclass__(**kwargs)
        if not hasattr(cls.__mro__[0], "_AutoSerdeDownCasting__askiff_childs"):
            cls.__askiff_childs = {}
            return
        cls.__askiff_childs = cls.__mro__[0].__askiff_childs  # type: ignore # ty:ignore[unresolved-attribute]
        cls.__askiff_childs[cls.type] = cls  # type: ignore

    @classmethod
    def deserialize_downcast(cls, sexp: GeneralizedSexpr) -> Self:
        dcf = cls.__downcast_field
        if isinstance(dcf, int):
            deserialized_type = sexp[dcf]
        else:
            deserialized_type = next(
                (
                    s[1]
                    for s in sexp
                    if isinstance(s, Sequence) and len(s) >= 2 and s[0] == dcf and isinstance(s[1], str)
                ),
                None,
            )

        if deserialized_type not in cls.__askiff_childs:
            log.warning(
                f" Downcast failed: `{deserialized_type}` does not match child types ({cls.__askiff_childs.keys()})",
                extra={"amodule": cls.__name__},
            )
            log.debug(sexp, extra={"amodule": cls.__name__})
            return cls.deserialize(sexp)
        return cls.__askiff_childs[deserialized_type].deserialize(sexp)  # type: ignore
