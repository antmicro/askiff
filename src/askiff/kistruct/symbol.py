from __future__ import annotations

from copy import copy
from typing import TYPE_CHECKING, Any, ClassVar, cast

from askiff.auto_serde import AutoSerde, AutoSerdeAgg, AutoSerdeEnum, AutoSerdeFile, F
from askiff.const import Version
from askiff.kistruct.common import (
    Effects,
    EmbeddedFile,
    Font,
    LibId,
    LibTable,
    PinType,
    Position,
    Property,
    PropertyList,
    Uuid,
)
from askiff.kistruct.gritems import GrItemSym
from askiff.sexpr import GeneralizedSexpr, Qstr

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore


class SymProperty(Property):
    show_name: bool | None = F(after="hide")
    do_not_autoplace: bool | None = None

    def _askiff_post_deser(self) -> None:
        if self.effects and self.effects.hide is not None:
            self.hide = self.effects.hide

    def _askiff_pre_ser(self) -> Property:
        _self = copy(self)
        if AutoSerdeFile._version <= Version.K9.sch:
            _self.effects = _self.effects or Effects()
            _self.effects.hide = self.hide
            _self.hide = None
        return _self


class _SymPropertyLibOrder(SymProperty):
    # order in sym library definitions is different than, e.g., schematic instances
    show_name: bool | None = F(after="position").version(Version.K9.sch, flag=True)
    _do_not_autoplace = F()

    @staticmethod
    def list_ser(val: PropertyList[SymProperty]) -> GeneralizedSexpr:
        for v in val:
            v._AutoSerde__ser_field = _SymPropertyLibOrder._AutoSerde__ser_field  # type: ignore # ty:ignore[unresolved-attribute]
        return tuple(("property", *v.serialize()) for v in val)


class PinShape(str, AutoSerdeEnum):
    LINE = "line"
    CLOCK = "clock"
    INVERTED_CLOCK = "inverted_clock"
    INPUT_LOW = "input_low"
    CLOCK_LOW = "clock_low"
    OUTPUT_LOW = "output_low"
    EDGE_CLOCK_HIGH = "edge_clock_high"
    NON_LOGIC = "non_logic"
    INVERTED = "inverted"


class PinAlternative(AutoSerde):
    _askiff_key: ClassVar[str] = "alternate"
    name: str = F(positional=True)
    type: PinType = F(PinType.PASSIVE, positional=True, unquoted=True)
    shape: PinShape = F(PinShape.LINE, positional=True)


class PinName(AutoSerde):
    value: str = F(positional=True)
    """Value of the property"""

    font: Font = F(nested=True, name="effects")
    """Defines text size"""


class PinNumber(AutoSerde):
    @staticmethod
    def __value_deserialize(sexpr: GeneralizedSexpr) -> list[str]:
        if not isinstance(sexpr, str):
            raise TypeError("First element of `PinNumber` is expected to be a string")
        return sexpr.strip("[]").split(",")

    @staticmethod
    def __value_serialize(value: list[str]) -> GeneralizedSexpr:
        match len(value):
            case 0:
                return (Qstr(),)
            case 1:
                return (Qstr(value[0]),)
            case _:
                return (Qstr("[" + ",".join(value) + "]"),)

    value: list[str] = F(positional=True, serialize=__value_serialize, deserialize=__value_deserialize)
    """Value of the property"""

    font: Font = F(nested=True, name="effects")
    """Defines text size"""


class Pin(AutoSerde):
    _askiff_key: ClassVar[str] = "pin"
    type: PinType = F(PinType.PASSIVE, positional=True, unquoted=True)
    shape: PinShape = F(PinShape.LINE, positional=True)
    position: Position = F(name="at")
    length: float = 1.27
    hide: bool | None = None
    name: PinName = F()
    number: PinNumber = F()
    alternative_functions: list[PinAlternative] = F(flatten=True, name="alternate")


class SymbolPartial(AutoSerde):
    _askiff_key: ClassVar[str] = "symbol"

    lib_id: LibId = F(positional=True)
    """Defines symbol name and library link"""

    unit_name: str | None = None
    """Optional custom name for unit"""

    graphic_items: AutoSerdeAgg[GrItemSym] = F(flatten=True)
    """List of graphical objects (lines, circles, arcs, texts, ...) in the footprint"""

    pins: list[Pin] = F(name="pin", flatten=True)
    """List of component pins"""


class SymbolPower(str, AutoSerdeEnum):
    GLOBAL = "global"
    LOCAL = "local"

    def serialize_k9(self) -> GeneralizedSexpr:
        return ()

    def deserialize_k9(self) -> SymbolPower:
        return SymbolPower.GLOBAL  # type: ignore


class LibSymbolPinNames(AutoSerde):
    offset: float | None = None
    hide: bool | None = None

    def __bool__(self) -> bool:
        return self.hide or self.offset is not None


class LibSymbolPinNumbers(AutoSerde):
    hide: bool = False

    def __bool__(self) -> bool:
        return self.hide


