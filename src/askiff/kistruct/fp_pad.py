from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Final, Unpack, cast

from askiff.auto_serde import AutoSerde, AutoSerdeAgg, AutoSerdeDownCasting, AutoSerdeEnum, F, SerdeOpt
from askiff.kistruct.common import PinTypePCB, Position, Size, Uuid
from askiff.kistruct.common_pcb import (
    BaseLayer,
    BasePoly,
    BoardSide,
    Layer,
    LayerCopper,
    LayerSet,
    Net,
    TeardropSettings,
)
from askiff.kistruct.gritems import BaseArc, BaseCircle, BaseLine
from askiff.sexpr import GeneralizedSexpr

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
    __askiff_down_cast_field: ClassVar[str] = "shape"
    __askiff_childs: ClassVar[dict[str, type]] = {}
    shape: str = ""
    size: Size = F()

    @classmethod
    def __init_subclass__(cls, **kwargs: Unpack[SerdeOpt]) -> None:  # type: ignore
        super().__init_subclass__(**kwargs)
        PadShape.__askiff_childs[cls.shape] = cls  # type: ignore


class PadShapeOval(PadShape):
    shape: Final[str] = F("oval", unquoted=True)  # type: ignore


class PadShapeCircle(PadShape):
    shape: Final[str] = F("circle", unquoted=True)  # type: ignore


class PadShapeChamfer(AutoSerde, flag=True, bare=True):  # type: ignore
    top_left: bool = F()
    top_right: bool = F()
    bottom_left: bool = F()
    bottom_right: bool = F()


class PadShapeRoundrect(PadShape):
    shape: Final[str] = F("roundrect", unquoted=True)  # type: ignore
    roundrect_rratio: float = F(0.25, precision=12)
    chamfer_ratio: float | None = F(precision=12)
    chamfer: PadShapeChamfer | None = None


class PadShapeTrapezoid(PadShape):
    shape: Final[str] = F("trapezoid", unquoted=True)  # type: ignore
    rect_delta: list[float] = F()


class PadShapeCustomAnchor(str, AutoSerdeEnum):
    RECT = "rect"
    CIRCLE = "circle"


class PadShapeCustomClearance(str, AutoSerdeEnum):
    OUTLINE = "outline"


class PadShapeCustomOptions(AutoSerde):
    clearance: PadShapeCustomClearance = F(PadShapeCustomClearance.OUTLINE)
    anchor: PadShapeCustomAnchor = F(PadShapeCustomAnchor.RECT)


class GrShapePad(AutoSerde):
    __askiff_childs: ClassVar[dict[str, type]] = {}
    __askiff_order: ClassVar[list[str]] = ["start", "mid", "center", "end", "pts", "width", "fill"]
    width: float = 0.2

    @classmethod
    def __init_subclass__(cls, **kwargs: Unpack[SerdeOpt]) -> None:  # type: ignore
        super().__init_subclass__(**kwargs)
        askiff_key = "_askiff_key"
        if hasattr(cls, askiff_key):
            GrShapePad.__askiff_childs[getattr(cls, askiff_key)] = cls
        # Note that this is not copy, it is exactly the same memory as for GrItem
        setattr(cls, f"_{cls.__name__}__askiff_childs", GrShapePad.__askiff_childs)


class GrShapePadPoly(GrShapePad, BasePoly):
    _askiff_key: ClassVar[str] = "gr_poly"
    fill: bool = False


class GrShapePadCurve(GrShapePadPoly):
    _askiff_key: ClassVar[str] = "gr_curve"


class GrShapePadCircle(GrShapePad, BaseCircle):
    _askiff_key: ClassVar[str] = "gr_circle"
    fill: bool = False


class GrShapePadArc(GrShapePad, BaseArc):
    _askiff_key: ClassVar[str] = "gr_arc"


class GrShapePadLine(GrShapePad, BaseLine):
    _askiff_key: ClassVar[str] = "gr_line"


class PadShapeCustom(PadShape):
    shape: Final[str] = F("custom", unquoted=True)  # type: ignore
    primitives: AutoSerdeAgg[GrShapePad] = F(keep_empty=True)
    options: PadShapeCustomOptions = F()


class PadStackMode(str, AutoSerdeEnum):
    FRONT_INNER_BACK = "front_inner_back"
    CUSTOM = "custom"


