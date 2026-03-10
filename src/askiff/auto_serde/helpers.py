from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable, Sequence
from copy import deepcopy
from enum import Enum, auto
from types import NoneType, UnionType
from typing import Any, Final, Literal, TypedDict, Union, Unpack, get_args, get_origin, get_type_hints

log = logging.getLogger()


class SerdeOpt(TypedDict, total=False):
    precision: int
    """(float only) Max number of digits after point"""
    keep_trailing: bool
    """(float only) Keep trailing zeros"""
    flatten: bool
    """List is unpacked on current level: `(name (k v))(name (k v))` instead `(name (k v) (k v))`"""
    positional: bool
    """Field is serialized without id: `serialized` instead `(id serialized)`"""
    name: str
    """Override id used in file, by default id == field_name"""
    name_case: str
    """Convert field name using following case rule (supported rules: lower)"""
    bare: bool
    """Item shall not be surrounded by parenthesis: `field_name (k v)` instead `(field_name (k v))`
    Caution: If field is not of primitive type, its deserializer shall consume only sexpr that it actually needs
    """
    flag: bool
    """(bool only) Bool is true if corresponding keyword is present: `(field_name)` instead `(field_name yes)`"""
    skip: bool
    """AutoSerde will ignore this field"""
    skip_deser: bool
    """AutoSerde will ignore this field during deserialization"""
    skip_ser: bool
    """AutoSerde will ignore this field during serialization"""
    invert: bool
    """(bool only) Python filed will have inverted logic compared to kicad file"""
    nested: bool
    """Data is additionally nested `(field_name (inner_cls data data))` instead `(field_name data data)`"""
    unquoted: bool
    """(str only) If true string value will not be surrounded by double quotes """
    true_val: str
    """(bool only) Identifier to use as True value (instead of `yes`)"""
    false_val: str
    """(bool only) Identifier to use as False value (instead of `no`)"""
    inline: bool
    """From the point of ser/deser fields of annotated field are copy pasted in main struct"""
    inline_basetype: type
    """(internal) Dict that allows down casting of `inline` type based on its first field"""
    serialize: Callable
    """Function that should be used to serialize field"""
    keep_empty: bool
    """Serialize field even if it has value corresponding to false (eg. empty list)"""
    after: str
    """In KiCad file annotated field is after field with specified name
    This affects also following fields, unless they specify their own `after`
    `field_a = F(after="field_b")` will serialize in order 
    `[.., field_b, field_a, *fields-after-field_a, *fields-after-field_b]`
    """
    _version_options: dict[int, SerdeOpt]


# A sentinel object to detect if a parameter is supplied or not.  Use
# a class to give it a better repr.
class _AUTO_DEFAULT:  # noqa: N801
    pass


AUTO_DEFAULT = _AUTO_DEFAULT()


class F(Any):
    def __new__(cls, *args: Any, **kwargs: Unpack[SerdeOpt]) -> F:  # noqa: ANN401
        return super().__new__(cls)

    def __init__(self, default: Any = AUTO_DEFAULT, **kwargs: Unpack[SerdeOpt]) -> None:  # noqa: ANN401
        self.default = default
        self.options = kwargs
        self.options.setdefault("_version_options", {})

    @staticmethod
    def unlocked(default: Any = AUTO_DEFAULT, **kwargs: Unpack[SerdeOpt]) -> F:  # noqa: ANN401
        return F(name="unlocked", invert=True, **kwargs)  # type:ignore

    def version(self, up_to_version: int, **kwargs: Unpack[SerdeOpt]) -> F:
        """Different config options up to file `version` (inclusive)"""
        self.options["_version_options"][up_to_version] = kwargs
        return self


