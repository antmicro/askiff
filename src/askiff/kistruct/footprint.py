from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Final, cast

from askiff.auto_serde import AutoSerde, AutoSerdeAgg, AutoSerdeEnum, AutoSerdeFile, F
from askiff.const import Version
from askiff.kistruct.common import (
    ComponentClass,
    EmbeddedFile,
    Group,
    LibId,
    LibTable,
    Position,
    Property,
    PropertyList,
    Uuid,
)
from askiff.kistruct.common_pcb import Layer, LayerSet, LayerUser, Point, Zone
from askiff.kistruct.fp_pad import Pad, ZoneConnect
from askiff.kistruct.gritems import Barcode, Dimension, GrItemFp, GrTablePCB
from askiff.sexpr import Qstr

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore


class Coordinate(AutoSerde):
    _askiff_key: ClassVar[str] = "xyz"
    x: float = F(positional=True)
    y: float = F(positional=True)
    z: float = F(positional=True)


class FpProperty(Property):
    """Stores footprint metadata such as Reference, Value, Datasheet, .."""

    _askiff_key: ClassVar[str] = "property"

    position: Position = F(name="at")
    """Property text position"""

    locked: bool | None = F.unlocked()
    """Defines if the property can be edited"""

    layer: Layer = Layer.FAB_F
    """Layer the text resides on"""

    _hide = F()

    uuid: Uuid = F()

    _effects = F()

    def _askiff_post_deser(self) -> None:
        # override hide removal of base class
        return


class BoardSide(Qstr, AutoSerdeEnum):
    """Indicates board side"""

    FRONT = "F.Cu"
    BACK = "B.Cu"


class Attributes(AutoSerde, flag=True, bare=True):  # type: ignore
    smd: bool = F()
    through_hole: bool = F()
    board_only: bool = F()
    exclude_from_pos_files: bool = F()
    exclude_from_bom: bool = F()
    allow_missing_courtyard: bool = F()
    dnp: bool = F()
    allow_soldermask_bridges: bool = F()

    def __bool__(self) -> bool:
        return (
            any(getattr(self, f.name) for f in dataclasses.fields(self))
            or bool(self._AutoSerde__extra)  # ty:ignore[unresolved-attribute]
            or bool(self._AutoSerde__extra_positional)  # ty:ignore[unresolved-attribute]
        )


class Model3D(AutoSerde):
    path: str = F(positional=True)
    hide: bool | None = None
    opacity: float | None = F(precision=4, keep_trailing=True)
    offset: Coordinate = F(nested=True)
    scale: Coordinate = F(nested=True)
    rotate: Coordinate = F(nested=True)


class Footprint(AutoSerde):
    _askiff_key: ClassVar[str] = "footprint"

    lib_id: LibId = F(positional=True)
    """Defines footprint name and library link"""

    side: BoardSide = F(BoardSide.FRONT, name="layer")
    """Describes on which board side footprint lies"""

    description: str | None = F(name="descr")
    """Allows to add additional text description to the footprint"""

    tags: str | None = None
    """Defines search tags"""

    properties: PropertyList[FpProperty] = F(name="property", flatten=True)
    """Properties of the footprint, such as reference, value, datasheet, ..."""

    solder_mask_margin: float | None = None
    """Solder mask expansion for all pads in the footprint. 
    If not set, the board level setting is used."""

    solder_paste_margin: float | None = None
    """Difference between pad size and solder paste size for all pads in the footprint. 
    If not set, the board level setting is used."""

    solder_paste_margin_ratio: float | None = None
    """Percentage of the pad size used for solder paste for all pads in the footprint. 
    If not set, the board level setting is used."""

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
    """Attributes of the footprint, such as smd/tht, dnp, ..."""

    stackup: LayerSet[Layer] = F(nested=True, serialize=LayerSet.serialize_nested)

    private_layers: LayerSet[LayerUser] = F(name="private_layers")
    """Defines a list of private layers assigned to the footprint"""

    net_tie_pad_groups: list[str] = F()
    """Defines list of net tie groups assigned to the footprint"""

    duplicate_pad_numbers_are_jumpers: bool | None = F()
    """If true DRC will consider pads with the same number as electrically connected"""

    jumper_pad_groups: list[list[str]] = F()
    """Pad numbers that shall be considered as internally connected"""

    graphic_items: AutoSerdeAgg[GrItemFp] = F(flatten=True)
    """List of graphical objects (lines, circles, arcs, texts, ...) in the footprint"""

    tables: list[GrTablePCB] = F(name="table", flatten=True)
    """Defines list of tables and their contents"""

    barcodes: list[Barcode] = F(name="barcode", flatten=True)
    """List of barcodes in the footprint"""

    dimensions: list[Dimension] = F(name="dimension", flatten=True)
    """List of dimensions in the footprint"""

    points: list[Point] = F(name="point", flatten=True)
    """List of points (these are empty/non-physical reference points) in the footprint"""

    pads: list[Pad] = F(name="pad", flatten=True)
    """List of pads in the footprint"""

    zones: list[Zone] = F(flatten=True, name="zone")
    """List of keep out zones in the footprint"""

    groups: list[Group] = F(flatten=True, name="group")
    """List of object groups in the footprint"""

    embedded_fonts: bool = F()
    """Indicates whether there are fonts embedded into this component"""

    embedded_files: list[EmbeddedFile] = F()
    """Stores data of embedded files, eg. fonts, 3d-models"""

    models: list[Model3D] = F(flatten=True, name="model")
    """List of 3D models associated with the footprint"""


class FpPropertyKiFpFilters(AutoSerde):
    ki_fp_filters: Final[str] = F("ki_fp_filters", unquoted=True, positional=True)
    patterns: str = F(positional=True)


class FootprintBoard(Footprint):
    locked: bool | None = F(after="lib_id")
    """Flag to indicate the footprint cannot be edited"""

    placed: bool | None = None

    uuid: Uuid | None = F(after="side")

    position: Position | None = F(name="at")
    """Defines the X and Y coordinates and rotation of the footprint"""

    autoplace_cost90: int | None = F(after="tags")
    """Defines the vertical cost of when using the automatic footprint placement tool. 
    Valid values: integers 1-10"""

    autoplace_cost180: int | None = None
    """Defines the horizontal cost of when using the automatic footprint placement tool. 
    Valid values: integers 1-10"""

    component_classes: list[ComponentClass] = F(after="properties")
    """Component classes assigned to associated symbol"""

    ki_fp_filters: FpPropertyKiFpFilters | None = F(name="property", skip_deser=True)

    path: str | None = None
    """Hierarchical path (sheet uuid's) of the schematic symbol linked to the footprint"""

    sheetname: str | None = None
    """Indicates in which schematic sheet was linked symbol added"""

    sheetfile: str | None = None
    """Indicates in which schematic file was linked symbol added"""

    def _askiff_post_deser(self) -> None:
        ki_fp_filters = self.properties.pop("ki_fp_filters")
        if ki_fp_filters:
            self.ki_fp_filters = FpPropertyKiFpFilters(patterns=ki_fp_filters.value)


class FootprintStandalone(Footprint, AutoSerdeFile):
    version: int | None = F(Version.DEFAULT.fp, after="lib_id")
    """Defines the file format version"""

    generator: str | None = Version.generator
    """Defines the program used to write the file"""

    generator_version: str | None = Version.generator_ver
    """Defines the program version used to write the file"""


class LibTableFp(LibTable, AutoSerdeFile):
    _askiff_key: ClassVar[str] = "fp_lib_table"
