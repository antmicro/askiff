from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Final, Unpack, cast

from askiff._auto_serde import AutoSerde, AutoSerdeAgg, AutoSerdeDownCasting, AutoSerdeEnum, F, SerdeOpt
from askiff._sexpr import GeneralizedSexpr
from askiff.common import BaseBezier, PinTypePCB, Position, Size, Uuid
from askiff.common_pcb import (
    BaseLayer,
    BasePoly,
    BoardSide,
    Layer,
    LayerCopper,
    LayerSet,
    Net,
    TeardropSettings,
)
from askiff.gritems import BaseArc, BaseCircle, BaseLine

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore


class ZoneConnect(str, AutoSerdeEnum):
    """Defines connection type between pad and zone"""

    NO_CONNECT = 0
    """Pads are not connect to zone"""

    THERMAL_RELIEF = 1
    """Pads are connected to zone using thermal reliefs"""

    SOLID = 2
    """Pads are connected to zone using solid fill"""

    THERMAL_RELIEF_THT = 3
    """Only through hold pads are connected to zone using thermal reliefs"""


class PadShape(AutoSerde):
    """Represents a pad shape definition in KiCad, used for specifying the geometric form of a pad in a footprint.

    This is an abstract base class
    that supports automated downcasting to specific pad shape types based on the `shape` field.

    Do not instantiate directly, use subclasses

    Remark: To change pad shape, instantiate new object of correct subclass"""

    __askiff_down_cast_field: ClassVar[str] = "shape"
    """Field used for downcasting pad shape types during deserialization."""
    __askiff_childs: ClassVar[dict[str, type]] = {}
    """Child pad shape types for automatic downcasting during deserialization."""
    shape: str = ""
    """Pad shape type identifier."""
    size: Size = F()
    """Pad size defined by width and height dimensions"""

    @classmethod
    def __init_subclass__(cls, **kwargs: Unpack[SerdeOpt]) -> None:  # type: ignore
        super().__init_subclass__(**kwargs)
        PadShape.__askiff_childs[cls.shape] = cls  # type: ignore


class PadShapeOval(PadShape):
    """Represents an oval-shaped pad in a KiCad footprint."""

    shape: Final[str] = F("oval", unquoted=True)  # type: ignore
    """Constant pad shape identifier"""


class PadShapeCircle(PadShape):
    """Pad shape definition for circular pads in KiCad footprints."""

    shape: Final[str] = F("circle", unquoted=True)  # type: ignore
    """Constant pad shape identifier"""


class PadShapeChamfer(AutoSerde, flag=True, bare=True):  # type: ignore
    """Represents chamfer settings for a pad's shape in KiCad, specifying which corners should be chamfered."""

    top_left: bool = F()
    """Whether the top-left corner is chamfered."""
    top_right: bool = F()
    """Whether the top-right corner is chamfered."""
    bottom_left: bool = F()
    """Whether the bottom-left corner is chamfered."""
    bottom_right: bool = F()
    """Whether the bottom-right corner is chamfered."""


class PadShapeRoundrect(PadShape):
    """Represents a rounded rectangle pad shape in KiCad"""

    shape: Final[str] = F("roundrect", unquoted=True)  # type: ignore
    """Constant pad shape identifier"""
    roundrect_rratio: float = F(0.25, precision=12)
    """Ratio of rounded rectangle corners to pad size."""
    chamfer_ratio: float | None = F(precision=12)
    """Ratio of chamfer to pad height for rounded rectangle pad shape."""
    chamfer: PadShapeChamfer | None = None
    """Chamfer settings for the pad's corners"""


class PadShapeTrapezoid(PadShape):
    """Pad shape definition for a trapezoidal pad in KiCad footprints."""

    shape: Final[str] = F("trapezoid", unquoted=True)  # type: ignore
    """Constant pad shape identifier"""
    rect_delta: list[float] = F()
    """Delta values for trapezoid pad shape definition."""


class PadShapeCustomAnchor(str, AutoSerdeEnum):
    """Enumeration for custom pad anchor shapes in KiCad"""

    RECT = "rect"
    CIRCLE = "circle"


