from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable, MutableSet, Sequence
from copy import deepcopy
from enum import Enum, auto
from types import NoneType, UnionType
from typing import Any, Final, Literal, TypedDict, TypeVar, Union, Unpack, get_args, get_origin, get_type_hints

log = logging.getLogger()


class SerdeOpt(TypedDict, total=False):
    """Configures serialization and deserialization behavior for AutoSerde fields.

    Typed dictionary for configuring serialization and deserialization behavior of fields in AutoSerde classes.
    Controls aspects like naming, formatting, boolean handling, and field ordering.
    Used with the `F()` hint when defining fields.
    """

    precision: int
    """Maximum number of digits after decimal point for float serialization."""
    keep_trailing: bool
    """Whether trailing zeros are preserved in float serialization."""
    flatten: bool
    """Whether list items are flattened onto the current level during serialization.

        `(name (k v))(name (k v))` instead `(name (k v) (k v))`"""
    positional: bool
    """Whether field is serialized without an identifier prefix. Field recognized by its position in sexpr"""
    name: str
    """Field name/keyword in KiCad sexpr file"""
    name_case: str | None
    """Field name case conversion rule.
    
    Supported rules:
    
    * `lower` - to lower case, remove spaces & `_`
    """
    bare: bool
    """Whether field is serialized without surrounding parentheses
    `field_name (k v)` instead `(field_name (k v))`"""
    flag: bool
    """(bool only) Bool is true if corresponding keyword is present: `(field_name)` instead `(field_name yes)`"""
    skip: bool
    """Skip field during serialization and deserialization."""
    skip_deser: bool
    """Whether deserialization should skip this field."""
    skip_ser: bool
    """Whether field is skipped during serialization"""
    invert: bool
    """Whether the field's Python value is the logical inverse of its KiCad file representation."""
    nested: bool
    """Whether data is nested within a sub-Expression.
    `(field_name (inner_cls data data))` instead `(field_name data data)`"""
    unquoted: bool
    """Whether string values shall not be surrounded by double quotes during serialization."""
    true_val: str
    """Identifier representing `True` in KiCad file instead of `yes`"""
    false_val: str
    """Identifier representing `False` in KiCad file instead of `no`"""
    inline: bool
    """From the point of ser/deser fields of annotated field are copy pasted in main struct"""
    inline_basetype: type
    """(internal) Dict that allows down casting of `inline` type based on its first field"""
    serialize: Callable
    """Function that should be used to serialize field"""
    deserialize: Callable
    """Function that should be used to deserialize field"""
    keep_empty: bool
    """Whether to serialize empty fields that would otherwise be omitted."""
    after: str
    """Field name this field should be serialized after.

    This affects also following fields, unless they specify their own `after`
    `field_a = F(after="field_b")` will serialize in order 
    `[.., field_b, field_a, *fields-after-field_a, *fields-after-field_b]`
    """
    _version_options: dict[int, SerdeOpt]


class _AUTO_DEFAULT:  # noqa: N801
    """Marker class for automatic default values in field definitions.
    Used internally by AutoSerde to distinguish between explicitly set None values
    and fields that should use automatic defaults during serialization."""

    pass


AUTO_DEFAULT = _AUTO_DEFAULT()


class F(Any):
    """Field configuration class for controlling of fields serde behavior of AutoSerde

    After AutoSerde subclass initialization, replaced with resolved default value for field"""

    def __new__(cls, *args: Any, **kwargs: Unpack[SerdeOpt]) -> F:  # noqa: ANN401
        """Factory function for creating F objects used to provide serde hints for fields in KiCad file structs"""
        return super().__new__(cls)

    def __init__(self, default: Any = AUTO_DEFAULT, **kwargs: Unpack[SerdeOpt]) -> None:  # noqa: ANN401
        """Initialize a field configuration for automatic serialization/deserialization."""
        self.default = default
        self.options = kwargs

    @staticmethod
    def unlocked(default: Any = AUTO_DEFAULT, **kwargs: Unpack[SerdeOpt]) -> F:  # noqa: ANN401
        """Preset to handle `unlocked` flag as `locked` field"""
        return F(name="unlocked", invert=True, **kwargs)  # type:ignore

    def version(self, up_to_version: int, **kwargs: Unpack[SerdeOpt]) -> F:
        """Configures serde options for a specific version or lower."""
        self.options.setdefault("_version_options", {})
        self.options["_version_options"][up_to_version] = kwargs
        return self


def _is_optional(typ: type) -> bool:
    """Check if a type annotation represents an optional type (Union with None)."""
    type_origin, type_args = get_origin(typ), get_args(typ)
    return (type_origin is UnionType or type_origin is Union) and NoneType in type_args


