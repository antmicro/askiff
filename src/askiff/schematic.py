from typing import TYPE_CHECKING, Any, ClassVar, Final, cast

from askiff._auto_serde import AutoSerde, AutoSerdeEnum, AutoSerdeFile, F
from askiff.common import (
    BasePoly,
    Color,
    Effects,
    EmbeddedFile,
    Group,
    Paper,
    Position,
    PropertyList,
    Size,
    Stroke,
    TitleBlock,
    Uuid,
)
from askiff.const import Version
from askiff.gritems import GrItemSch, GrPolySch, GrTableSch
from askiff.symbol import ObjectSchematicInstance, SymbolDefinition, SymbolSchematic, SymProperty

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore


class BusAlias(AutoSerde):
    """Represents a bus alias definition in a KiCad schematic file.
    Used to define named groups of signals that can be referenced together in schematic labels"""

    name: str = F(positional=True)
    """Name of the bus alias definition"""
    members: list[str] = F(keep_empty=True)
    """Members of the bus alias group"""


class LabelShape(str, AutoSerdeEnum):
    """Enumeration of label shape types"""

    PASSIVE = "passive"
    INPUT = "input"
    OUTPUT = "output"
    BIDIRECTIONAL = "bidirectional"
    TRI_STATE = "tri_state"


class LabelBase(AutoSerde):
    """Base class for schematic label objects, providing common fields for name, position, effects, and properties."""

    name: str = F(positional=True)
    """Explicit signal name, that this label forces"""
    position: Position = F(name="at")
    """Position of the label on the schematic canvas"""
    fields_autoplaced: bool | None = None
    """Whether fields are auto-placed"""
    effects: Effects = F()
    """Text formatting properties including font, justification, and visibility"""
    uuid: Uuid = F()
    """Unique identifier"""
    properties: PropertyList[SymProperty] = F(lambda: PropertyList(SymProperty), name="property", flatten=True)
    """Additional label properties such as net-class and intersheet-references"""


class LabelLocal(LabelBase):
    """Local label object in a KiCad schematic.
    Used to define local labels within schematic sheets for internal connections or annotations."""

    pass


class LabelGlobal(LabelBase):
    """Global label object in KiCad schematics"""

    shape: LabelShape = F(LabelShape.PASSIVE, after="name")
    """Label graphical shape"""


class LabelHierarchical(LabelBase):
    """Label representing a hierarchical label in a KiCad schematic"""

    shape: LabelShape = F(LabelShape.PASSIVE, after="name")
    """Label graphical shape"""


class RuleArea(AutoSerde):
    """Rule area definition, allowing geographical assignment of symbol/net properties"""

    exclude_from_sim: bool | None = None
    """Whether items inside region are excluded from simulation output."""
    in_bom: bool | None = None
    """Whether items inside region are included in bill of materials generation"""
    on_board: bool | None = None
    """Whether items inside region exist on board"""
    in_pos_files: bool | None = None
    """Whether items inside region are included in position files."""
    dnp: bool | None = None
    """Whether items inside region are marked as DNP"""
    shape: GrPolySch = F(name="polyline")
    """Graphic polyline shape defining rule area boundary in schematic."""


class NetclassFlagShape(str, AutoSerdeEnum):
    """Enumeration of flag shapes"""

    ROUND = "round"
    DOT = "dot"
    DIAMOND = "diamond"
    RECT = "rectangle"


class NetclassFlag(AutoSerde):
    """Represents a netclass flag in a KiCad schematic"""

    _askiff_key: ClassVar[str] = "netclass_flag"
    _positional: str | None = F(positional=True)
    length: float = 1.27
    """Length of the netclass flag in millimeters."""
    shape: NetclassFlagShape = F(NetclassFlagShape.ROUND)
    """Flag shape"""
    position: Position = F(name="at")
    """Position of the netclass flag in the schematic."""
    fields_autoplaced: bool | None = None
    """Whether fields are auto-placed."""
    effects: Effects = F()
    """Text formatting properties including font, justification, and visibility."""
    uuid: Uuid = F()
    """Unique identifier"""
    properties: PropertyList[SymProperty] = F(lambda: PropertyList(SymProperty), name="property", flatten=True)
    """Properties this flag assigns, including net-class and component class."""

    def component_class(self) -> str:
        """Returns the component class property of the netclass flag, or an empty string if not set."""
        return self.properties.get_value("Component Class", "")

    def net_class(self) -> str:
        """Returns the name of the net class associated with this flag."""
        return self.properties.get_value("Net Class", "")


