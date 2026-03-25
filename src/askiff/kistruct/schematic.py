from typing import TYPE_CHECKING, Any, ClassVar, Final, cast

from askiff.auto_serde import AutoSerde, AutoSerdeAgg, AutoSerdeEnum, AutoSerdeFile, F
from askiff.const import Version
from askiff.kistruct.common import (
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
from askiff.kistruct.gritems import GrItemSch, GrPolySch, GrTableSch
from askiff.kistruct.symbol import LibSymbol, SymbolSchematic, SymProperty

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore


class BusAlias(AutoSerde):
    pass


class LabelShape(str, AutoSerdeEnum):
    PASSIVE = "passive"
    INPUT = "input"
    OUTPUT = "output"
    BIDIRECTIONAL = "bidirectional"
    TRI_STATE = "tri_state"


class LabelBase(AutoSerde):
    name: str = F(positional=True)
    position: Position = F(name="at")
    fields_autoplaced: bool | None = None
    effects: Effects = F()
    uuid: Uuid = F()
    properties: PropertyList[SymProperty] = F(name="property", flatten=True).version(Version.K9.sch, skip=True)
    """Additional properties of the label, such as net-class, intersheet-references ..."""


class LabelLocal(LabelBase):
    pass


class LabelGlobal(LabelBase):
    shape: LabelShape = F(LabelShape.PASSIVE, after="name")


class LabelHierarchical(LabelBase):
    shape: LabelShape = F(LabelShape.PASSIVE, after="name")


class RuleArea(AutoSerde):
    exclude_from_sim: bool | None = None
    in_bom: bool | None = None
    on_board: bool | None = None
    in_pos_files: bool | None = None
    dnp: bool | None = None
    shape: GrPolySch = F(name="polyline")


class NetclassFlag(AutoSerde):
    pass


class SheetFillStyle(AutoSerde):
    # color: Color
    pass


class Sheet(AutoSerde):
    position: Position = F(name="at")
    size: Size = F()
    exclude_from_sim: bool | None = None
    in_bom: bool | None = None
    on_board: bool | None = None
    in_pos_files: bool | None = None
    dnp: bool | None = None
    fields_autoplaced: bool | None = None
    stroke: Stroke = F()
    fill: SheetFillStyle = F()
    uuid: Uuid = F()

    properties: PropertyList[SymProperty] = F(name="property", flatten=True)
    """Sheet properties such as file, name"""


class HierarchicalInstance(AutoSerde):
    _askiff_key: Final[str] = "path"
    path: str = F(positional=True)
    page: str = F()


class GrItemConnection(GrItemSch):
    __askiff_order: ClassVar[list[str]] = ["position", "pts", "diameter", "color", "size", "stroke", "uuid"]
    uuid: Uuid = F()


class Junction(GrItemConnection):
    """Junctions between wires/buses"""

    _askiff_key: Final[str] = "junction"  # type: ignore
    position: Position = F(name="at")
    diameter: float = F()
    color: Color = F()


class NoConnectMark(GrItemConnection):
    """No connect marks (cross)"""

    _askiff_key: Final[str] = "no_connect"  # type: ignore
    position: Position = F(name="at")


class BusEntry(GrItemConnection):
    """Bus entries/connections between bus and wire"""

    _askiff_key: Final[str] = "bus_entry"  # type: ignore
    position: Position = F(name="at")
    size: Size = F(lambda: Size(1.27, -1.27))
    stroke: Stroke = F()


class WireBase(BasePoly, GrItemConnection):
    stroke: Stroke = F()


class Wire(WireBase):
    _askiff_key: Final[str] = "wire"  # type: ignore


class Bus(WireBase):
    _askiff_key: Final[str] = "bus"  # type: ignore


class Schematic(AutoSerdeFile):
    _askiff_key: Final[str] = "kicad_sch"  # type: ignore

    version: int = Version.DEFAULT.sch
    """Defines the file format version"""

    generator: str = Version.generator
    """Defines the program used to write the file"""

    generator_version: str = Version.generator_ver
    """Defines the program version used to write the file"""

    uuid: Uuid = F()
    """Schematic sheet uuid, used to identify sheet in hierarchical schematics"""

    paper: Paper = F()

    title_block: TitleBlock = F()

    lib_symbols: list[LibSymbol] = F()
    """Definition of symbols used in sch (this is kind of cache of library symbols)"""

    bus_aliases: list[BusAlias] = F(flatten=True, name="bus_alias")
    """Definition of members assigned to bus aliases"""

    graphic_items: AutoSerdeAgg[GrItemSch] = F(flatten=True)
    """list of graphical objects (lines, circles, arcs, ...)"""

    tables: list[GrTableSch] = F(name="table", flatten=True)
    """Defines list of tables and their contents"""

    labels: list[LabelLocal] = F(flatten=True, name="label")
    """Local net labels (connects just to same named labels in one sheet)"""

    global_labels: list[LabelGlobal] = F(flatten=True, name="global_label")
    """Global net labels (connected across all sheets in project)"""

    hierarchical_labels: list[LabelHierarchical] = F(flatten=True, name="hierarchical_label")
    """Hierarchical net labels, connects to hierarchical sheet pin, where this schematic is instantiated"""

    rule_areas: list[RuleArea] = F(flatten=True, name="rule_area")
    """Rule areas definition (used in conjunction with netclass_flags to provide areal property assignment)"""

    netclass_flags: list[NetclassFlag] = F(flatten=True, name="netclass_flag")
    """Labels used to Assign net classes and component classes"""

    symbols: list[SymbolSchematic] = F(flatten=True, name="symbol")
    """Actual instances of symbols used in schematic"""

    groups: list[Group] = F(flatten=True, name="group")
    """Grouping of schematics objects"""

    sheets: list[Sheet] = F(flatten=True, name="sheet")
    """Instantiated hierarchical sheets placed in this schematic"""

    sheet_instances: list[HierarchicalInstance] = F()
    """Stores information where in schematic hierarchy sheet has been used"""

    embedded_fonts: bool | None = None
    """Indicates whether there are fonts embedded into this component"""

    embedded_files: list[EmbeddedFile] = F()
    """Stores data of embedded files, eg. fonts, datasheet"""