def normalize_type(typ: type) -> type:
    """Normalizes a type annotation by resolving special typing constructs like
    `Literal`, `Final`, `TypeVar`, and `UnionType` into their concrete forms.
    Ensures consistent type handling during serialization and deserialization.

    Returns:
        Normalized type
    """
    type_origin, type_args = get_origin(typ), get_args(typ)
    if type_origin is Literal:
        typ = type(type_args[0])
        type_origin, type_args = get_origin(typ), get_args(typ)
    if type_origin is Final:
        typ = type_args[0]
        type_origin, type_args = get_origin(typ), get_args(typ)
    if type_origin is None:
        return typ
    if type_origin is UnionType:
        type_origin = Union

    if [arg for arg in type_args if get_origin(arg) is Literal]:
        type_args = tuple(type(get_args(arg)[0]) if get_origin(arg) is Literal else arg for arg in type_args)

    type_args = tuple(arg.__bound__ if isinstance(arg, TypeVar) else arg for arg in type_args)

    return type_origin[*type_args]  # type: ignore


@dataclasses.dataclass
class GeneratorParams:
    """Helper class for managing field serialization and deserialization parameters in AutoSerde.
    Extracts and stores type information, metadata, and processing flags needed during (de)serialization.
    """

    typ: type
    """Field type"""
    type_origin: Any
    """Base type of `typ`, if it is complex type"""
    type_args: tuple[Any, ...]
    """Type hints for generic type parameters"""
    is_optional: bool
    """Whether field is optional"""
    is_list: bool
    """Whether the field represents a list of items."""
    list_of_lists: bool | None
    """Whether the field represents a list of lists of items."""
    is_enum: bool
    """Whether field is enum."""
    fmeta: SerdeOpt
    """All field metadata for serde config"""
    positional: bool
    """Whether field is positional"""
    flatten: bool
    """Whether structure are flattened during serialization."""
    bare: bool
    """Whether the field is serialized without surrounding parentheses."""
    flag: bool
    """Whether the field is serialized as its name, with no value"""
    invert: bool
    """Whether the field value is inverted during KiCad file."""
    skip: bool
    """Skip serializing the field."""
    nested: bool
    """Whether the field has additional nesting in file"""
    agg: None | Callable
    """Aggregation function for processing field values during serialization."""
    inline_basetype: type | None
    """Base type for inline serialization"""
    alias: set[str]
    """Field keyword aliases"""
    fname: str
    """Keyword used for field in S-Expr"""
    vtrue: Sequence[str]
    """Values from S-Expr recognized as `True`"""
    vfalse: Sequence[str]
    """Values from S-Expr recognized as `False`"""

    @staticmethod
    def is_type_list(typ: type) -> bool:
        """Checks if a type annotation represents a list-like collection.
        Returns True for standard list, set, and subclasses of these types, including generic variants."""
        type_origin = get_origin(typ)
        return (
            # standard list/set
            type_origin is list
            or type_origin is set
            # class inherited from list but with generics
            or (isinstance(type_origin, type) and issubclass(type_origin, (list, set)))
            # class inherited from list
            or (isinstance(typ, type) and issubclass(typ, (list, MutableSet)))
        )

    def unwrap_list_type(self) -> None:
        """Unwraps the type annotation to extract the element type from list-like collections.
        Handles nested lists and Union types within lists.
        Modifies the instance's `typ` attribute to point to the actual element type."""
        if self.is_list:
            self.typ = get_args(self.typ)[0]
            if get_origin(self.typ) is UnionType:
                self.typ = get_args(self.typ)[0]

        self.list_of_lists = False
        if GeneratorParams.is_type_list(self.typ):
            # case of nested list
            self.typ = get_args(self.typ)[0]
            self.list_of_lists = True

    @staticmethod
    def _get_vtruefalse(fmeta: SerdeOpt, invert: bool) -> tuple[Sequence[str], Sequence[str]]:
        """Return true and false value tuples, that shall be recognized in file, optionally inverted."""
        _vtrue, _vfalse = fmeta.get("true_val", "yes"), fmeta.get("false_val", "no")
        vtrue = (_vtrue,) if "yes" == _vtrue else (_vtrue, "yes")
        vfalse = (_vfalse,) if "no" == _vfalse else (_vfalse, "no")
        return (vfalse, vtrue) if invert else (vtrue, vfalse)

    @staticmethod
    def _get_serialization_name(fmeta: SerdeOpt, class_field_name: str) -> str:
        """Return the fields serialization keyword based on metadata and naming conventions."""
        name_case = fmeta.get("name_case", None)
        fname = class_field_name
        if name_case == "lower":
            fname = fname.lower().replace("_", "")
        return fmeta.get("name", fname).split(".")[-1].removeprefix("_")

    @staticmethod
    def extract(
        cls_name: str, typ: type, class_field_name: str, field_meta: dict[str, SerdeOpt], serialization: bool
    ) -> GeneratorParams:
        """Extract fields serde config from fields type, name & metadata (from `F()`)"""
        type_origin, type_args = get_origin(typ), get_args(typ)
        is_optional = _is_optional(typ)
        if is_optional:
            typ = next(t for t in type_args if t is not NoneType)
            type_origin, type_args = get_origin(typ), get_args(typ)

        is_list = GeneratorParams.is_type_list(typ)
        is_enum = isinstance(typ, type) and issubclass(typ, Enum)
        fmeta = field_meta.get(class_field_name, {})

        positional, flatten, bare, flag, skip, invert, nested = [
            bool(fmeta.get(x, False)) for x in ["positional", "flatten", "bare", "flag", "skip", "invert", "nested"]
        ]
        if positional and flatten:
            raise Exception(f"`{cls_name}.{class_field_name}`: `flatten` & `positional` are mutually exclusive")

        skip = skip or bool(fmeta.get("skip_ser" if serialization else "skip_deser", False))

        fname = GeneratorParams._get_serialization_name(fmeta, class_field_name)

        alias: set[str] = getattr(typ, f"_{typ.__name__}__askiff_alias", set())
        if alias:
            alias = deepcopy(alias)
        alias.add(fname)

        agg = getattr(typ, f"_{typ.__name__}__askiff_aggregator", None)
        inline_basetype = fmeta.get("inline_basetype", None)

        vtrue, vfalse = GeneratorParams._get_vtruefalse(fmeta, invert)

        return GeneratorParams(
            typ,
            type_origin,
            type_args,
            is_optional,
            is_list,
            None,
            is_enum,
            fmeta,
            positional,
            flatten,
            bare,
            flag,
            invert,
            skip,
            nested,
            agg,
            inline_basetype,
            alias,
            fname,
            vtrue,
            vfalse,
        )