class SheetFillStyleColor(Color, positional=True):  # type: ignore
    """Color value for sheet fill style in schematic files"""

    R: int = 0
    """Red component of the color value."""
    G: int = 0
    """Green component of the color value."""
    B: int = 0
    """Blue component of the color value."""
    A: float = F(precision=4).version(Version.K9.sch, keep_trailing=True)
    """Alpha channel value for the sheet fill color, normalized from 0.0 to 1.0"""


class SheetFillStyle(AutoSerde):
    """Represents the fill style for a schematic sheet, controlling how the sheet's rectangle is rendered."""

    color: SheetFillStyleColor = F()
    """Color of the sheet fill including alpha channel precision."""


class SheetInstance(ObjectSchematicInstance):
    """Represents a schematic sheet instance within a KiCad schematic,
    linking to a specific schematic path and page."""

    _askiff_key: ClassVar[str] = "path"
    page: str = F(after="path")
    """Page number"""


class SheetProject(AutoSerde):
    """Describes instances of schematic sheet inside project"""

    _askiff_key: ClassVar[str] = "project"
    project_name: str = F(positional=True)
    """Name of project"""
    instances: list[SheetInstance] = F(flatten=True, name="path")
    """Instances of this sheet in this `project`"""


class SheetPin(AutoSerde):
    """Represents a sheet pin in a KiCad schematic, defining connections between sheets in hierarchical designs."""

    _askiff_key: ClassVar[str] = "pin"
    name: str = F(positional=True)
    """Pin name, typically a net or signal identifier."""
    shape: LabelShape = F(LabelShape.PASSIVE, positional=True)
    """Pin shape indicating visual representation."""
    position: Position = F(name="at")
    """Pin position on the schematic sheet rectangle"""
    uuid: Uuid = F()
    """Unique identifier"""
    effects: Effects = F()
    """Text effects applied to the pin label."""


class Sheet(AutoSerde):
    """Represents a hierarchical schematic sheet in a KiCad symbol library

    Allows encapsulation of schematic file inside other schematic and connection between schematic blocks"""

    position: Position = F(name="at")
    """Position of the sheet's origin in schematic coordinates"""
    size: Size = F()
    """Size of the sheet rectangle"""
    exclude_from_sim: bool | None = None
    """Whether the sheet is excluded from simulation"""
    in_bom: bool | None = None
    """Whether the sheet is included in the bill of materials"""
    on_board: bool | None = None
    """Whether sheet is placed on the board"""
    in_pos_files: bool | None = None
    """Whether the sheet is included in position files"""
    dnp: bool | None = None
    """Whether the sheet is marked as do-not-place"""
    fields_autoplaced: bool | None = None
    """Whether fields of sheet are auto-placed"""
    stroke: Stroke = F()
    """Visual styling of the sheet's graphical elements including line thickness, style, and color"""
    fill: SheetFillStyle = F()
    """Style of sheet rectangle fill"""
    uuid: Uuid = F()
    """Unique identifier"""

    properties: PropertyList[SymProperty] = F(lambda: PropertyList(SymProperty), name="property", flatten=True)
    """Schematic sheet properties including file and name references"""

    pins: list[SheetPin] = F(flatten=True, name="pin")
    """Pins associated with the schematic sheet
    
    Connects to corresponding hierarchical labels inside schematic this sheet references to"""

    instances: list[SheetProject] = F()
    """Describes properties of sheet instances across projects in which this schematic was used"""


class HierarchicalInstance(AutoSerde):
    """Stores information where in schematic hierarchy sheet has been used"""

    _askiff_key: Final[str] = "path"
    path: str = F(positional=True)
    """Path (uuids of parent schematics) """
    page: str = F()
    """Page number"""


class GrItemConnection(GrItemSch):
    """Signal/electric connection item"""

    __askiff_order: ClassVar[list[str]] = ["position", "pts", "diameter", "color", "size", "stroke", "uuid"]
    uuid: Uuid = F()
    """Unique identifier"""


class Junction(GrItemConnection):
    """Junctions between wires and buses"""

    _askiff_key: Final[str] = "junction"  # type: ignore
    position: Position = F(name="at")
    """Position of the junction in the schematic"""
    diameter: float = F()
    """Diameter of the junction"""
    color: Color = F()
    """Color of the junction"""


class NoConnectMark(GrItemConnection):
    """No connect marks (cross),
    Used to indicate pins or nets that are intentionally left unconnected"""

    _askiff_key: Final[str] = "no_connect"  # type: ignore
    position: Position = F(name="at")
    """Position of the no connect mark on the schematic"""


