from __future__ import annotations

import builtins
import logging
from abc import abstractmethod
from collections.abc import Sequence
from enum import Enum
from typing import ClassVar, Final, Self, Unpack

from askiff._sexpr import GeneralizedSexpr

from .base_class import AutoSerde
from .helpers import F, SerdeOpt

log = logging.getLogger()


class AutoSerdeEnum(Enum):
    """
    AutoSerdeEnum is an enhanced enum implementation that extends standard Enum behavior to support arbitrary values,
    enabling graceful handling of unknown or future KiCad enum options during deserialization.

    It automatically creates pseudo-members for unrecognized values while maintaining type safety for known options.
    The class overrides `_missing_` to log warnings and dynamically instantiate unknown enum values as members.

    Child classes should inherit also from
    * `_sexpr.Qstr` - to serialize as quoted strings
    * `str` - to serialize as unquoted strings
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


class AutoSerdeDownCasting(AutoSerde):
    """Base class for types that support downcasting during deserialization,
    allowing a single class to represent multiple related subtypes based on a designated field.
    """

    __askiff_childs: ClassVar[dict[str, builtins.type[Self]]]
    """Child class type lookup for automatic downcasting during deserialization."""

    type: Final[str] = F()
    """Keyword for to identify this specific subclass during downcasting"""

    @property
    @abstractmethod
    def __downcast_field(self) -> str | int:
        """Keyword or position (if `type` is positional), to find `type` in unparsed sexpr"""
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
        """Deserializes a sexpr into an instance of the class or one of its downcast subclasses"""
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


class AutoSerdeDownCastingAgg(AutoSerde):
    """Base class for types that support downcasting during deserialization,
    allowing a single class to represent multiple related subtypes based on a starting keyword.
    """

    __askiff_childs: ClassVar[dict[str, builtins.type[Self]]]
    """Child class type lookup for automatic downcasting during deserialization."""

    @classmethod
    def __init_subclass__(cls, **kwargs: Unpack[SerdeOpt]) -> None:  # type: ignore
        """Registers child class in `__askiff_childs` of all ancestors"""
        super().__init_subclass__(**kwargs)
        base = (getattr(parent, "_AutoSerdeDownCastingAgg__askiff_childs", None) for parent in cls.__mro__[1:])
        base_filtr = [b for b in base if b is not None]
        cls.__askiff_childs = {}
        for base_askiff_childs in base_filtr:
            askiff_key = getattr(cls, "_askiff_key", None)
            if askiff_key:
                base_askiff_childs[askiff_key] = cls

    @property
    @abstractmethod
    def _askiff_key(self) -> str:
        """Key used to identify the object type in KiCad sexpr files.
        Internal method for askiff's serialization system; library users should not call this directly."""
        # added to prevent direct creation of base classes (child classes should assign value to _askiff_key)
        pass

    @classmethod
    def deserialize_downcast_agg(cls, sexp: GeneralizedSexpr) -> Self:
        """Deserializes a sexpr into an instance of the class or one of its downcast subclasses"""
        deserialized_type = sexp[0]
        if deserialized_type not in cls.__askiff_childs:
            log.warning(
                f" Downcast failed: `{deserialized_type}` does not match child types ({cls.__askiff_childs.keys()})",
                extra={"amodule": cls.__name__},
            )
            log.debug(sexp, extra={"amodule": cls.__name__})
            return cls.deserialize(sexp[1:])
        return cls.__askiff_childs[deserialized_type].deserialize(sexp[1:])  # type: ignore
