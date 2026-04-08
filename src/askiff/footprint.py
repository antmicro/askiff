from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Final, cast

from askiff._auto_serde import AutoSerde, AutoSerdeAgg, AutoSerdeEnum, AutoSerdeFile, F
from askiff.common import (
    ComponentClass,
    EmbeddedFile,
    Group,
    LibId,
    LibraryTable,
    Position,
    Property,
    PropertyList,
    Uuid,
)
from askiff.common_pcb import BaseLayer, BoardSide, Layer, LayerSet, LayerUser, Point, Zone
from askiff.const import Version
from askiff.fp_pad import Pad, ZoneConnect
from askiff.gritems import Barcode, Dimension, GrItemFp, GrTablePCB

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore


class Coordinate(AutoSerde):
    """Represents a 3D point in space with X, Y, and Z components"""

    _askiff_key: ClassVar[str] = "xyz"
    x: float = F(positional=True)
    """X coordinate value in millimeters."""
    y: float = F(positional=True)
    """Y coordinate value in millimeters."""
    z: float = F(positional=True)
    """Z-axis coordinate value"""


class FpProperty(Property):
    """Stores footprint metadata such as Reference, Value, Datasheet, ..."""

    locked: bool | None = F.unlocked()
    """Whether the property is locked against edits."""

    layer: BaseLayer = Layer.FAB_F
    """Layer the text resides on"""

    _hide = F()

    uuid: Uuid = F()
    """Unique identifier"""

    _effects = F()


class FootprintType(str, AutoSerdeEnum):
    """Enumeration of footprint types used in KiCad"""

    SMD = "smd"
    THT = "through_hole"
    UNSPECIFIED = ""


class Attributes(AutoSerde, flag=True, bare=True):  # type: ignore
    """Attributes of a footprint, controlling assembly and export behavior."""

    fp_type: FootprintType = F(FootprintType.UNSPECIFIED)
    """Footprint type"""
    board_only: bool = F()
    """Whether the footprint is excluded from board assembly"""
    exclude_from_pos_files: bool = F()
    """Whether the footprint is excluded from position files"""
    exclude_from_bom: bool = F()
    """Whether the footprint is excluded from the bill of materials"""
    allow_missing_courtyard: bool = F()
    """Whether missing courtyard is allowed in footprint"""
    dnp: bool = F()
    """Whether the footprint is marked as do-not-place"""
    allow_soldermask_bridges: bool = F()
    """Whether solder mask bridges are allowed between footprint pads"""

    def __bool__(self) -> bool:
        return (
            any(getattr(self, f.name) for f in dataclasses.fields(self))
            or bool(self._AutoSerde__extra)  # type: ignore # ty:ignore[unresolved-attribute]
            or bool(self._AutoSerde__extra_positional)  # type: ignore # ty:ignore[unresolved-attribute]
        )


class Model3D(AutoSerde):
    """3D model definition for KiCad footprints, including path, visibility, opacity, and transformation data."""

    path: str = F(positional=True)
    """File path to the 3D model."""
    hide: bool | None = None
    """Whether the model is hidden."""
    opacity: float | None = F(precision=4, keep_trailing=True)
    """Opacity level of the model, from 0.0 (transparent) to 1.0 (opaque)."""
    offset: Coordinate = F(nested=True)
    """3D offset coordinates (x, y, z)."""
    scale: Coordinate = F(nested=True)
    """3D scale factor (x, y, z)."""
    rotate: Coordinate = F(nested=True)
    """3D rotation angle (x, y, z) in degrees."""