class BusEntry(GrItemConnection):
    """Bus entry connection between a bus and a wire"""

    _askiff_key: Final[str] = "bus_entry"  # type: ignore
    position: Position = F(name="at")
    """Position of the bus entry element in the schematic"""
    size: Size = F(lambda: Size(1.27, -1.27))
    """Size of the bus entry connection"""
    stroke: Stroke = F()
    """Visual styling of the bus entry line including thickness, style, and color"""


class WireBase(BasePoly, GrItemConnection):
    """Base class for wire-like graphic elements in KiCad schematics."""

    stroke: Stroke = F()
    """Visual styling of the wire including thickness, line style, and color."""


class Wire(WireBase):
    """Wire represents a wire segment in a KiCad schematic,
    Used to define graphical connections between components in schematic diagrams."""

    _askiff_key: Final[str] = "wire"  # type: ignore


class Bus(WireBase):
    """A bus is a wire-like graphic element in KiCad schematics acting as a wire for a group of signals"""

    _askiff_key: Final[str] = "bus"  # type: ignore


class Schematic(AutoSerdeFile):
    """Represents a `.kicad_sch` file"""

    _askiff_key: Final[str] = "kicad_sch"  # type: ignore

    fs_ext: Final[str] = F(".kicad_sch", skip=True)  # type: ignore # ty:ignore[override-of-final-variable]
    """File name extension"""

    version: int = Version.DEFAULT.sch
    """Schematic file format version number."""

    generator: str = Version.generator
    """Program that generated the schematic file"""

    generator_version: str = Version.generator_ver
    """Version of program that generated the schematic file"""

    uuid: Uuid = F()
    """Unique identifier"""

    paper: Paper = F()
    """Paper size configuration for the schematic."""

    title_block: TitleBlock = F()
    """Title block metadata for the schematic."""

    lib_symbols: list[SymbolDefinition] = F()
    """Definition of symbols used in sch (this is kind of cache of library symbols)"""

    bus_aliases: list[BusAlias] = F(flatten=True, name="bus_alias", skip=True).version(Version.K9.sch, skip=False)
    """[K10: Deprecated] Definition of members assigned to bus aliases (K10 defines this in kicad_pro)"""

    graphic_items: list[GrItemSch] = F(flatten=True)
    """Graphic items present in the schematic such as lines, circles, and arcs.
    including items defining electrical connections"""

    tables: list[GrTableSch] = F(name="table", flatten=True)
    """List of tables and their contents in the schematic."""

    labels: list[LabelLocal] = F(flatten=True, name="label")
    """Local net labels in the schematic"""

    global_labels: list[LabelGlobal] = F(flatten=True, name="global_label")
    """Global net labels connected across all sheets in project"""

    hierarchical_labels: list[LabelHierarchical] = F(flatten=True, name="hierarchical_label")
    """Hierarchical net labels connecting to hierarchical sheet pins where this schematic is instantiated"""

    rule_areas: list[RuleArea] = F(flatten=True, name="rule_area")
    """Rule areas definition (used in conjunction with netclass_flags to provide areal property assignment)"""

    netclass_flags: list[NetclassFlag] = F(flatten=True, name="netclass_flag")
    """Flags defining component and net class assignments"""

    symbols: list[SymbolSchematic] = F(flatten=True, name="symbol")
    """Actual instances of symbols used in schematic"""

    groups: list[Group] = F(flatten=True, name="group")
    """Groups of schematic objects"""

    sheets: list[Sheet] = F(flatten=True, name="sheet")
    """Instantiated hierarchical sheets placed in this schematic"""

    sheet_instances: list[HierarchicalInstance] = F()
    """Stores information where in schematic hierarchy sheet has been used"""

    embedded_fonts: bool | None = F().version(Version.K8.pcb, skip=True)
    """Whether fonts are embedded into schematic file"""

    embedded_files: list[EmbeddedFile] = F().version(Version.K8.pcb, skip=True)
    """Embedded files data including fonts and datasheets"""

    def add_symbol(
        self, lib_sym: SymbolDefinition, reference: str | None = None, position: Position | None = None, unit: int = 1
    ) -> None:
        """Add a symbol instance to the schematic, optionally setting its reference, position, and unit.

        If symbol is not in cached library symbols, it is added there too
        """
        if not next((s for s in self.lib_symbols if lib_sym.lib_id == s.lib_id), None):
            self.lib_symbols.append(lib_sym)
        sym_instance = SymbolSchematic(
            **{k: v for k, v in lib_sym.__dict__.items() if k in SymbolSchematic.__dataclass_fields__}
        )

        if reference:
            sym_instance.properties.ref.value = reference
        sym_instance.position = position or Position()
        # sym_instance.pins
        # sym_instance.instances
        self.symbols.append(sym_instance)