class SerMode(int, Enum):
    """Serialization modes for KiCad sexpr fields.
    Controls field serialization including type handling, nesting, and formatting."""

    SERIALIZE = auto()
    SERIALIZE_OVERRIDE = auto()
    SERIALIZE_NESTED = auto()
    BOOL = auto()
    BOOL_FLAG = auto()
    BOOL_FLAG_BARE = auto()
    INT = auto()
    FLOAT = auto()
    FLOAT_NO_TRIM = auto()
    STR = auto()
    QSTR = auto()
    ENUM = auto()
    QENUM = auto()
    LIST = auto()
    LIST_FLAT = auto()
    UNSUPPORTED = auto()


class DeserMode(int, Enum):
    """DeserMode enum defines serialization modes for KiCad file fields.
    Used internally by AutoSerde to control how fields are deserialized.
    Each mode specifies a different handling strategy from KiCad sexpr format to python structures"""

    DESERIALIZE = auto()
    DESERIALIZE_DOWNCAST = auto()
    DESERIALIZE_NESTED = auto()
    DESERIALIZE_OVERRIDE = auto()
    BOOL = auto()
    INT = auto()
    FLOAT = auto()
    STR = auto()
    ENUM = auto()
    ENUM_NESTED = auto()
    LIST = auto()
    LIST_AGG = auto()
    LIST_FLAT = auto()
    UNSUPPORTED = auto()
    INLINED = auto()


DeserModWExtra = tuple[str, DeserMode, Any]
"""(Object field name, deserialization mode, deserialization mode extra args)"""

SerModWExtra = tuple[SerMode, Any, bool]
"""(serialization_mode, serialization_mode_args, keep_if_empty)"""

_askiff_dict: dict[type, dict[str, Any]] = {}


def _resolve_mro_askiff_dict(cls: type) -> dict[str, Any]:
    """Get all fields with `F()` metadata including fields from ancestor classes,
    handling overrides according to inheritance order"""
    parent_dict: dict[str, Any] = {}
    for parent in reversed(cls.__mro__[1:]):  # first elem is class itself, ignore it
        parent_askiff_dict = _askiff_dict.get(parent, None)
        if parent_askiff_dict:
            # below handles indirect inheritance (C: subclass(B), B: subclass(A) & field is defined in A, but not in B)
            filtered_dict = {k: v for k, v in parent_askiff_dict.items() if not isinstance(v, dataclasses.Field)}  # type: ignore

            # If field is in multiple steps of inheritance use one with more direct ancestry
            overridden_fields = parent_dict.keys() & filtered_dict.keys()
            for key in overridden_fields:
                parent_dict.pop(key)
            parent_dict.update(filtered_dict)

    # If field is redefined in current class, use field position from current class, not parent
    overridden_fields = parent_dict.keys() & cls.__dict__.keys()
    for key in overridden_fields:
        parent_dict.pop(key)

    return parent_dict