class PadShapeCustomClearance(str, AutoSerdeEnum):
    """Enumeration for custom clearance options in pad shapes"""

    OUTLINE = "outline"


class PadShapeCustomOptions(AutoSerde):
    """Options for custom pad shapes in KiCad, specifying clearance and anchor behavior."""

    clearance: PadShapeCustomClearance = F(PadShapeCustomClearance.OUTLINE)
    """Clearance type for the custom pad shape."""
    anchor: PadShapeCustomAnchor = F(PadShapeCustomAnchor.RECT)
    """Anchor type for the custom pad shape."""


class GrShapePad(AutoSerde):
    """Graphic shape representing a pad on a PCB, used for visual elements such as outlines or cutouts."""

    __askiff_childs: ClassVar[dict[str, type]] = {}
    """Child class type mapping for automatic deserialization"""
    __askiff_order: ClassVar[list[str]] = ["start", "mid", "center", "end", "pts", "width", "fill"]
    width: float = 0.2
    """Width of the pad outline in millimeters."""

    @classmethod
    def __init_subclass__(cls, **kwargs: Unpack[SerdeOpt]) -> None:  # type: ignore
        super().__init_subclass__(**kwargs)
        askiff_key = "_askiff_key"
        if hasattr(cls, askiff_key):
            GrShapePad.__askiff_childs[getattr(cls, askiff_key)] = cls
        # Note that this is not copy, it is exactly the same memory as for GrItem
        setattr(cls, f"_{cls.__name__}__askiff_childs", GrShapePad.__askiff_childs)


class GrShapePadPoly(GrShapePad, BasePoly):
    """Polygon primitive for defining pad custom shapes."""

    _askiff_key: ClassVar[str] = "gr_poly"
    fill: bool = False
    """Whether the polygon pad fill is enabled."""


class GrShapePadCurve(GrShapePad, BaseBezier):
    """Bezier primitive for defining pad custom shapes."""

    _askiff_key: ClassVar[str] = "gr_curve"


class GrShapePadCircle(GrShapePad, BaseCircle):
    """Circle primitive for defining pad custom shapes."""

    _askiff_key: ClassVar[str] = "gr_circle"
    fill: bool = False
    """Whether the circle pad is filled with solid color."""


class GrShapePadArc(GrShapePad, BaseArc):
    """Arc primitive for defining pad custom shapes."""

    _askiff_key: ClassVar[str] = "gr_arc"


class GrShapePadLine(GrShapePad, BaseLine):
    """Line primitive for defining pad custom shapes."""

    _askiff_key: ClassVar[str] = "gr_line"


class PadShapeCustom(PadShape):
    """Custom pad shape defined by graphic primitives. Used in footprint pad definitions for non-standard geometries."""

    shape: Final[str] = F("custom", unquoted=True)  # type: ignore
    """Constant pad shape identifier"""
    primitives: AutoSerdeAgg[GrShapePad] = F(keep_empty=True)
    """Graphic primitives defining the custom pad shape"""
    options: PadShapeCustomOptions = F()
    """Options for custom pad shape clearance and anchor behavior"""


class PadStackMode(str, AutoSerdeEnum):
    """Enumeration of pad stack mode options for KiCad pad definitions. Controls granularity of layer configuration."""

    FRONT_INNER_BACK = "front_inner_back"
    CUSTOM = "custom"


class PadStackLayer(AutoSerde):
    """Represents a shape definition for one layer in pad stack"""

    _askiff_key: ClassVar[str] = "layer"
    layer: LayerCopper = F(Layer.CU_B, positional=True)
    """Copper layer of pad which this object refers to"""
    shape: PadShape = F(inline=True)
    """Pad shape definition for the layer."""
    offset: Position | None = None
    """Offset position of the pad stack layer relative to the pad center."""
    thermal_bridge_angle: float | None = None
    """Angle of thermal relief bridge for this pad stack layer."""
    zone_connect: int | None = None
    """Pad stack layer zone connection type."""


class PadStack(AutoSerde):
    """Pad represents a pad stack configuration (pad shape across different layers) in a KiCad footprint"""

    mode: PadStackMode = F(PadStackMode.FRONT_INNER_BACK)
    """Pad stack mode defining how granular are layer settings"""
    layers: list[PadStackLayer] = F(flatten=True, name="layer")
    """Pad stack layers configuration."""