@dataclasses.dataclass
class GeneratorParams:
    """Helper class used by (de)serialize generator in AutoSerde"""

    typ: type
    type_origin: Any
    type_args: tuple[Any, ...]
    is_optional: bool
    is_list: bool
    list_of_lists: bool | None
    is_enum: bool
    fmeta: SerdeOpt
    positional: bool
    flatten: bool
    bare: bool
    flag: bool
    invert: bool
    skip: bool
    nested: bool
    agg: None | Callable
    inline_basetype: type | None
    alias: set[str]
    fname: str
    vtrue: Sequence[str]
    vfalse: Sequence[str]

    @staticmethod
    def is_type_list(typ: type) -> bool:
        type_origin = get_origin(typ)
        return (
            # standard list/set
            type_origin is list
            or type_origin is set
            # class inherited from list but with generics
            or (isinstance(type_origin, type) and issubclass(type_origin, (list, set)))
            # class inherited from list
            or (isinstance(typ, type) and issubclass(typ, (list, set)))
        )

    def unwrap_list_type(self) -> None:
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
    def extract(
        cls_name: str, typ: type, field: str, field_meta: dict[str, SerdeOpt], serialization: bool
    ) -> GeneratorParams:
        """Extract some variables useful for field processing"""
        type_origin, type_args = get_origin(typ), get_args(typ)
        is_optional = (type_origin is UnionType or type_origin is Union) and NoneType in type_args
        if is_optional:
            typ = next(t for t in type_args if t is not NoneType)
            type_origin, type_args = get_origin(typ), get_args(typ)

        is_list = GeneratorParams.is_type_list(typ)
        is_enum = isinstance(typ, type) and issubclass(typ, Enum)
        fmeta = field_meta.get(field, {})

        positional, flatten, bare, flag, skip, invert, nested = [
            bool(fmeta.get(x, False)) for x in ["positional", "flatten", "bare", "flag", "skip", "invert", "nested"]
        ]
        skip = skip or bool(fmeta.get("skip_ser" if serialization else "skip_deser", False))

        if positional and flatten:
            raise Exception(f"`{cls_name}.{field}`: `flatten` & `positional` are mutually exclusive")
        name_case = fmeta.get("name_case", None)
        fname = field
        if name_case == "lower":
            fname = fname.lower().replace("_", "")
        fname = fmeta.get("name", fname).split(".")[-1]

        agg = getattr(typ, f"_{typ.__name__}__askiff_aggregator", None)
        inline_basetype = fmeta.get("inline_basetype", None)

        alias: set[str] = getattr(typ, f"_{typ.__name__}__askiff_alias", set())
        alias.add(fname)

        _vtrue, _vfalse = fmeta.get("true_val", "yes"), fmeta.get("false_val", "no")
        vtrue = (_vtrue,) if "yes" == _vtrue else (_vtrue, "yes")
        vfalse = (_vfalse,) if "no" == _vfalse else (_vfalse, "no")
        if invert:
            vtrue, vfalse = vfalse, vtrue

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


def normalize_type(typ: type) -> tuple:
    type_origin, type_args = get_origin(typ), get_args(typ)
    if type_origin is Literal:
        typ = type(type_args[0])
        type_origin, type_args = get_origin(typ), get_args(typ)
    if type_origin is Final:
        typ = type_args[0]
        type_origin, type_args = get_origin(typ), get_args(typ)
    if type_origin is not None and [arg for arg in type_args if get_origin(arg) is Literal]:
        type_args = tuple(type(get_args(arg)[0]) if get_origin(arg) is Literal else arg for arg in type_args)
        typ = type_origin[*type_args]
    return typ, type_origin, type_args


class SerMode(int, Enum):
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
    DESERIALIZE = auto()
    DESERIALIZE_DOWNCAST = auto()
    DESERIALIZE_NESTED = auto()
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

_askiff_dict: dict[type, dict[str, Any]] = {}