def _resolve_mro_askiff_order(cls: type) -> list[str] | None:
    """Retrieve `__askiff_order` from ancestor classes"""
    askiff_order = None
    for parent in reversed(cls.__mro__[1:]):  # first elem is class itself, ignore it
        askiff_order = getattr(parent, f"_{parent.__name__}__askiff_order", askiff_order)
    return getattr(cls, f"_{cls.__name__}__askiff_order", askiff_order)


def resolve_serialization_order(cls: type, field_meta: dict[str, SerdeOpt]) -> list[str]:
    """Return field names in the order they should be serialized, based on class hierarchy & explicit ordering hints"""
    askiff_order = _resolve_mro_askiff_order(cls)
    if askiff_order:
        return [field for field in askiff_order if field in field_meta]

    ser_order: list[str] = []
    ser_order_idx = 0

    for name, options in field_meta.items():
        if name.startswith("_") and name[1:] in field_meta:
            ser_order.insert(ser_order_idx, name[1:])
            ser_order_idx += 1
            continue
        after = options.get("after", None)
        if after == "__begin__":
            ser_order_idx = 0
        elif after and after in ser_order:
            ser_order_idx = ser_order.index(after) + 1
        else:
            pass
        ser_order.insert(ser_order_idx, name)
        ser_order_idx += 1

    return ser_order


def _reorder_insert(meta_dict: dict, key: str, val: Any) -> None:  # noqa: ANN401
    """Inserts `val` to dict with `key`, pushing it to the end of the dict, if it was already in dict"""
    if not isinstance(val, F):
        meta_dict[key] = meta_dict.pop(key, {})
        return

    meta_dict[key] = val.options or meta_dict.pop(key, {})


def preprocess_cls_fields(cls: type) -> tuple[dict[str, type], dict[str, SerdeOpt]]:
    """Processes class fields to extract type hints and serialization metadata
    configuring dataclass-like behavior and building internal mapping for KiCad keyword resolution.

    Extracts field information from class and parent classes, handling special F() hints
    Creates `_askiff_dict` entry for class (used to retrieve parents `F()` meta data from child classes)

    Returns: (type_hints, field metadata)
    """
    type_hints = get_type_hints(cls)
    field_meta: dict[str, SerdeOpt] = {}
    cls_askiff_dict = _askiff_dict.setdefault(cls, {})

    parent_dict = _resolve_mro_askiff_dict(cls)

    for name, value in (parent_dict | cls.__dict__).items():
        if name.startswith("_"):
            if not isinstance(value, F) or (
                value.options.get("skip", False) and not value.options.get("_version_options", ())
            ):
                continue
            if name[1:] in parent_dict:
                _reorder_insert(field_meta, name[1:], value)

        if name not in type_hints:
            continue

        cls_askiff_dict[name] = value

        typ = normalize_type(type_hints[name])
        type_hints[name] = typ
        cls.__annotations__.setdefault(name, typ)

        if not isinstance(value, F):
            field_meta.setdefault(name, {})
            continue

        _reorder_insert(field_meta, name, value)

        if value.options.get("inline", False):
            value.options["skip"] = True
            inline_type_hints = get_type_hints(typ)
            inline_dict = deepcopy(_askiff_dict[typ])
            inner_childs = getattr(typ, f"_{typ.__name__}__askiff_childs", {})
            inner_dc_field = getattr(typ, f"_{typ.__name__}__askiff_down_cast_field", {})
            for ic in inner_childs.values():
                inline_dict |= _askiff_dict.get(ic, {})
                inline_type_hints |= get_type_hints(ic)
            for inline_field, inline_val in inline_dict.items():  # type:ignore
                full_id = name + "." + inline_field
                inline_typ = normalize_type(inline_type_hints[inline_field])
                type_hints[full_id] = inline_typ
                _reorder_insert(field_meta, full_id, inline_val)
                if inline_field == inner_dc_field:
                    filt_opt = deepcopy(value.options)
                    filt_opt.pop("inline")
                    filt_opt.pop("skip", None)
                    field_meta[full_id] |= filt_opt
                    field_meta[full_id]["inline_basetype"] = typ

        # normalize field default for dataclass processing
        if value.default == []:
            value.default = list
        if value.default == {}:
            value.default = dict
        if value.default == AUTO_DEFAULT:
            # Use class constructor (with no args) as default If Optional field, default to None
            value.default = None if _is_optional(typ) else typ
        if callable(value.default):
            setattr(cls, name, dataclasses.field(default_factory=value.default))
        else:
            setattr(cls, name, dataclasses.field(default=value.default))

    return type_hints, field_meta