class PadProperty(str, AutoSerdeEnum):
    """PadProperty represents enumerated pad properties used in KiCad footprint definitions.
    These properties define special characteristics of pads such as BGA, heatsink, fiducial, and mechanical types."""

    BGA = "pad_prop_bga"
    HEATSINK = "pad_prop_heatsink"
    FIDUCIAL_LOC = "pad_prop_fiducial_loc"
    FIDUCIAL_GLOB = "pad_prop_fiducial_glob"
    TESTPOINT = "pad_prop_testpoint"
    MECHANICAL = "pad_prop_mechanical"
    CASTELLATED = "pad_prop_castellated"
    PRESSFIT = "pad_prop_pressfit"


class PadDrill(AutoSerde):
    """Base class for drill configuration for a pad in a KiCad footprint.

    Do not instantiate directly, use subclasses

    Remark: To change drill type, instantiate new object of correct subclass"""

    offset: Position | None = None
    """Pad drill offset from pad center."""

    @classmethod
    def deserialize_downcast(cls, sexp: GeneralizedSexpr) -> PadDrill:
        if isinstance(sexp[0], list):
            return PadDrillNone.deserialize(sexp)
        if sexp[0] == "oval":
            return PadDrillOval.deserialize(sexp)
        return PadDrillSimple.deserialize(sexp)


class PadDrillOval(PadDrill):
    """Represents an oval drill configuration for a pad in a KiCad footprint."""

    type: Final[str] = F("oval", positional=True, unquoted=True)
    """Drill type keyword, class constant"""
    x: float = F(positional=True)
    """X dimension of the oval drill shape."""
    y: float = F(positional=True)
    """Y dimension of the oval drill shape."""
    _offset = F()


class PadDrillSimple(PadDrill):
    """Represents a simple pad drill configuration with a circular hole of fixed diameter."""

    diameter: float = F(positional=True)
    """Diameter of the pad drill hole."""
    _offset = F()


class PadDrillNone(PadDrill):
    """Represents a pad drill configuration for SMD pads with no drill, but possible center offset."""

    pass