def preprocess_cls_fields(cls: type) -> tuple[dict[str, type], dict[str, SerdeOpt], list[str]]:
    """Process typing and defaults of class, configure for dataclass and extract metadata,
    create `_askiff_dict` entry for class
    returns (type_hints, field metadata, field names in serialization order)
    """
    type_hints = get_type_hints(cls)
    field_meta = {}
    cls_askiff_dict = _askiff_dict.setdefault(cls, {})
    parent_dict = {}
    askiff_order = None

    for parent in reversed(cls.__mro__[1:]):  # first elem is class itself, ignore it
        parent_askiff_dict = _askiff_dict.get(parent, None)
        if parent_askiff_dict:
            # bellows handles case where A->B->C and field is defined in A, but not in B
            filtered_dict = {k: v for k, v in parent_askiff_dict.items() if not isinstance(v, dataclasses.Field)}  # type: ignore
            askiff_order = getattr(parent, f"_{parent.__name__}__askiff_order", askiff_order)
            parent_dict.update(filtered_dict)

    ser_order: list[str] = []
    ser_order_idx = 0
    askiff_order = getattr(cls, f"_{cls.__name__}__askiff_order", askiff_order)
    overridden_fields = parent_dict.keys() & cls.__dict__.keys()
    for key in overridden_fields:
        parent_dict.pop(key)

    for name, value in (parent_dict | cls.__dict__).items():
        skip_field = True
        if name.startswith("_") and name[1:] in type_hints:
            ser_order.insert(ser_order_idx, name[1:])
            ser_order_idx += 1
        elif name.startswith("_") and name in type_hints and isinstance(value, F):
            ser_order.insert(ser_order_idx, name)
            ser_order_idx += 1
            skip_field = False
        elif not name.startswith("_") and name in type_hints:
            skip_field = False
            if ("_" + name) not in cls.__dict__:
                if isinstance(value, F):
                    after = value.options.get("after", None)
                    if after == "__begin__":
                        ser_order_idx = 0
                    elif after and after in ser_order:
                        ser_order_idx = ser_order.index(after) + 1
                ser_order.insert(ser_order_idx, name)
                ser_order_idx += 1

        if skip_field:
            continue

        typ, type_origin, type_args = normalize_type(type_hints[name])
        type_hints[name] = typ

        cls_askiff_dict[name] = value

        if name in type_hints and name not in cls.__annotations__:
            cls.__annotations__[name] = type_hints[name]
        if isinstance(value, F):
            inline, skip = value.options.get("inline"), value.options.get("skip")
            if inline or skip:
                ser_order_idx -= 1
                ser_order.pop(ser_order_idx)  # skipped or inlined field will not be serialized directly

            if inline:
                inline_type_hints = get_type_hints(typ)
                inline_dict = deepcopy(_askiff_dict[typ])
                inner_childs = getattr(typ, f"_{typ.__name__}__askiff_childs", {})
                inner_dc_field = getattr(typ, f"_{typ.__name__}__askiff_down_cast_field", {})
                for ic in inner_childs.values():
                    inline_dict |= _askiff_dict.get(ic, {})
                    inline_type_hints |= get_type_hints(ic)
                for inline_field, inline_val in inline_dict.items():  # type:ignore
                    full_id = name + "." + inline_field
                    inline_typ, _, _ = normalize_type(inline_type_hints[inline_field])
                    type_hints[full_id] = inline_typ
                    field_meta[full_id] = inline_val.options if isinstance(inline_val, F) else {}
                    if inline_field == inner_dc_field:
                        filt_opt = deepcopy(value.options)
                        filt_opt.pop("inline")
                        filt_opt.pop("skip", None)
                        field_meta[full_id] |= filt_opt
                        field_meta[full_id]["inline_basetype"] = typ
                    ser_order.insert(ser_order_idx, full_id)
                    ser_order_idx += 1
                value.options["skip"] = True

            if value.options:
                field_meta[name] = value.options
            if value.default is None:
                continue

            if value.default == []:
                value.default = list
            if value.default == {}:
                value.default = dict
            if value.default == AUTO_DEFAULT:
                # Use class constructor (with no args) as default If Optional field, default to None
                value.default = (
                    None if (type_origin is UnionType or type_origin is Union) and NoneType in type_args else typ
                )
            if callable(value.default):
                setattr(cls, name, dataclasses.field(default_factory=value.default))
            else:
                setattr(cls, name, dataclasses.field(default=value.default))
        if name not in field_meta:
            field_meta[name] = {}
    ser_ord = [field for field in askiff_order or ser_order if field in type_hints]
    return type_hints, field_meta, ser_ord