class Footprint(AutoSerde):
    """Base class for KiCad footprint

    Typically one of subclasses shall be used:

    * :class:`askiff.footprint.FootprintFile` - for standalone footprint files
    * :class:`askiff.footprint.FootprintBoard` - for footprint on PCB
    """

    _askiff_key: ClassVar[str] = "footprint"

    lib_id: LibId = F(positional=True)
    """Library identifier defining library and footprint name"""

    side: BoardSide = F(BoardSide.FRONT, name="layer")
    """Board side where footprint is placed"""

    description: str | None = F(name="descr")
    """Allows to add additional text description to the footprint"""

    tags: str | None = None
    """Defines search tags"""

    properties: PropertyList[FpProperty] = F(name="property", flatten=True)
    """Footprint properties like reference, value and datasheet."""

    solder_mask_margin: float | None = None
    """Solder mask expansion for all pads in the footprint. 
    If not set, the board level setting is used."""

    solder_paste_margin: float | None = None
    """Difference between pad size and solder paste size for all pads in the footprint. 
    If not set, the board level setting is used."""

    solder_paste_margin_ratio: float | None = None
    """Percentage of pad size used for solder paste margin."""

    clearance: float | None = None
    """Clearance to all board copper objects for all pads in the footprint.
    If not set, the board level setting is used."""

    zone_connect: ZoneConnect | None = None
    """Defines how all pads are connected to filled zone.
    If not defined, then the zone level `connect_pads` setting is used"""

    thermal_width: float | None = None
    """Thermal relief spoke width used for zone connections for all pads in the footprint.
    Affects only pads connected with thermal reliefs.
    If not defined, then the zone level setting is used"""

    thermal_gap: float | None = None
    """Spacing between pad and the zone for all pads in the footprint.
    Affects only pads connected with thermal reliefs.
    If not defined, then the zone level setting is used"""

    attributes: Attributes = F(name="attr")
    """Footprint attributes controlling assembly and export behavior"""

    stackup: LayerSet[BaseLayer] = F(serialize=LayerSet.serialize_nested, deserialize=LayerSet.deserialize_nested)
    """Stackup configuration defining the layers used in footprint."""

    private_layers: LayerSet[LayerUser] = F(name="private_layers")
    """Assigned private layers for the footprint"""

    net_tie_pad_groups: list[str] = F()
    """Net tie groups assigned to the footprint."""

    duplicate_pad_numbers_are_jumpers: bool | None = F()
    """Whether duplicate pad numbers are considered electrically connected."""

    jumper_pad_groups: list[list[str]] = F()
    """Pad numbers considered internally connected"""

    graphic_items: AutoSerdeAgg[GrItemFp] = F(flatten=True)
    """Graphic items in the footprint such as lines, circles, and texts"""

    tables: list[GrTablePCB] = F(name="table", flatten=True)
    """Tables defined in the footprint"""

    barcodes: list[Barcode] = F(name="barcode", flatten=True)
    """List of barcodes in the footprint"""

    dimensions: list[Dimension] = F(name="dimension", flatten=True)
    """List of dimension objects in the footprint"""

    points: list[Point] = F(name="point", flatten=True)
    """List of points (these are empty/non-physical reference points) in the footprint"""

    pads: list[Pad] = F(name="pad", flatten=True)
    """List of pads in the footprint"""

    zones: list[Zone] = F(flatten=True, name="zone")
    """List of keep out zones in the footprint"""

    groups: list[Group] = F(flatten=True, name="group")
    """List of object groups in the footprint"""

    embedded_fonts: bool = F().version(Version.K8.pcb, skip=True)
    """Whether there are fonts embedded into this footprint."""

    embedded_files: list[EmbeddedFile] = F()
    """Embedded files data including fonts and 3D models."""

    models: list[Model3D] = F(flatten=True, name="model")
    """List of 3D models associated with the footprint"""


class FpPropertyKiFpFilters(AutoSerde):
    """Represents KiCad footprint property filters for filtering footprint files based on patterns

    This is inherited property from schematic for baord footprints
    """

    ki_fp_filters: Final[str] = F("ki_fp_filters", unquoted=True, positional=True)
    """KiCad keyword for the property, always set to 'ki_fp_filters'."""
    patterns: str = F(positional=True)
    """Pattern string used for filtering footprint files."""


class FootprintBoard(Footprint):
    """FootprintBoard represents a KiCad footprint as it appears in a board file,
    extending the base Footprint class with board-specific attributes such as placement, locking, and schematic link"""

    locked: bool | None = F(after="lib_id")
    """Whether the footprint is locked against editing."""

    placed: bool | None = None
    """Whether the footprint is placed on the board."""

    uuid: Uuid = F(after="side")
    """Unique identifier"""

    position: Position = F(name="at")
    """Footprint position and rotation on the board"""

    autoplace_cost90: int | None = F(after="tags")
    """Defines the vertical cost of when using the automatic footprint placement tool. 
    Valid values: integers 1-10"""

    autoplace_cost180: int | None = None
    """Defines the horizontal cost of when using the automatic footprint placement tool. 
    Valid values: integers 1-10"""

    component_classes: list[ComponentClass] = F(after="properties")
    """Component classes assigned to associated symbol"""

    ki_fp_filters: FpPropertyKiFpFilters | None = F(name="property", skip_deser=True)
    """KiCad footprint property filters for pattern-based footprint file filtering"""

    path: str | None = None
    """Hierarchical path (sheet uuid's) of the schematic symbol linked to the footprint"""

    sheetname: str | None = None
    """Indicates in which schematic sheet was linked symbol added"""

    sheetfile: str | None = None
    """Indicates in which schematic file was linked symbol added"""

    def _askiff_post_deser(self) -> None:
        """Post-deserialization handler for FootprintBoard.
        Extracts and processes the `ki_fp_filters` property"""
        ki_fp_filters = self.properties.pop("ki_fp_filters")
        if ki_fp_filters:
            self.ki_fp_filters = FpPropertyKiFpFilters(patterns=ki_fp_filters.value)


class FootprintFile(Footprint, AutoSerdeFile):
    """Represents a KiCad footprint file (.kicad_mod).

    Examples:
        Add footprint from file to board (See also :ref:`add-footprint-to-pcb` for way using askiff's library discovery)
        >>> from askiff import Board, FootprintFile
        >>> from askiff.common import Position
        >>> board = Board()
        >>> # Load footprint (from file)
        >>> # footprint = FootprintFile.from_file("path/to/footprint.kicad_mod")
        >>> # Or use already loaded footprint
        >>> footprint = FootprintFile()
        >>> board.add_footprint(footprint, reference="R1", position=Position(15, 20))
    """

    version: int = F(Version.DEFAULT.fp, after="lib_id")
    """Defines the file format revision"""

    generator: str = Version.generator
    """Defines the program used to write the file"""

    generator_version: str = Version.generator_ver
    """Defines the program version used to write the file"""


class FootprintLibraryTable(LibraryTable, AutoSerdeFile):
    """Represents KiCad's footprint library table (fp-lib-table) file"""

    _askiff_key: ClassVar[str] = "fp_lib_table"