class LibSymbol(AutoSerde):
    _askiff_key: ClassVar[str] = "symbol"

    lib_id: LibId = F(positional=True)
    """Defines symbol name and library link"""

    extends: str | None = None
    body_styles: list[str] | None = F(serialize=lambda val: (v if v in ["demorgan"] else Qstr(v) for v in val))
    power: SymbolPower | None = F().version(
        Version.K9.sch, serialize=SymbolPower.serialize_k9, deserialize=SymbolPower.deserialize_k9, keep_empty=True
    )
    pin_numbers: LibSymbolPinNumbers = F()
    pin_names: LibSymbolPinNames = F()
    exclude_from_sim: bool | None = None
    in_bom: bool | None = None
    on_board: bool | None = None
    in_pos_files: bool | None = None

    duplicate_pin_numbers_are_jumpers: bool | None = None
    """If true DRC will consider pins with the same number as electrically connected"""

    jumper_pin_groups: list[list[str]] = F()
    """Pin numbers that shall be considered as internally connected"""

    properties: PropertyList[SymProperty] = F(name="property", flatten=True, serialize=_SymPropertyLibOrder.list_ser)
    """Properties of the symbol, such as reference, value, datasheet, ..."""

    symbols: list[SymbolPartial] = F(flatten=True, name="symbol")
    """Symbol components: symbol units * symbol styles (+ common elements)"""

    embedded_fonts: bool | None = None
    """Indicates whether there are fonts embedded into this component"""

    embedded_files: list[EmbeddedFile] = F()
    """Stores data of embedded files, eg. fonts, 3d-models"""


class Mirror(str, AutoSerdeEnum):
    X = "x"
    Y = "y"


class SchematicSheetPath(AutoSerde):
    segments: list[Uuid] = F()

    def serialize(self) -> GeneralizedSexpr:
        return (Qstr("/" + "/".join(self.segments)),)

    @classmethod
    def deserialize(cls, sexp: GeneralizedSexpr) -> SchematicSheetPath:
        sexp = sexp if isinstance(sexp, str) else sexp[0]
        if not isinstance(sexp, str):
            raise TypeError("Schematic Sheet Path expected to be a string")
        spl = sexp.removeprefix("/").split("/")
        return SchematicSheetPath([Uuid(s) for s in spl])


class ObjectSchematicVariant(AutoSerde):
    name: str = F()
    dnp: bool | None = None
    exclude_from_sim: bool | None = None
    in_bom: bool | None = None
    in_pos_files: bool | None = F(None).version(Version.K9.sch, skip=True)


class ObjectSchematicInstance(AutoSerde):
    _askiff_key: ClassVar[str] = "path"
    path: SchematicSheetPath = F(positional=True)
    variant: ObjectSchematicVariant | None = F()


class SymbolSchematicInstance(ObjectSchematicInstance):
    _askiff_key: ClassVar[str] = "path"
    reference: str = F(after="path")
    unit: int = F()


class SymbolSchematicProject(AutoSerde):
    _askiff_key: ClassVar[str] = "project"
    project_name: str = F(positional=True)
    instances: list[SymbolSchematicInstance] = F(flatten=True, name="path")


class SymbolSchematicPin(AutoSerde):
    _askiff_key: ClassVar[str] = "pin"
    number: str = F(positional=True)
    uuid: Uuid = F()
    alternate: str | None = F()
    """Alternate function enabled for instance pin"""


class SymbolSchematic(AutoSerde):
    _askiff_key: ClassVar[str] = "symbol"

    lib_id: LibId = F()
    """Defines symbol name and library link"""

    locked: bool | None = F(after="lib_id")
    """Flag to indicate the footprint cannot be edited"""

    position: Position | None = F(name="at")
    """Defines the X and Y coordinates and rotation of the footprint"""

    mirror: Mirror | None = None

    unit: int = 1
    body_style: int = F(1).version(Version.K9.sch, name="convert", serialize=lambda x: x if x != 1 else None)

    exclude_from_sim: bool = True
    in_bom: bool = True
    on_board: bool = True
    in_pos_files: bool = F(True).version(Version.K9.sch, skip=True)
    dnp: bool = False
    fields_autoplaced: bool | None = None

    uuid: Uuid = F()

    properties: PropertyList[SymProperty] = F(name="property", flatten=True)
    """Properties of the symbol, such as reference, value, datasheet, ..."""

    pins: list[SymbolSchematicPin] = F(flatten=True, name="pin")

    instances: list[SymbolSchematicProject] = F()


class SymbolFile(AutoSerdeFile):
    _askiff_key: ClassVar[str] = "kicad_symbol_lib"

    version: int = F(Version.DEFAULT.sym, after="lib_id")
    """Defines the file format version"""

    generator: str = Version.generator
    """Defines the program used to write the file"""

    generator_version: str = Version.generator_ver
    """Defines the program version used to write the file"""

    symbols: list[LibSymbol] = F(flatten=True, name="symbol")
    """Symbols stored in this file (one, when in symbol-per-file library)"""


class LibTableSym(LibTable, AutoSerdeFile):
    _askiff_key: ClassVar[str] = "sym_lib_table"
