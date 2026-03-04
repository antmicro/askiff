from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable, Generator, Iterable
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from pprint import pprint
from types import NoneType, UnionType
from typing import (
    Any,
    ClassVar,
    Final,
    Generic,
    Literal,
    Self,
    TypedDict,
    TypeVar,
    Unpack,
    cast,
    dataclass_transform,
    get_args,
    get_origin,
    get_type_hints,
)

from .const import TRACE, TRACE_DIS, Version
from .sexpr import GeneralizedSexpr, Qstr, Sexpr

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
    bare: bool
    """Item shall not be surrounded by parenthesis: `field_name (k v)` instead `(field_name (k v))`
    Caution: If field is not of primitive type, its deserializer shall consume only sexpr that it actually needs
    """
    flag: bool
    """(bool only) Bool is true if corresponding keyword is present: `(field_name)` instead `(field_name yes)`"""
    skip: bool
    """AutoSerde will ignore this field"""
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

    @staticmethod
    def unlocked(default: Any = AUTO_DEFAULT, **kwargs: Unpack[SerdeOpt]) -> F:  # noqa: ANN401
        return F(name="unlocked", invert=True, **kwargs)  # type:ignore


class AutoSerdeEnum(Enum):
    """Class for definition of enums, comparing to `enum.Enum` class it allows storing arbitrary values
    (to allow new options that KiCad may add in future)
    Inherit also from sexpr.Qstr to serialize as quoted string
    """

    @classmethod
    def _missing_(cls, value):  # type: ignore  # noqa: ANN001, ANN206
        # Handle unknown enum fields that may be added in future KiCad versions
        # dynamically create a pseudo-member
        log.warning(f"{cls.__name__}: Unknown option: {value}")
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


