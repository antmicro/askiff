from __future__ import annotations

import dataclasses
import logging
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from pprint import pprint
from typing import Any, Self, Unpack, cast, dataclass_transform

from askiff.const import TRACE, TRACE_DIS
from askiff.sexpr import GeneralizedSexpr, Qstr, Sexpr

from .helpers import DeserMode, DeserModWExtra, F, GeneratorParams, SerdeOpt, SerMode, preprocess_cls_fields

log = logging.getLogger()


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
    __ser_field_positional: dict[str, tuple[SerMode, Any, bool]]
    __ser_field: dict[str, tuple[str, tuple[SerMode, Any, bool]]]
    """class_field: (serialized name, (serialization_mode, serialization_mode_args, keep_if_empty))"""
    __deser_field_positional: list[DeserModWExtra]
    __deser_field: dict[str, DeserModWExtra]
    __deser_field_bare_flags: dict[str, DeserModWExtra]

    @classmethod
    def __init_deserializer(
        cls, ser_order: list[str], type_hints: dict[str, type], field_meta: dict[str, SerdeOpt]
    ) -> dict:
        deser_field, deser_field_positional, deser_field_bare_flags = {}, [], {}
        names_kicad = {v.get("name", k).split(".")[-1] for k, v in field_meta.items()}

        def inline_wrap(field: str, mode: DeserMode, extra: Any) -> DeserModWExtra:  # noqa: ANN401
            if "." in field:
                return field, DeserMode.INLINED, (mode, extra)
            return field, mode, extra

        for field in ser_order:
            typ = type_hints[field]
            fparam = GeneratorParams.extract(cls.__name__, typ, field, field_meta, False)
            if fparam.skip:
                continue
            typ = fparam.typ
            fmode: tuple[DeserMode, Any]
            if fparam.agg:
                if fparam.flatten:
                    for var_name, var_type in fparam.agg(inner=fparam.type_args[0]).items():
                        fmode = DeserMode.DESERIALIZE, var_type
                        deser_field[var_name] = inline_wrap(field, DeserMode.LIST_FLAT, (fmode, typ))
                else:
                    deser_field[fparam.fname] = inline_wrap(
                        field, DeserMode.LIST_AGG, (fparam.agg(inner=fparam.type_args[0]), typ)
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
                org_typ = typ
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
                    fmode = DeserMode.BOOL, [[], *([x] for x in fparam.vtrue)]
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
                    fmode = DeserMode.LIST_FLAT if fparam.flatten else DeserMode.LIST, (fmode, org_typ)

            if fparam.bare and fparam.flag:
                for flag in bare_flags:
                    deser_field_bare_flags[flag] = inline_wrap(field, *fmode)
            elif fparam.positional:
                deser_field_positional.append(inline_wrap(field, *fmode))
            else:
                aliases = [alias for alias in fparam.alias if alias not in names_kicad]
                aliases.append(fparam.fname)
                for alias in aliases:
                    deser_field[alias] = inline_wrap(field, *fmode)

        if __debug__:  # __debug__ allows total code removal if PYTHONOPTIMIZE flag is set
            if log.isEnabledFor(TRACE):
                print("\n#########################################################")
                print(f"# Deserialization map for {cls}:")
                pprint(cls.__deser_field_positional)
                pprint(cls.__deser_field)
                print()
        return {
            "_AutoSerde__deser_field": deser_field,
            "_AutoSerde__deser_field_bare_flags": deser_field_bare_flags,
            "_AutoSerde__deser_field_positional": deser_field_positional,
        }

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
                    (mode, mode_extra), constructor = mode_extra
                    if list_obj is None:
                        list_obj = constructor()
                        setattr(ret, field, list_obj)
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
                    agg_map, constructor = mode_extra
                    if list_obj is None:
                        list_obj = constructor()
                        list_obj = []
                        setattr(ret, field, list_obj)
                    list_obj.extend(agg_map.get(n, Sexpr).deserialize(ns) for n, *ns in nodes)

                case DeserMode.LIST:
                    list_obj = getattr(ret, field, None)
                    (mode, mode_extra), constructor = mode_extra
                    if list_obj is None:
                        list_obj = constructor()
                        setattr(ret, field, list_obj)
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
    ) -> dict:
        ser_field, ser_field_positional = {}, {}
        for field in ser_order:
            typ = type_hints[field]
            fparam = GeneratorParams.extract(cls.__name__, typ, field, field_meta, True)
            if fparam.skip:
                continue
            fmode: tuple[SerMode, Any]
            explicit_name = fparam.fmeta.get("name", None)
            keep_empty = False

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
                    fmode = SerMode.BOOL, (fparam.vtrue[0], fparam.vfalse[0])
                    keep_empty = True
                elif typ is int:
                    fmode = SerMode.INT, None
                    keep_empty = True
                elif typ is float and fparam.fmeta.get("keep_trailing", False):
                    fmode = SerMode.FLOAT_NO_TRIM, fparam.fmeta.get("precision", 6)
                    keep_empty = True
                elif typ is float:
                    fmode = SerMode.FLOAT, fparam.fmeta.get("precision", 6)
                    keep_empty = True
                elif issubclass(typ, str):
                    no_quote = fparam.fmeta.get("unquoted", False)
                    fmode = (SerMode.STR if no_quote else SerMode.QSTR), None
                    keep_empty = True
                else:
                    raise Exception(f"{cls}.__init_serializer: Unsupported type: {field}: {typ}")

                if fparam.list_of_lists:
                    fmode = SerMode.LIST, fmode
                    keep_empty = False
                if fparam.is_list:
                    fmode = SerMode.LIST_FLAT if fparam.flatten else SerMode.LIST, fmode
                    keep_empty = False
            keep_empty = fparam.fmeta.get("keep_empty", keep_empty)
            if fparam.positional:
                ser_field_positional[field] = (*fmode, keep_empty)
            else:
                ser_field[field] = fparam.fname, (*fmode, keep_empty)
        if __debug__:  # __debug__ allows total code removal if PYTHONOPTIMIZE flag is set
            if log.isEnabledFor(TRACE):
                print("\n#########################################################")
                print(f"# Serialization map for {cls}:")
                pprint(ser_field_positional)
                pprint(ser_field)
                print()
        return {"_AutoSerde__ser_field": ser_field, "_AutoSerde__ser_field_positional": ser_field_positional}

    def serialize(self) -> GeneralizedSexpr:
        # asserts in this function are just to keep mypy happy, __init_serializer ensures correct types

        ret: GeneralizedSexpr = []
        askiff_pre_ser = getattr(self, "_askiff_pre_ser", None)
        _self = askiff_pre_ser() if askiff_pre_ser else self
        append = ret.append
        extend = ret.extend
        for field, (fmode, mode_extra, force_empty) in _self.__ser_field_positional.items():
            field_val = getattr(_self, field, None)
            if not field_val:
                if "." in field:
                    direct_field, _, inner_field = field.partition(".")
                    field_val = getattr(_self, direct_field, None)
                    field_val = field_val and getattr(field_val, inner_field, None)
                if field_val is None or (not field_val and not force_empty):
                    continue

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

        for field, (fname, (fmode, mode_extra, force_empty)) in _self.__ser_field.items():
            field_val = getattr(_self, field, None)
            if not field_val:
                if "." in field:
                    direct_field, _, inner_field = field.partition(".")
                    field_val = getattr(_self, direct_field, None)
                    field_val = field_val and getattr(field_val, inner_field, None)
                if field_val is None or (not field_val and not force_empty):
                    continue
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
        type_hints, field_meta, ser_order = preprocess_cls_fields(cls)

        for glob_name, glob_val in kwargs.items():
            for meta in field_meta.values():
                meta.setdefault(glob_name, glob_val)  # type: ignore # ty:ignore[no-matching-overload]

        file_versions = set()  # default version without additional modyfications
        for fmeta in field_meta.values():
            file_versions |= set(fmeta.get("_version_options", {}).keys())

        cls = dataclass(cls)

        default_opts: dict[str, list | dict] = cls.__init_serializer(ser_order, type_hints, field_meta)
        default_opts |= cls.__init_deserializer(ser_order, type_hints, field_meta)
        _askiff_opts_default[cls] = default_opts
        for dict_name, val in default_opts.items():
            setattr(cls, dict_name, val)

        if file_versions:
            _askiff_opts_version_map[cls] = {}
            for ver in sorted(file_versions):
                _field_meta = deepcopy(field_meta)
                for fmeta in _field_meta.values():
                    field_versions = fmeta.get("_version_options", {})
                    for opt_ver, opt in field_versions.items():
                        if opt_ver >= ver:
                            fmeta.update(opt)
                _askiff_opts_version_map[cls][ver] = cls.__init_serializer(ser_order, type_hints, _field_meta)
                _askiff_opts_version_map[cls][ver] |= cls.__init_deserializer(ser_order, type_hints, _field_meta)

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


_askiff_opts_version_map: dict[type[AutoSerde], dict[int, dict[str, Any]]] = {}
"""class: {file_version: {option_dict_name: option_dict}}  (file_versions in growing order)"""
_askiff_opts_default: dict[type[AutoSerde], dict[str, Any]] = {}
"""class: {option_dict_name: option_dict}"""