class DrillPostMatching(AutoSerdeDownCasting):
    """Drill post-matching settings for footprint vias or pads."""

    _AutoSerdeDownCasting__downcast_field: ClassVar[int] = 0
    type: Final[str] = F(positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Drill post-matching type, class constant"""
    size: float = F()
    """Drill size"""


class DrillPostMatchingCounterbore(DrillPostMatching):
    """Drill counterbore post-matching settings for a footprint's pad or via"""

    type: Final[str] = F("counterbore", positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Drill post-matching type, class constant"""
    _size = F()
    depth: float = F()
    """Depth of the counterbore hole"""


class DrillPostMatchingCountersink(DrillPostMatching):
    """Drill countersink post-matching settings for a footprint's pad or via"""

    type: Final[str] = F("countersink", positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Drill post-matching type, class constant"""
    _size = F()
    angle: float = F()
    """Angle of the countersink drill in degrees"""


class AfterDrillLayers(AutoSerde, positional=True):  # type: ignore
    """Represents depth specification for an after-drill operation"""

    board_side: BoardSide = F(BoardSide.FRONT)
    """Board side where drilling starts"""
    stop_layer: LayerCopper = F(Layer.CU_F)
    """Stop layer for drilling depth specification"""


class AfterDrill(AutoSerde):
    """Represents the `after_drill` setting of pad,
    defining properties related to additional drill operation after the initial drilling"""

    size: float = F()
    """Drill size"""
    layers: AfterDrillLayers = F()
    """Layers involved in the after-drill operation, specifying start side and stop layer."""


class Pad(AutoSerdeDownCasting):
    """Pad represents a pad in a KiCad footprint supporting various pad types, shapes, and drill configurations

    Do not instantiate directly use subclasses.

    Remark: To change pad type from e.g. SMD to THT, create new instance of other subclass"""

    _AutoSerdeDownCasting__downcast_field: ClassVar[int] = 1
    __askiff_order: ClassVar[list[str]] = [
        "number",
        "type",
        "shape.shape",
        "position",
        "shape.size",
        "drill",
        "backdrill",
        "tertiary_drill",
        "front_post_machining",
        "back_post_machining",
        "property",
        "layers",
        "shape.rect_delta",
        "remove_unused_layers",
        "keep_end_layers",
        "shape.roundrect_rratio",
        "shape.chamfer_ratio",
        "shape.chamfer",
        "die_length",
        "die_delay",
        "net",
        "pinfunction",
        "pintype",
        "solder_mask_margin",
        "solder_paste_margin",
        "solder_paste_margin_ratio",
        "clearance",
        "zone_connect",
        "thermal_bridge_width",
        "thermal_bridge_angle",
        "thermal_gap",
        "teardrops",
        "shape.options",
        "shape.primitives",
        "uuid",
        "padstack",
    ]
    number: str = F(positional=True)
    """Pad number string."""
    type: Final[str] = F(positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Pad type identifier. Class constant"""
    shape: PadShape = F(inline=True, positional=True)
    """Pad geometric shape definition"""
    padstack: PadStack | None = None
    """Pad stack configuration including mode and layers."""
    position: Position = F(name="at")
    """Pad position in footprint space"""
    property: PadProperty | None = None
    """Pad special properties like BGA, heatsink, fiducial, or mechanical type."""
    drill: PadDrill | None = None
    """Drill configuration for the pad, including type, dimensions and offset."""
    remove_unused_layers: bool | None = None
    """Whether to keep annular ring on unconnected layers"""
    layers: LayerSet[BaseLayer] = F(name="layers")
    """Layers assigned to the pad"""
    die_length: float | None = None
    """Trace length inside IC"""
    die_delay: float | None = None
    """Trace delay inside IC"""
    solder_mask_margin: float | None = None
    """Additional margin applied to solder mask opening size."""
    solder_paste_margin: float | None = None
    """Solder paste margin value for the pad."""
    solder_paste_margin_ratio: float | None = None
    """Ratio of solder paste margin to pad size."""
    clearance: float | None = None
    """Pad clearance value in millimeters."""
    zone_connect: ZoneConnect | None = None
    """Pad connection type to copper zones."""
    thermal_bridge_width: float | None = None
    """Width of thermal relief bridge"""
    thermal_bridge_angle: float | None = None
    """Angle of thermal relief bridge"""
    thermal_gap: float | None = None
    """Gap between pad and zone with thermal relief connection"""
    teardrops: TeardropSettings | None = None
    """Whether teardrop settings are applied to the pad"""
    net: Net | None = None
    """Signal net assigned to pad"""
    pinfunction: str | None = None
    """Pad pin function name."""
    pintype: PinTypePCB | None = None
    """Pad pin type configuration."""
    uuid: Uuid = F()
    """Unique identifier"""


class PadTHT(Pad):
    """Represents a through-hole pad"""

    type: Final[str] = F("thru_hole", positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Pad type identifier. Class constant"""
    keep_end_layers: bool | None = None
    """Whether to `remove_unused_layers` affects end layers of pad"""
    backdrill: AfterDrill | None = None
    """Backdrill configuration"""
    tertiary_drill: AfterDrill | None = None
    """Drill configuration for the tertiary drilling operation."""
    front_post_machining: DrillPostMatching | None = None
    """Front post-machining settings."""
    back_post_machining: DrillPostMatching | None = None
    """Back post-machining settings"""


class PadSMD(Pad):
    """Surface-mount pad"""

    type: Final[str] = F("smd", positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Pad type identifier. Class constant"""
    drill: PadDrillNone | None = None
    """Defines shape offset from pad center"""


class PadEdgeConnector(Pad):
    """Represents a edge connector pad"""

    type: Final[str] = F("connect", positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Pad type identifier. Class constant"""
    drill: PadDrillNone | None = None
    """Defines shape offset from pad center"""


class PadNonPlated(Pad):
    """Represents a non-plated through-hole pad"""

    type: Final[str] = F("np_thru_hole", positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Pad type identifier. Class constant"""
