from __future__ import annotations

from copy import copy
from typing import TYPE_CHECKING, Any, ClassVar, cast

from askiff._auto_serde import AutoSerde, AutoSerdeAgg, AutoSerdeEnum, AutoSerdeFile, F
from askiff._sexpr import GeneralizedSexpr, Qstr
from askiff.common import (
    Effects,
    EmbeddedFile,
    Font,
    LibId,
    LibraryTable,
    PinType,
    Position,
    Property,
    PropertyList,
    Uuid,
)
from askiff.const import Version
from askiff.gritems import GrItemSym

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore


class SymProperty(Property):
    """SymProperty stores symbol metadata such as reference, value, and datasheet,
    with additional fields for symbol/flow-specific metadata"""

    show_name: bool | None = F(after="hide")
    """Whether the symbol property name is shown"""
    do_not_autoplace: bool | None = None
    """Whether the symbol property should not be automatically placed"""

    def _askiff_post_deser(self) -> None:
        if self.effects and self.effects.hide is not None:
            self.hide = self.effects.hide

    def _askiff_pre_ser(self) -> Property:
        """Preprocesses the instance before serialization to ensure compatibility with older KiCad schematic versions.
        For versions <= K9.sch, it initializes default Effects if missing
        and migrates the `hide` flag from the top-level field to the Effects subfield."""
        _self = copy(self)
        if AutoSerdeFile._version <= Version.K9.sch:
            _self.effects = _self.effects or Effects()
            _self.effects.hide = self.hide
            _self.hide = None
        return _self


class _SymPropertyLibOrder(SymProperty):
    # order in sym library definitions is different than, e.g., schematic instances
    """Stub class used internally to ensure proper formatting

    Represents a symbol property for library order definitions in KiCad schematic files.
    Adjusts serialization to match KiCad formatting in library context"""

    show_name: bool | None = F(after="position").version(Version.K9.sch, flag=True)
    _do_not_autoplace = F()

    @staticmethod
    def list_ser(val: PropertyList[SymProperty]) -> GeneralizedSexpr:
        """Serializes a list of symbol properties into sexpr AST"""
        for v in val:
            v._AutoSerde__ser_field = _SymPropertyLibOrder._AutoSerde__ser_field  # type: ignore # ty:ignore[unresolved-attribute]
        return tuple(("property", *v.serialize()) for v in val)


class PinShape(str, AutoSerdeEnum):
    """PinShape represents the visual shape of a pin in a KiCad symbol"""

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
    """Represents definition of an alternative pin function"""

    _askiff_key: ClassVar[str] = "alternate"
    name: str = F(positional=True)
    """Alternative pin name"""
    type: PinType = F(PinType.PASSIVE, positional=True, unquoted=True)
    """Pin logic type"""
    shape: PinShape = F(PinShape.LINE, positional=True)
    """Visual shape of the pin"""


class PinName(AutoSerde):
    """Represents a pin name in a KiCad schematic symbol."""

    value: str = F(positional=True)
    """Pin name text value"""

    font: Font = F(nested=True, name="effects")
    """Font properties for the pin name text."""


class PinNumber(AutoSerde):
    """Represents a pin number in a KiCad schematic symbol."""

    @staticmethod
    def __value_deserialize(sexpr: GeneralizedSexpr) -> list[str]:
        """Converts a sexpr string representation of pin numbers into a list of strings"""
        if not isinstance(sexpr, str):
            raise TypeError("First element of `PinNumber` is expected to be a string")
        return sexpr.strip("[]").split(",")

    @staticmethod
    def __value_serialize(value: list[str]) -> GeneralizedSexpr:
        """Converts a list of pin number strings into a sexpr-compatible format.
        Handles empty lists, single values, and multiple values by wrapping them in brackets"""
        match len(value):
            case 0:
                return (Qstr(),)
            case 1:
                return (Qstr(value[0]),)
            case _:
                return (Qstr("[" + ",".join(value) + "]"),)

    value: list[str] = F(positional=True, serialize=__value_serialize, deserialize=__value_deserialize)
    """Pin number(s)"""

    font: Font = F(nested=True, name="effects")
    """Font settings for the pin number including size and styling."""


class Pin(AutoSerde):
    """Represents a pin in a KiCad symbol,
    defining its configuration as type, shape, position, length, visibility, name, number, and alternative functions.
    """

    _askiff_key: ClassVar[str] = "pin"
    type: PinType = F(PinType.PASSIVE, positional=True, unquoted=True)
    """Pin logic type"""
    shape: PinShape = F(PinShape.LINE, positional=True)
    """Visual shape of the pin in the symbol."""
    position: Position = F(name="at")
    """Pin position in symbol space"""
    length: float = 1.27
    """Pin length in millimeters."""
    hide: bool | None = F().version(Version.K8.sch, bare=True, flag=True, after="length")
    """Whether the pin name is hidden."""
    name: PinName = F()
    """Pin name text value and font properties"""
    number: PinNumber = F()
    """Pin number(s)"""
    alternative_functions: list[PinAlternative] = F(flatten=True, name="alternate")
    """Alternative pin configurations/functions for the symbol pin."""