@dataclass
class _GeneratorParams:
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
    vtrue: str
    vfalse: str

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
        if _GeneratorParams.is_type_list(self.typ):
            # case of nested list
            self.typ = get_args(self.typ)[0]
            self.list_of_lists = True

    @staticmethod
    def extract(cls_name: str, typ: type, field: str, field_meta: dict[str, SerdeOpt]) -> _GeneratorParams:
        """Extract some variables useful for field processing"""
        type_origin, type_args = get_origin(typ), get_args(typ)
        is_optional = type_origin is UnionType and NoneType in type_args
        if is_optional:
            typ = next(t for t in type_args if t is not NoneType)
            type_origin, type_args = get_origin(typ), get_args(typ)

        is_list = _GeneratorParams.is_type_list(typ)
        is_enum = isinstance(typ, type) and issubclass(typ, Enum)
        fmeta = field_meta.get(field, {})

        positional, flatten, bare, flag, skip, invert, nested = [
            bool(fmeta.get(x, False)) for x in ["positional", "flatten", "bare", "flag", "skip", "invert", "nested"]
        ]

        if positional and flatten:
            raise Exception(f"`{cls_name}.{field}`: `flatten` & `positional` are mutually exclusive")
        fname = fmeta.get("name", field).split(".")[-1]

        agg = getattr(typ, f"_{typ.__name__}__askiff_aggregator", None)
        inline_basetype = fmeta.get("inline_basetype", None)

        alias: set[str] = getattr(typ, f"_{typ.__name__}__askiff_alias", set())
        alias.add(fname)

        vtrue, vfalse = fmeta.get("true_val", "yes"), fmeta.get("false_val", "no")
        if invert:
            vtrue, vfalse = vfalse, vtrue

        return _GeneratorParams(
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


def _normalize_type(typ: type) -> tuple:
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


@dataclass_transform(field_specifiers=(F, dataclasses.field))
class AutoSerde:
    """
    Base class that adds serialize/deserialize functions based on field typing and F() objects passed as field defaults
    Field will be serialized in same order as defined

    Class level implementation tunning:
    * field name prefixed `_` - indicated that matching field from parent struct shall be serialized in this place
    * `__askiff_order: ClassVar[list[str]]` - allows to force fully arbitrary field reorder
    * `_askiff_key: ClassVar[str]` - default struct `name` after serialization
        (struct is serialized as `($name ..struct_fields..)`)
        in most cases default name is overridden by serialize(name=..) (typically set to field name or value from `F()`)
        except for usage inside aggregator classes or union
    * `__askiff_alias: ClassVar[set[str]]` - Additional struct `name` that may occur in serialized file
    * `__askiff_aggregator(inner: type) -> dict[str, type]` - indicates that class is an aggregator
        = either itself or inner type can be deserialized into different classes depending on serialized name
        should return {serialized_name: type_to_deserialize_into}
    * `_askiff_pre_ser(self) -> Self` - pre processing before serialization
    * `_askiff_post_deser(self) -> None` - post processing after deserialization
    * `SerdeOpt` keywords passed with base class (`class SomeClass(AutoSerde, flag=True)`) are applied to all fields

    Handling of each field can be modified by passing F(**kwargs) as field default, see `SerdeOpt` for available options
    """

    __extra: Sexpr | None = None
    __extra_positional: Sexpr | None = None
    __askiff_dict: dict
    __ser_field_positional: dict[str, tuple[SerMode, Any]]
    __ser_field: dict[str, tuple[str, tuple[SerMode, Any]]]
    __deser_field_positional: list[DeserModWExtra]
    __deser_field: dict[str, DeserModWExtra]
    __deser_field_bare_flags: dict[str, DeserModWExtra]

    @classmethod
    def __init_deserializer(
        cls, ser_order: list[str], type_hints: dict[str, type], field_meta: dict[str, SerdeOpt]
    ) -> None:
        cls.__deser_field, cls.__deser_field_positional, cls.__deser_field_bare_flags = {}, [], {}
        names_kicad = {v.get("name", k).split(".")[-1] for k, v in field_meta.items()}

        def inline_wrap(field: str, mode: DeserMode, extra: Any) -> DeserModWExtra:  # noqa: ANN401
            if "." in field:
                return field, DeserMode.INLINED, (mode, extra)
            return field, mode, extra

        for field in ser_order:
            typ = type_hints[field]
            fparam = _GeneratorParams.extract(cls.__name__, typ, field, field_meta)
            typ = fparam.typ
            fmode: tuple[DeserMode, Any]
            if fparam.agg:
                if fparam.flatten:
                    for var_name, var_type in fparam.agg(inner=fparam.type_args[0]).items():
                        fmode = DeserMode.DESERIALIZE, var_type
                        cls.__deser_field[var_name] = inline_wrap(field, DeserMode.LIST_FLAT, fmode)
                else:
                    cls.__deser_field[fparam.fname] = inline_wrap(
                        field, DeserMode.LIST_AGG, fparam.agg(inner=fparam.type_args[0])
                    )
                continue

            if hasattr(typ, "deserialize_downcast"):
                fmode = DeserMode.DESERIALIZE_DOWNCAST, typ
            elif hasattr(typ, "deserialize"):
                if fparam.nested:
                    fmode = DeserMode.DESERIALIZE_NESTED, typ
                else:
                    fmode = DeserMode.DESERIALIZE, typ
            else:
                fparam.unwrap_list_type()
                typ = fparam.typ

                if hasattr(typ, "deserialize_downcast"):
                    fmode = DeserMode.DESERIALIZE_DOWNCAST, typ
                elif hasattr(typ, "deserialize"):
                    fmode = DeserMode.DESERIALIZE, typ
                elif issubclass(typ, Enum):
                    bare_flags = [flag.value for flag in typ if flag.value != ""]
                    mode = DeserMode.ENUM_NESTED if fparam.nested else DeserMode.ENUM
                    fmode = mode, typ
                elif typ is bool:
                    bare_flags = [fparam.fname]
                    fmode = DeserMode.BOOL, [[], [fparam.vtrue]]
                elif typ is int:
                    fmode = DeserMode.INT, None
                elif typ is float:
                    fmode = DeserMode.FLOAT, None
                elif issubclass(typ, str):
                    fmode = DeserMode.STR, None
                else:
                    raise Exception(f"{cls}.__init_deserializer: Unsupported type: {field}: {typ}")

                if fparam.list_of_lists:
                    fmode = DeserMode.LIST, fmode
                if fparam.is_list:
                    fmode = DeserMode.LIST_FLAT if fparam.flatten else DeserMode.LIST, fmode

            if fparam.bare and fparam.flag:
                for flag in bare_flags:
                    cls.__deser_field_bare_flags[flag] = inline_wrap(field, *fmode)
            elif fparam.positional:
                cls.__deser_field_positional.append(inline_wrap(field, *fmode))
            else:
                aliases = [alias for alias in fparam.alias if alias not in names_kicad]
                aliases.append(fparam.fname)
                for alias in aliases:
                    cls.__deser_field[alias] = inline_wrap(field, *fmode)

        if __debug__:  # __debug__ allows total code removal if PYTHONOPTIMIZE flag is set
            if log.isEnabledFor(TRACE):
                print("\n#########################################################")
                print(f"# Deserialization map for {cls}:")
                pprint(cls.__deser_field_positional)
                pprint(cls.__deser_field)
                print()

    @classmethod
    def deserialize(cls, sexp: GeneralizedSexpr) -> Self:
        ret: Self = cls()
        deser_map = cls.__deser_field
        deser_map_pos = cls.__deser_field_positional
        pos_idx = 0
        for node in sexp:
            if isinstance(node, str):
                field, mode, mode_extra = (
                    deser_map_pos[pos_idx]
                    if pos_idx < len(deser_map_pos)
                    # bellow cast is to trick typecheckers, we are ensuring correct
                    # types/method availability on __init_deserialzier level
                    else ("", DeserMode.UNSUPPORTED, cast(Any, None))
                )
                match mode:
                    case DeserMode.DESERIALIZE:
                        setattr(ret, field, mode_extra.deserialize(node))
                    case DeserMode.DESERIALIZE_DOWNCAST:
                        setattr(ret, field, mode_extra.deserialize_downcast(node))
                    case DeserMode.BOOL:
                        setattr(ret, field, node in mode_extra)
                    case DeserMode.INT:
                        setattr(ret, field, int(node))
                    case DeserMode.FLOAT:
                        setattr(ret, field, float(node))
                    case DeserMode.STR:
                        setattr(ret, field, str(node))
                    case DeserMode.ENUM:
                        setattr(ret, field, mode_extra(node))
                    case DeserMode.INLINED:
                        mode, mode_extra = mode_extra
                        outer_field, _, field = field.partition(".")
                        match mode:
                            case DeserMode.DESERIALIZE:
                                setattr(getattr(ret, outer_field), field, mode_extra.deserialize(node))
                            case DeserMode.DESERIALIZE_DOWNCAST:
                                setattr(getattr(ret, outer_field), field, mode_extra.deserialize_downcast(node))
                            case DeserMode.BOOL:
                                setattr(getattr(ret, outer_field), field, node in mode_extra)
                            case DeserMode.INT:
                                setattr(getattr(ret, outer_field), field, int(node))
                            case DeserMode.FLOAT:
                                setattr(getattr(ret, outer_field), field, float(node))
                            case DeserMode.STR:
                                setattr(getattr(ret, outer_field), field, str(node))
                            case DeserMode.ENUM:
                                setattr(getattr(ret, outer_field), field, mode_extra(node))

                    case _:
                        field, mode, mode_extra = cls.__deser_field_bare_flags.get(
                            node, ("", DeserMode.UNSUPPORTED, None)
                        )
                        match mode:
                            case DeserMode.BOOL:
                                setattr(ret, field, True)
                            case DeserMode.ENUM:
                                setattr(ret, field, mode_extra(node))
                            case DeserMode.INLINED:
                                mode, mode_extra = mode_extra
                                outer_field, _, field = field.partition(".")
                                match mode:
                                    case DeserMode.BOOL:
                                        setattr(getattr(ret, outer_field), field, True)
                                    case DeserMode.ENUM:
                                        setattr(getattr(ret, outer_field), field, mode_extra(node))
                            case _:
                                if ret.__extra_positional is None:
                                    ret.__extra_positional = Sexpr()
                                ret.__extra_positional.append(node)
                                log.warning(f" Unexpected positional node: `{node}`", extra={"amodule": cls.__name__})
                pos_idx += 1
                continue

            node_name, *nodes = node

            field, mode, mode_extra = deser_map.get(
                node_name,
                # bellow cast is to trick typecheckers, we are ensuring correct
                # types/method availability on __init_deserialzier level
                ("", DeserMode.UNSUPPORTED, cast(Any, None)),
            )
            inlined = mode == DeserMode.INLINED
            if inlined:
                mode, mode_extra = mode_extra
                outer_field, _, field = field.partition(".")
                ret_cp = ret
                ret = getattr(ret, outer_field)
            match mode:
                case DeserMode.DESERIALIZE:
                    setattr(ret, field, mode_extra.deserialize(nodes))
                case DeserMode.DESERIALIZE_NESTED:
                    setattr(ret, field, mode_extra.deserialize(nodes[0][1:]))
                case DeserMode.DESERIALIZE_DOWNCAST:
                    setattr(ret, field, mode_extra.deserialize_downcast(nodes))
                case DeserMode.BOOL:
                    setattr(ret, field, nodes in mode_extra)
                case DeserMode.INT:
                    setattr(ret, field, int(nodes[0]))
                case DeserMode.FLOAT:
                    setattr(ret, field, float(nodes[0]))
                case DeserMode.STR:
                    setattr(ret, field, str(nodes[0]))
                case DeserMode.ENUM:
                    setattr(ret, field, mode_extra(nodes[0]))
                case DeserMode.LIST_FLAT:
                    list_obj = getattr(ret, field, None)
                    if list_obj is None:
                        list_obj = []
                        setattr(ret, field, list_obj)
                    mode, mode_extra = mode_extra
                    match mode:
                        case DeserMode.DESERIALIZE:
                            list_obj.append(mode_extra.deserialize(nodes))
                        case DeserMode.DESERIALIZE_DOWNCAST:
                            list_obj.append(mode_extra.deserialize_downcast(nodes))
                        case DeserMode.BOOL:
                            list_obj.append(nodes in mode_extra)
                        case DeserMode.INT:
                            list_obj.append(int(nodes[0]))
                        case DeserMode.FLOAT:
                            list_obj.append(float(nodes[0]))
                        case DeserMode.STR:
                            list_obj.append(str(nodes[0]))
                        case DeserMode.ENUM:
                            list_obj.append(mode_extra(nodes[0]))
                        case _:
                            raise Exception(f"Unreachable {field} {mode}")
                case DeserMode.LIST_AGG:
                    list_obj = getattr(ret, field, None)
                    if list_obj is None:
                        list_obj = []
                        setattr(ret, field, list_obj)
                    list_obj.extend(mode_extra.get(n, Sexpr).deserialize(ns) for n, *ns in nodes)

                case DeserMode.LIST:
                    list_obj = getattr(ret, field, None)
                    if list_obj is None:
                        list_obj = []
                        setattr(ret, field, list_obj)
                    mode, mode_extra = mode_extra
                    match mode:
                        case DeserMode.DESERIALIZE:
                            list_obj.extend(mode_extra.deserialize(n[1:]) for n in nodes)
                        case DeserMode.DESERIALIZE_DOWNCAST:
                            list_obj.extend(mode_extra.deserialize_downcast(n[1:]) for n in nodes)
                        case DeserMode.BOOL:
                            list_obj.extend((n in mode_extra) for n in nodes)
                        case DeserMode.INT:
                            list_obj.extend(int(n) for n in nodes)
                        case DeserMode.FLOAT:
                            list_obj.extend(float(n) for n in nodes)
                        case DeserMode.STR:
                            list_obj.extend(str(n) for n in nodes)
                        case DeserMode.ENUM:
                            list_obj.extend(mode_extra(n) for n in nodes)
                        case DeserMode.ENUM_NESTED:
                            list_obj.extend(mode_extra(n[1]) for n in nodes)
                        case DeserMode.LIST:
                            mode, mode_extra = mode_extra
                            match mode:
                                case DeserMode.STR:
                                    list_obj.extend([str(ni) for ni in n] for n in nodes)
                                case DeserMode.ENUM:
                                    list_obj.extend([mode_extra(ni) for ni in n] for n in nodes)
                                case _:
                                    raise Exception(f"Unreachable {field} {mode}")
                        case _:
                            raise Exception(f"Unreachable {field} {mode}")
                case _:
                    if ret.__extra is None:
                        ret.__extra = Sexpr()
                    ret.__extra.append(node)
                    log.warning(f" Unknown node: `{node_name}`", extra={"amodule": cls.__name__})
                    log.debug(node, extra={"amodule": cls.__name__})
            if inlined:
                ret = ret_cp

        askiff_post_deser = getattr(ret, "_askiff_post_deser", None)
        if askiff_post_deser:
            askiff_post_deser()
        return ret

    @classmethod
    def __init_serializer(
        cls, ser_order: list[str], type_hints: dict[str, type], field_meta: dict[str, SerdeOpt]
    ) -> None:
        cls.__ser_field, cls.__ser_field_positional = {}, {}
        for field in ser_order:
            typ = type_hints[field]
            fparam = _GeneratorParams.extract(cls.__name__, typ, field, field_meta)
            fmode: tuple[SerMode, Any]
            explicit_name = fparam.fmeta.get("name", None)

            serialize_override = fparam.fmeta.get("serialize", None)
            if callable(serialize_override):
                fmode = SerMode.SERIALIZE_OVERRIDE, serialize_override
            elif hasattr(fparam.typ, "serialize"):
                if fparam.nested:
                    fmode = SerMode.SERIALIZE_NESTED, None
                else:
                    fmode = SerMode.SERIALIZE, explicit_name
            else:
                fparam.unwrap_list_type()
                typ = fparam.typ

                if hasattr(typ, "serialize"):
                    fmode = SerMode.SERIALIZE, explicit_name
                elif issubclass(typ, Enum):
                    if issubclass(typ, Qstr):
                        fmode = SerMode.QENUM, None
                    else:
                        fmode = SerMode.ENUM, None
                elif typ is bool and fparam.flag and fparam.bare:
                    fmode = SerMode.BOOL_FLAG_BARE, fparam.invert
                elif typ is bool and fparam.flag:
                    fmode = SerMode.BOOL_FLAG, fparam.invert
                elif typ is bool:
                    fmode = SerMode.BOOL, (fparam.vtrue, fparam.vfalse)
                elif typ is int:
                    fmode = SerMode.INT, None
                elif typ is float and fparam.fmeta.get("keep_trailing", False):
                    fmode = SerMode.FLOAT_NO_TRIM, fparam.fmeta.get("precision", 6)
                elif typ is float:
                    fmode = SerMode.FLOAT, fparam.fmeta.get("precision", 6)
                elif issubclass(typ, str):
                    no_quote = fparam.fmeta.get("unquoted", False)
                    fmode = (SerMode.STR if no_quote else SerMode.QSTR), None
                else:
                    raise Exception(f"{cls}.__init_serializer: Unsupported type: {field}: {typ}")

                if fparam.list_of_lists:
                    fmode = SerMode.LIST, fmode
                if fparam.is_list:
                    fmode = SerMode.LIST_FLAT if fparam.flatten else SerMode.LIST, fmode

            if fparam.positional:
                cls.__ser_field_positional[field] = fmode
            else:
                cls.__ser_field[field] = fparam.fname, fmode
        if __debug__:  # __debug__ allows total code removal if PYTHONOPTIMIZE flag is set
            if log.isEnabledFor(TRACE):
                print("\n#########################################################")
                print(f"# Serialization map for {cls}:")
                pprint(cls.__ser_field_positional)
                pprint(cls.__ser_field)
                print()

    def serialize(self) -> GeneralizedSexpr:
        # asserts in this function are just to keep mypy happy, __init_serializer ensures correct types

        ret: GeneralizedSexpr = []
        askiff_pre_ser = getattr(self, "_askiff_pre_ser", None)
        _self = askiff_pre_ser() if askiff_pre_ser else self
        append = ret.append
        extend = ret.extend
        for field, (fmode, mode_extra) in _self.__ser_field_positional.items():
            field_val = getattr(_self, field, None)
            if not field_val:
                if field_val in [0.0, 0, "", False]:
                    # The values should not be skipped
                    pass
                elif "." in field:
                    direct_field, _, inner_field = field.partition(".")
                    field_val = getattr(_self, direct_field, None)
                    field_val = field_val and getattr(field_val, inner_field, None)
                    if field_val is None:
                        continue
                else:
                    continue
            assert field_val is not None
            match fmode:
                case SerMode.SERIALIZE:
                    append(field_val.serialize())
                case SerMode.SERIALIZE_OVERRIDE:
                    append(*mode_extra(field_val))  # mode_extra =  custom serialize function
                case SerMode.BOOL:
                    (key_true, key_false) = mode_extra
                    append(key_true if field_val else key_false)
                case SerMode.INT:
                    append(str(field_val))
                case SerMode.FLOAT:
                    append(f"{field_val:.{mode_extra}f}".rstrip("0").rstrip("."))
                case SerMode.FLOAT_NO_TRIM:
                    append(f"{field_val:.{mode_extra}f}")
                case SerMode.STR:
                    append(field_val)
                case SerMode.QSTR:
                    append(Qstr(field_val))
                case SerMode.ENUM:
                    _val = field_val.value
                    if _val:
                        append(_val)
                case SerMode.QENUM:
                    _val = field_val.value
                    if _val:
                        append(Qstr(_val))
                case SerMode.LIST | SerMode.LIST_FLAT:
                    assert isinstance(field_val, Iterable)
                    fmode, mode_extra = mode_extra
                    match fmode:
                        case SerMode.SERIALIZE:
                            extend(f.serialize() for f in field_val)
                        case SerMode.BOOL:
                            (key_true, key_false) = mode_extra
                            extend(key_true if f else key_false for f in field_val)
                        case SerMode.INT:
                            extend(str(f) for f in field_val)
                        case SerMode.FLOAT:
                            extend(f"{f:.{mode_extra}f}".rstrip("0").rstrip(".") for f in field_val)
                        case SerMode.FLOAT_NO_TRIM:
                            extend(f"{f:.{mode_extra}f}" for f in field_val)
                        case SerMode.STR:
                            extend(f for f in field_val)
                        case SerMode.QSTR:
                            extend(Qstr(f) for f in field_val)
                        case SerMode.ENUM:
                            extend(f.value for f in field_val)
                        case SerMode.QENUM:
                            extend(Qstr(f.value) for f in field_val)
                        case _:
                            raise Exception(f"Unreachable {field} {mode_extra}")
                case _:
                    raise Exception(f"Unreachable {field}")

        extend(_self.__extra_positional or ())

        for field, (fname, (fmode, mode_extra)) in _self.__ser_field.items():
            field_val = getattr(_self, field, None)
            if not field_val:
                if field_val in [0.0, 0, "", False]:
                    # The values should not be skipped
                    pass
                # field_val is one of None, [], {}
                elif "." in field:
                    direct_field, _, inner_field = field.partition(".")
                    field_val = getattr(_self, direct_field, None)
                    field_val = field_val and getattr(field_val, inner_field, None)
                    if field_val is None:
                        continue
                else:
                    continue
            assert field_val is not None
            match fmode:
                case SerMode.SERIALIZE:
                    if not mode_extra:  # mode_extra = name attribute from F(..)
                        askiff_key = getattr(field_val, "_askiff_key", None)
                        fname = askiff_key() if callable(askiff_key) else fname
                    # serial id priority: 1. explicit name, 2. _askiff_key method, 3. field name
                    # (note that _askiff_key string is ignored in this case)
                    append((fname, *field_val.serialize()))
                case SerMode.SERIALIZE_OVERRIDE:
                    if not mode_extra:  # mode_extra = name attribute from F(..)
                        askiff_key = getattr(field_val, "_askiff_key", None)
                        fname = askiff_key() if callable(askiff_key) else fname
                    append((fname, *mode_extra(field_val)))  # mode_extra =  custom serialize function
                case SerMode.SERIALIZE_NESTED:
                    askiff_key = getattr(field_val, "_askiff_key", "")
                    askiff_key = askiff_key() if callable(askiff_key) else askiff_key
                    append((fname, ((askiff_key, *field_val.serialize()))))
                case SerMode.BOOL:
                    (key_true, key_false) = mode_extra
                    append(Sexpr((fname, key_true if field_val else key_false)))
                case SerMode.BOOL_FLAG:
                    if field_val ^ mode_extra:  # mode_extra = invert
                        append((fname,))
                case SerMode.BOOL_FLAG_BARE:  # mode_extra = invert
                    if field_val ^ mode_extra:
                        append(fname)
                case SerMode.INT:
                    append((fname, str(field_val)))
                case SerMode.FLOAT:
                    append((fname, f"{field_val:.{mode_extra}f}".rstrip("0").rstrip(".")))  # mode_extra=precision
                case SerMode.FLOAT_NO_TRIM:
                    append((fname, f"{field_val:.{mode_extra}f}"))  # mode_extra=precision
                case SerMode.STR:
                    append((fname, field_val))
                case SerMode.QSTR:
                    append((fname, Qstr(field_val)))
                case SerMode.ENUM:
                    _val = field_val.value
                    if _val:
                        append((fname, _val))
                case SerMode.QENUM:
                    _val = field_val.value
                    if _val:
                        append((fname, Qstr(_val)))
                case SerMode.LIST:
                    assert isinstance(field_val, Iterable)
                    fmode, mode_extra = mode_extra
                    match fmode:
                        case SerMode.SERIALIZE:
                            askiff_key = getattr(field_val, "_askiff_key", None)
                            if askiff_key:
                                fname = askiff_key() if callable(askiff_key) else askiff_key
                            temp = [
                                fname,
                            ]
                            temp_append = temp.append
                            for f in field_val:
                                askiff_key = getattr(f, "_askiff_key", "")
                                n = askiff_key() if callable(askiff_key) else askiff_key
                                temp_append((n, *f.serialize()))
                            append(temp)
                        case SerMode.BOOL:
                            (key_true, key_false) = mode_extra
                            append((fname, *(key_true if f else key_false for f in field_val)))
                        case SerMode.INT:
                            append((fname, *(str(f) for f in field_val)))
                        case SerMode.FLOAT:  # mode_extra=precision
                            append((fname, *(f"{f:.{mode_extra}f}".rstrip("0").rstrip(".") for f in field_val)))
                        case SerMode.FLOAT_NO_TRIM:  # mode_extra=precision
                            append((fname, *(f"{f:.{mode_extra}f}" for f in field_val)))
                        case SerMode.STR:
                            append((fname, *(f for f in field_val)))
                        case SerMode.QSTR:
                            append((fname, *(Qstr(f) for f in field_val)))
                        case SerMode.ENUM:
                            append((fname, *(f.value for f in field_val)))
                        case SerMode.QENUM:
                            append((fname, *(Qstr(f.value) for f in field_val)))
                        case SerMode.LIST:
                            assert isinstance(field_val, Iterable)
                            fmode, mode_extra = mode_extra
                            match fmode:
                                case SerMode.STR:
                                    append((fname, *((fi for fi in f) for f in field_val)))
                                case SerMode.QSTR:
                                    append((fname, *((Qstr(fi) for fi in f) for f in field_val)))
                                case SerMode.ENUM:
                                    append((fname, *((fi.value for fi in f) for f in field_val)))
                                case SerMode.QENUM:
                                    append((fname, *((Qstr(fi.value) for fi in f) for f in field_val)))
                                case _:
                                    raise Exception(f"Unreachable {field} {mode_extra}")
                        case _:
                            raise Exception(f"Unreachable {field} {mode_extra}")
                case SerMode.LIST_FLAT:
                    assert isinstance(field_val, Iterable)
                    fmode, mode_extra = mode_extra
                    match fmode:
                        case SerMode.SERIALIZE:
                            for f in field_val:
                                n = fname
                                if not mode_extra:  # mode_extra = name attribute from F(..)
                                    askiff_key = getattr(f, "_askiff_key", None)
                                    if askiff_key:
                                        n = askiff_key() if callable(askiff_key) else askiff_key
                                append((n, *f.serialize()))
                        case SerMode.BOOL:
                            (key_true, key_false) = mode_extra
                            extend((fname, key_true if f else key_false) for f in field_val)
                        case SerMode.INT:
                            extend((fname, str(f)) for f in field_val)
                        case SerMode.FLOAT:  # mode_extra=precision
                            extend((fname, f"{f:.{mode_extra}f}".rstrip("0").rstrip(".")) for f in field_val)
                        case SerMode.FLOAT_NO_TRIM:  # mode_extra=precision
                            extend((fname, f"{f:.{mode_extra}f}") for f in field_val)
                        case SerMode.STR:
                            extend((fname, f) for f in field_val)
                        case SerMode.QSTR:
                            extend((fname, Qstr(f)) for f in field_val)
                        case SerMode.ENUM:
                            extend((fname, f.value) for f in field_val)
                        case SerMode.QENUM:
                            extend((fname, Qstr(f.value)) for f in field_val)
                        case _:
                            raise Exception(f"Unreachable {field} {mode_extra}")
                case _:
                    raise Exception(f"Unreachable {field} {fmode}")
        extend(_self.__extra or ())

        return ret

    def __init_subclass__(cls, **kwargs: Unpack[SerdeOpt]) -> None:
        type_hints = get_type_hints(cls)
        field_meta, ser_order = cls.__preprocess_fields(type_hints)

        for glob_name, glob_val in kwargs.items():
            for meta in field_meta.values():
                meta.setdefault(glob_name, glob_val)  # type: ignore # ty:ignore[no-matching-overload]

        cls = dataclass(cls)
        cls.__init_serializer(ser_order, type_hints, field_meta)

        cls.__init_deserializer(ser_order, type_hints, field_meta)

        if __debug__:  # __debug__ allows total code removal if PYTHONOPTIMIZE flag is set
            if log.isEnabledFor(TRACE_DIS):
                from dis import dis

                print("\n\n#########################################################")
                print(f"## Disassembled `serialize` function for {cls}:")
                dis(cls.serialize)

                print(f"## Disassembled `deserialize` function for {cls}:")
                dis(cls.deserialize)

                print(f"\n\n## Disassembled `__init__` function for {cls}:")
                dis(cls.__init__)

    @classmethod
    def __preprocess_fields(cls, type_hints: dict[str, type]) -> tuple[dict[str, SerdeOpt], list[str]]:
        """Process typing and defaults of class, configure for dataclass and extract metadata,
        create `_AutoSerde__askiff_dict` for class
        returns (field metadata, field names in serialization order)
        """
        field_meta = {}
        cls.__askiff_dict = {}
        parent_dict = {}
        askiff_order = None

        for parent in reversed(cls.__mro__[1:]):  # first elem is class itself, ignore it
            if hasattr(parent, "_AutoSerde__askiff_dict"):
                # bellows handles case where A->B->C and field is defined in A, but not in B
                filtered_dict = {k: v for k, v in parent.__askiff_dict.items() if not isinstance(v, dataclasses.Field)}  # type: ignore
                askiff_order = getattr(parent, f"_{parent.__name__}__askiff_order", askiff_order)
                parent_dict.update(filtered_dict)

        ser_order = []
        askiff_order = getattr(cls, f"_{cls.__name__}__askiff_order", askiff_order)

        for name, value in (parent_dict | cls.__dict__).items():
            if name.startswith("_") and name[1:] in type_hints:
                ser_order.append(name[1:])
            elif not name.startswith("_") and name in type_hints and ("_" + name) not in cls.__dict__:
                ser_order.append(name)

            if name.startswith("_") or name not in type_hints:
                continue

            typ, type_origin, type_args = _normalize_type(type_hints[name])
            type_hints[name] = typ

            cls.__askiff_dict[name] = value

            if name in type_hints and name not in cls.__annotations__:
                cls.__annotations__[name] = type_hints[name]
            if isinstance(value, F):
                inline, skip = value.options.get("inline"), value.options.get("skip")
                if inline or skip:
                    ser_order.pop()  # skipped or inlined field will not be serialized directly

                if inline:
                    inline_type_hints = get_type_hints(typ)
                    inline_dict = deepcopy(typ._AutoSerde__askiff_dict)
                    inner_childs = getattr(typ, f"_{typ.__name__}__askiff_childs", {})
                    inner_dc_field = getattr(typ, f"_{typ.__name__}__askiff_down_cast_field", {})
                    for ic in inner_childs.values():
                        inline_dict |= getattr(ic, "_AutoSerde__askiff_dict", {})
                        inline_type_hints |= get_type_hints(ic)
                    for inline_field, inline_val in inline_dict.items():  # type:ignore
                        full_id = name + "." + inline_field
                        inline_typ, _, _ = _normalize_type(inline_type_hints[inline_field])
                        type_hints[full_id] = inline_typ
                        field_meta[full_id] = inline_val.options if isinstance(inline_val, F) else {}
                        if inline_field == inner_dc_field:
                            filt_opt = deepcopy(value.options)
                            filt_opt.pop("inline")
                            filt_opt.pop("skip", None)
                            field_meta[full_id] |= filt_opt
                            field_meta[full_id]["inline_basetype"] = typ
                        ser_order.append(full_id)
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
                    value.default = None if type_origin is UnionType and NoneType in type_args else typ
                if callable(value.default):
                    setattr(cls, name, dataclasses.field(default_factory=value.default))
                else:
                    setattr(cls, name, dataclasses.field(default=value.default))
            if name not in field_meta:
                field_meta[name] = {}
        ser_ord = [field for field in askiff_order or ser_order if field in type_hints]
        return field_meta, ser_ord


class AutoSerdeFile(AutoSerde):
    """`AutoSerde` wrapper that targets top (file) level structures"""

    _askiff_key: ClassVar[str]
    _fs_path: Path | None = None
    __version_map: ClassVar[dict[str, str]] = {
        "kicad_pcb": "pcb",
        "kicad_sch": "sch",
        "symbol": "sym",
        "footprint": "fp",
        "sym_lib_table": "lib_table",
        "fp_lib_table": "lib_table",
    }

    @classmethod
    def from_file(cls, path: Path) -> Self:
        sexp = Sexpr.from_file(path)
        askiff_key = cls._askiff_key
        if askiff_key != sexp[0]:
            raise Exception(f"{cls.__name__}: File {path} is not valid ")
        ver_key = cls.__version_map[askiff_key]
        raw_ver = [int(x[1]) for x in sexp[:5] if isinstance(x, list) and x[0] == "version" and isinstance(x[1], str)]
        ver = raw_ver[0] if raw_ver else 0

        vmin, vmax = getattr(Version.MIN, ver_key), getattr(Version.MAX, ver_key)
        if vmin <= ver <= vmax:
            ret = cls.deserialize(Sexpr(sexp[1:]))
            ret._fs_path = path
            return ret
        raise Exception(f"{cls.__name__}: File {path} has unsupported version (Expects: {vmin}-{vmax}, File: {ver})")

    def to_file(self, path: Path | None = None) -> None:
        path = path if path else self._fs_path
        if path is None:
            raise Exception(f"Saving {type(self).__name__} to file requires specifying file system path!")
        Sexpr.to_file(Sexpr((self._askiff_key, *self.serialize())), path)
