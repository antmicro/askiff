from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Final, cast

from askiff.auto_serde import AutoSerde, AutoSerdeAgg, AutoSerdeEnum, AutoSerdeFile, F
from askiff.const import Version
from askiff.kistruct.common import (
    EmbeddedFile,
    LibId,
    LibTable,
    Position,
    Property,
    PropertyList,
    Uuid,
)
from askiff.kistruct.gritems import GrItemSch

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore


class BaseSymbol(AutoSerde):
    _askiff_key: ClassVar[str] = "symbol"

    lib_id: LibId = F(positional=True)
    """Defines symbol name and library link"""

    graphic_items: AutoSerdeAgg[GrItemSch] = F(flatten=True)
    """List of graphical objects (lines, circles, arcs, texts, ...) in the footprint"""


class LibSymbol(AutoSerde):
    _askiff_key: ClassVar[str] = "symbol"

    lib_id: LibId = F(positional=True)
    """Defines symbol name and library link"""

    duplicate_pin_numbers_are_jumpers: bool | None = F()
    """If true DRC will consider pins with the same number as electrically connected"""

    jumper_pin_groups: list[list[str]] = F()
    """Pin numbers that shall be considered as internally connected"""

    properties: PropertyList[Property] = F(name="property", flatten=True)
    """Properties of the symbol, such as reference, value, datasheet, ..."""

    symbols: list[BaseSymbol] = F(flatten=True, name="symbol")
    """Symbol components: symbol units * symbol styles (+ common elements)"""

    embedded_fonts: bool = F()
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

    uuid: Uuid | None = F()

    # instances: ? = F()


class SymbolFile(AutoSerdeFile):
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