class SymbolAspect(AutoSerde):
    """Represents part of graphic representation of symbol.

    Each `SymbolAspect` instance corresponds to single symbol unit, alternative style or common part between them
    """

    _askiff_key: ClassVar[str] = "symbol"

    lib_id: LibId = F(positional=True)
    """Defines symbol name and library link"""

    unit_name: str | None = None
    """Unit name for the symbol, if defined"""

    graphic_items: AutoSerdeAgg[GrItemSym] = F(flatten=True)
    """Graphic items belonging to the symbol such as lines, circles, and texts"""

    pins: list[Pin] = F(name="pin", flatten=True)
    """List of symbol pins"""


class SymbolPower(str, AutoSerdeEnum):
    """Enum representing power flag type.
    Used in symbol definitions to specify whether a symbol is power is global or local power flag"""

    GLOBAL = "global"
    LOCAL = "local"

    def serialize_k9(self) -> GeneralizedSexpr:
        return ()

    def deserialize_k9(self) -> SymbolPower:
        return SymbolPower.GLOBAL  # type: ignore


class SymbolDefinitionPinNames(AutoSerde):
    """Controls pin names of a KiCad symbol library entry, handling their visibility and offset"""

    offset: float | None = None
    """Pin name offset from pin"""
    hide: bool | None = F().version(Version.K8.sch, bare=True, flag=True, after="__begin__")
    """Whether the pin names are hidden"""

    def __bool__(self) -> bool:
        return self.hide or self.offset is not None


class SymbolDefinitionPinNumbers(AutoSerde):
    """Controls pin numbers of a KiCad symbol library entry, handling their visibility"""

    hide: bool = F().version(Version.K8.sch, bare=True, flag=True, after="__begin__")
    """Whether pin numbers are hidden in the schematic symbol."""

    def __bool__(self) -> bool:
        return self.hide


class SymbolDefinition(AutoSerde):
    """A library symbol definition, representing a component symbol with associated metadata, pins, and properties"""

    _askiff_key: ClassVar[str] = "symbol"

    lib_id: LibId = F(positional=True)
    """Symbol name and library link identifier"""

    extends: str | None = None
    """Library id of a symbol this symbol extends"""
    body_styles: list[str] | None = F(serialize=lambda val: (v if v in ["demorgan"] else Qstr(v) for v in val))
    """User defined names for symbol body styles"""
    power: SymbolPower | None = F().version(
        Version.K9.sch, serialize=SymbolPower.serialize_k9, deserialize=SymbolPower.deserialize_k9, keep_empty=True
    )
    """Whether the symbol is a global or local power symbol."""
    pin_numbers: SymbolDefinitionPinNumbers = F()
    """Whether pin numbers are shown in the schematic symbol."""
    pin_names: SymbolDefinitionPinNames = F()
    """Pin names configuration including visibility and offset settings."""
    exclude_from_sim: bool | None = None
    """Whether component is excluded from simulation"""
    in_bom: bool | None = None
    """Whether component is included in bill of materials"""
    on_board: bool | None = None
    """Whether component is placed on a board."""
    in_pos_files: bool | None = None
    """Whether component is included in position files."""

    duplicate_pin_numbers_are_jumpers: bool | None = None
    """Whether duplicate pin numbers are treated as electrically connected jumpers during DRC checks."""

    jumper_pin_groups: list[list[str]] = F()
    """Pin numbers that shall be considered as internally connected"""

    properties: PropertyList[SymProperty] = F(name="property", flatten=True, serialize=_SymPropertyLibOrder.list_ser)
    """Symbol properties including reference, value, and datasheet information"""

    aspects: list[SymbolAspect] = F(flatten=True, name="symbol")
    """Symbol graphical parts: symbol units * symbol styles (+ common elements)"""

    embedded_fonts: bool | None = F().version(Version.K8.pcb, skip=True)
    """Whether fonts are embedded into this symbol"""

    embedded_files: list[EmbeddedFile] = F().version(Version.K8.pcb, skip=True)
    """Embedded files data including fonts and datasheets."""


class Mirror(str, AutoSerdeEnum):
    """Mirror represents a reflection direction for KiCad objects,
    used to control mirroring behavior along the X or Y axis."""

    X = "x"
    Y = "y"