class PadStackLayer(AutoSerde):
    _askiff_key: ClassVar[str] = "layer"
    layer: LayerCopper = F(Layer.CU_B, positional=True)
    shape: PadShape = F(inline=True)
    offset: Position | None = None
    thermal_bridge_angle: float | None = None
    zone_connect: int | None = None


class PadStack(AutoSerde):
    mode: PadStackMode = F(PadStackMode.FRONT_INNER_BACK)
    layers: list[PadStackLayer] = F(flatten=True, name="layer")


class PadProperty(str, AutoSerdeEnum):
    BGA = "pad_prop_bga"
    HEATSINK = "pad_prop_heatsink"
    FIDUCIAL_LOC = "pad_prop_fiducial_loc"
    FIDUCIAL_GLOB = "pad_prop_fiducial_glob"
    TESTPOINT = "pad_prop_testpoint"
    MECHANICAL = "pad_prop_mechanical"
    CASTELLATED = "pad_prop_castellated"
    PRESSFIT = "pad_prop_pressfit"


class PadDrill(AutoSerde):
    offset: Position | None = None
    """Offset pad shape from pad center/drill (this is also allowed for non drilled pads)"""

    @classmethod
    def deserialize_downcast(cls, sexp: GeneralizedSexpr) -> PadDrill:
        if isinstance(sexp[0], list):
            return PadDrillNone.deserialize(sexp)
        if sexp[0] == "oval":
            return PadDrillOval.deserialize(sexp)
        return PadDrillSimple.deserialize(sexp)


class PadDrillOval(PadDrill):
    type: Final[str] = F("oval", positional=True, unquoted=True)
    x: float = F(positional=True)
    y: float = F(positional=True)
    _offset = F()


class PadDrillSimple(PadDrill):
    diameter: float = F(positional=True)
    _offset = F()


class PadDrillNone(PadDrill):
    """This Drill class is used for eg. SMD pads that have no drill, but they still can have offset from center"""

    pass


class DrillPostMatching(AutoSerdeDownCasting):
    _AutoSerdeDownCasting__downcast_field: ClassVar[int] = 0
    type: Final[str] = F(positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    size: float = F()


class DrillPostMatchingCounterbore(DrillPostMatching):
    type: Final[str] = F("counterbore", positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    _size = F()
    depth: float = F()


class DrillPostMatchingCountersink(DrillPostMatching):
    type: Final[str] = F("countersink", positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    _size = F()
    angle: float = F()


class AfterDrillLayers(AutoSerde, positional=True):  # type: ignore
    board_side: BoardSide = F(BoardSide.FRONT)
    """Drill start layer - board side"""
    stop_layer: LayerCopper = F(Layer.CU_F)
    """stop layer / how deep should drill extend"""


class AfterDrill(AutoSerde):
    size: float = F()
    layers: AfterDrillLayers = F()


class Pad(AutoSerdeDownCasting):
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
    type: Final[str] = F(positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    shape: PadShape = F(inline=True, positional=True)
    padstack: PadStack | None = None
    position: Position = F(name="at")
    property: PadProperty | None = None
    drill: PadDrill | None = None
    remove_unused_layers: bool | None = None
    layers: LayerSet[BaseLayer] = F(name="layers")
    die_length: float | None = None
    die_delay: float | None = None
    solder_mask_margin: float | None = None
    solder_paste_margin: float | None = None
    solder_paste_margin_ratio: float | None = None
    clearance: float | None = None
    zone_connect: ZoneConnect | None = None
    thermal_bridge_width: float | None = None
    thermal_bridge_angle: float | None = None
    thermal_gap: float | None = None
    teardrops: TeardropSettings | None = None
    net: Net | None = None
    pinfunction: str | None = None
    pintype: PinTypePCB | None = None
    uuid: Uuid = F()


class PadTHT(Pad):
    type: Final[str] = F("thru_hole", positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    keep_end_layers: bool | None = None
    backdrill: AfterDrill | None = None
    tertiary_drill: AfterDrill | None = None
    front_post_machining: DrillPostMatching | None = None
    back_post_machining: DrillPostMatching | None = None


class PadSMD(Pad):
    type: Final[str] = F("smd", positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    drill: PadDrillNone | None = None


class PadEdgeConnector(Pad):
    type: Final[str] = F("connect", positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    drill: PadDrillNone | None = None


class PadNonPlated(Pad):
    type: Final[str] = F("np_thru_hole", positional=True, unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
