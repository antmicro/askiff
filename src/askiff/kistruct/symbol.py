from __future__ import annotations  # noqa: I001
from copy import copy

from typing import TYPE_CHECKING, Any, ClassVar, cast

from askiff.auto_serde import AutoSerde, AutoSerdeAgg, AutoSerdeEnum, AutoSerdeFile, F
from askiff.const import Version
from askiff.kistruct.common import (
    Effects,
    EmbeddedFile,
    LibId,
    LibTable,
    PinType,
    Position,
    Property,
    PropertyList,
    Uuid,
)
from askiff.kistruct.gritems import GrItemSch
from askiff.sexpr import GeneralizedSexpr, Qstr

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore


class SymProperty(Property):
    show_name: bool | None = F(after="position").version(Version.K9.sym, flag=True)
    do_not_autoplace: bool | None = None

    def _askiff_post_deser(self) -> None:
        if self.effects and self.effects.hide is not None:
            self.hide = self.effects.hide

    def _askiff_pre_ser(self) -> Property:
        _self = copy(self)
        if AutoSerdeFile._version <= Version.K9.sym:
            _self.effects = _self.effects or Effects()
            _self.effects.hide = self.hide
            _self.hide = None
        return _self


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


class Pin(AutoSerde):
    _askiff_key: ClassVar[str] = "pin"
    type: PinType = F(PinType.PASSIVE, positional=True, unquoted=True)
    shape: PinShape = F(PinShape.LINE, positional=True)
    position: Position = F(name="at")
    length: float = 1.27
    hide: bool | None = None


class SymbolPartial(AutoSerde):
    _askiff_key: ClassVar[str] = "symbol"

    lib_id: LibId = F(positional=True)
    """Defines symbol name and library link"""

    unit_name: str | None = None
    """Optional custom name for unit"""

    graphic_items: AutoSerdeAgg[GrItemSch] = F(flatten=True)
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


class LibSymbol(AutoSerde):
    _askiff_key: ClassVar[str] = "symbol"

    lib_id: LibId = F(positional=True)
    """Defines symbol name and library link"""

    extends: str | None = None
    body_styles: list[str] | None = F(serialize=lambda val: (v if v in ["demorgan"] else Qstr(v) for v in val))
    power: SymbolPower | None = F().version(
        Version.K9.sch, serialize=SymbolPower.serialize_k9, deserialize=SymbolPower.deserialize_k9
    )
    exclude_from_sim: bool | None = None
    in_bom: bool | None = None
    on_board: bool | None = None
    in_pos_files: bool | None = None

    duplicate_pin_numbers_are_jumpers: bool | None = None
    """If true DRC will consider pins with the same number as electrically connected"""

    jumper_pin_groups: list[list[str]] = F()
    """Pin numbers that shall be considered as internally connected"""

    properties: PropertyList[SymProperty] = F(name="property", flatten=True)
    """Properties of the symbol, such as reference, value, datasheet, ..."""

    symbols: list[SymbolPartial] = F(flatten=True, name="symbol")
    """Symbol components: symbol units * symbol styles (+ common elements)"""

    embedded_fonts: bool | None = None
    """Indicates whether there are fonts embedded into this component"""

    embedded_files: list[EmbeddedFile] = F()
    """Stores data of embedded files, eg. fonts, 3d-models"""


class SymbolSchematic(AutoSerde):
    _askiff_key: ClassVar[str] = "symbol"

    lib_id: LibId = F(positional=True)
    """Defines symbol name and library link"""

    locked: bool | None = F(after="lib_id")
    """Flag to indicate the footprint cannot be edited"""

    position: Position | None = F(name="at")
    """Defines the X and Y coordinates and rotation of the footprint"""

    properties: PropertyList[SymProperty] = F(name="property", flatten=True)
    """Properties of the symbol, such as reference, value, datasheet, ..."""

    uuid: Uuid | None = F()

    # instances: ? = F()


class SymbolFile(AutoSerdeFile):
    _askiff_key: ClassVar[str] = "kicad_symbol_lib"

    version: int | None = F(Version.DEFAULT.sym, after="lib_id")
    """Defines the file format version"""

    generator: str | None = Version.generator
    """Defines the program used to write the file"""

    generator_version: str | None = Version.generator_ver
    """Defines the program version used to write the file"""

    symbols: list[LibSymbol] = F(flatten=True, name="symbol")
    """Symbols stored in this file (one, when in symbol-per-file library)"""


class LibTableSym(LibTable, AutoSerdeFile):
    _askiff_key: ClassVar[str] = "sym_lib_table"