class SchematicSheetPath(AutoSerde):
    """Identifies location in schematic sheets hierarchy"""

    segments: list[Uuid] = F()
    """UUIDs identifying the hierarchical path to the sheet."""

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
    """Represents a schematic variant definition within a KiCad schematic file,
    specifying BOM, position file, and simulation settings in this assembly variant"""

    name: str = F()
    """Name of the variant"""
    dnp: bool | None = None
    """Whether symbol in this variant is marked as do-not-place"""
    exclude_from_sim: bool | None = None
    """Whether symbol in this variant is excluded from simulation models"""
    in_bom: bool | None = None
    """Whether symbol in this variant is included in the bill of materials"""
    in_pos_files: bool | None = F(None).version(Version.K9.sch, skip=True)
    """Whether symbol in this variant is included in position files generation"""


class ObjectSchematicInstance(AutoSerde):
    """Represents a sheet or symbol instance within a KiCad schematic"""

    _askiff_key: ClassVar[str] = "path"
    path: SchematicSheetPath = F(positional=True)
    """Schematic sheet path"""
    variant: ObjectSchematicVariant | None = F()
    """Describes objects different configurations depending on assembly variant"""


class SymbolSchematicInstance(ObjectSchematicInstance):
    """Represents a schematic symbol instance within a KiCad project,
    linking to a schematic sheet path and containing instance-specific data like reference and unit."""

    _askiff_key: ClassVar[str] = "path"
    reference: str = F(after="path")
    """Symbol instance reference designator."""
    unit: int = F()
    """Symbol instance unit number"""


class SymbolSchematicProject(AutoSerde):
    """Describes instances of this symbol inside project"""

    _askiff_key: ClassVar[str] = "project"
    project_name: str = F(positional=True)
    """Name of project"""
    instances: list[SymbolSchematicInstance] = F(flatten=True, name="path")
    """Instances of this symbol in this `project`"""


class SymbolSchematicPin(AutoSerde):
    """Represents a pin in a symbol."""

    _askiff_key: ClassVar[str] = "pin"
    number: str = F(positional=True)
    """Pin number"""
    uuid: Uuid = F()
    """Unique identifier"""
    alternate: str | None = F()
    """Alternate function enabled for instance pin"""


class SymbolSchematic(AutoSerde):
    """Class representing a instance of a symbol in schematic"""

    _askiff_key: ClassVar[str] = "symbol"

    lib_id: LibId = F()
    """Defines symbol name and library link
    
    References :class:`askiff.symbol.SymbolDefinition` that defines graphic representation"""

    locked: bool | None = F(after="lib_id")
    """Whether the symbol is locked against modifications."""

    position: Position | None = F(name="at")
    """Position and rotation of the symbol in the schematic"""

    mirror: Mirror | None = None
    """Whether the symbol is mirrored along the X or Y axis."""

    unit: int = 1
    """Symbol unit (of multi unit symbols)"""
    body_style: int = F(1).version(Version.K9.sch, name="convert", serialize=lambda x: x if x != 1 else None)
    """Symbol body style"""

    exclude_from_sim: bool = True
    """Whether component is excluded from simulation."""
    in_bom: bool = True
    """Whether component is included in bill of materials."""
    on_board: bool = True
    """Whether component is represented on the board."""
    in_pos_files: bool = F(True).version(Version.K9.sch, skip=True)
    """Whether component is included in position files."""
    dnp: bool = False
    """Whether component is excluded from production data."""
    fields_autoplaced: bool | None = None
    """Whether symbol fields are auto-placed"""

    uuid: Uuid = F()
    """Unique identifier"""

    properties: PropertyList[SymProperty] = F(name="property", flatten=True)
    """Schematic symbol properties including reference, value, and datasheet"""

    pins: list[SymbolSchematicPin] = F(flatten=True, name="pin")
    """Pin instances in the schematic symbol."""

    instances: list[SymbolSchematicProject] = F()
    """Defines location of this symbol in schematic project"""

    _lib_name: str | None = F(skip=True).version(Version.K8.sch, skip=False)


class SymbolFile(AutoSerdeFile):
    """A file containing KiCad symbol library data, used for storing one or more component symbol definitions."""

    _askiff_key: ClassVar[str] = "kicad_symbol_lib"

    version: int = F(Version.DEFAULT.sym, after="lib_id")
    """Symbol file format version number."""

    generator: str = Version.generator
    """Program that generated the file."""

    generator_version: str = Version.generator_ver
    """Version of program that generated the file."""

    symbols: list[SymbolDefinition] = F(flatten=True, name="symbol")
    """Symbols stored in this file (one, when in symbol-per-file library)."""


class SymbolLibraryTable(LibraryTable, AutoSerdeFile):
    """Symbol library table file handler.
    Provides typed access to library definitions and their properties"""

    _askiff_key: ClassVar[str] = "sym_lib_table"
