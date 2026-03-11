from __future__ import annotations

from collections.abc import Iterable
from enum import EnumMeta
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Literal, TypeVar, cast

from askiff.auto_serde import AutoSerde, AutoSerdeEnum, F
from askiff.const import KICAD_MAX_LAYER_CU, KICAD_MAX_LAYER_USER
from askiff.kistruct.common import BasePoly, Position, Uuid
from askiff.sexpr import GeneralizedSexpr, Qstr, Sexpr

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore


###########################Layer###########################


class __LayerMeta(EnumMeta):
    def __new__(mcls: type, name: str, bases: tuple[type, ...], namespace: dict[str, Any]) -> type:
        for i in range(1, KICAD_MAX_LAYER_CU + 1):
            namespace[f"CU_IN{i}"] = f"In{i}.Cu"
        for i in range(1, KICAD_MAX_LAYER_USER + 1):
            namespace[f"USER{i}"] = f"User.{i}"
        return super().__new__(mcls, name, bases, namespace)  # type: ignore  # ty:ignore[invalid-super-argument]


class Layer(Qstr, AutoSerdeEnum, metaclass=__LayerMeta):
    """PCB layer keywords
    To keep type checker happy use .incu(1)/.user(1) for In1.Cu/User.1 (instead CU_IN1/USER1)
    Used metaclass based generation of options is valid python but seems to be unsupported by typechecker
    """

    CU_F = "F.Cu"
    CU_B = "B.Cu"
    CU_ALL = "*.Cu"
    ADHESIVE_F = "F.Adhes"
    ADHESIVE_B = "B.Adhes"
    PASTE_F = "F.Paste"
    PASTE_B = "B.Paste"
    SILKS_F = "F.SilkS"
    SILKS_B = "B.SilkS"
    MASK_F = "F.Mask"
    MASK_B = "B.Mask"
    MASK_ALL = "*.Mask"
    EDGE = "Edge.Cuts"
    MARGIN = "Margin"
    COURTYARD_F = "F.CrtYd"
    COURTYARD_B = "B.CrtYd"
    FAB_F = "F.Fab"
    FAB_B = "B.Fab"
    DRAWINGS = "Dwgs.User"
    COMMENTS = "Cmts.User"
    ECO1 = "Eco1.User"
    ECO2 = "Eco2.User"

    INNER = "Inner"
    """Only used inside padstack; all inner copper layers"""

    _KNOCKOUT = "knockout"
    """This is not layer, but for text items in PCB/FP, KiCad inserts here info if text is knockout or not"""

    @staticmethod
    def user(number: int) -> Layer:
        if 1 <= number <= KICAD_MAX_LAYER_USER:
            return Layer(f"User.{number}")
        raise ValueError(f"User.{number} is not supported, number should be between 1 & {KICAD_MAX_LAYER_USER}")

    @staticmethod
    def incu(number: int) -> Layer:
        if 1 <= number <= KICAD_MAX_LAYER_CU:
            return Layer(f"In{number}.Cu")
        raise ValueError(f"In{number}.Cu is not supported, number should be between 1 & {KICAD_MAX_LAYER_CU}")

    def order_id(self) -> int:
        return _layer_order_dict.get(self, 1000)

    def layer_type(self) -> str:
        return "signal" if ".Cu" in self.value else "user"


_layer_order_dict: dict[Layer, int] = {
    Layer.CU_F: 0,
    Layer.CU_B: 2,
    Layer.CU_ALL: 0,
    Layer.ADHESIVE_F: 9,
    Layer.ADHESIVE_B: 11,
    Layer.PASTE_F: 13,
    Layer.PASTE_B: 15,
    Layer.SILKS_F: 5,
    Layer.SILKS_B: 7,
    Layer.MASK_F: 1,
    Layer.MASK_B: 3,
    Layer.MASK_ALL: 1,
    Layer.EDGE: 25,
    Layer.MARGIN: 27,
    Layer.COURTYARD_F: 31,
    Layer.COURTYARD_B: 29,
    Layer.FAB_F: 35,
    Layer.FAB_B: 33,
    Layer.DRAWINGS: 17,
    Layer.COMMENTS: 19,
    Layer.ECO1: 21,
    Layer.ECO2: 23,
    **{Layer(f"In{i + 1}.Cu"): 4 + 2 * i for i in range(KICAD_MAX_LAYER_CU)},
    **{Layer(f"User.{i + 1}"): 39 + 2 * i for i in range(KICAD_MAX_LAYER_USER)},
}

LayerUser = Literal[
    Layer.DRAWINGS,
    Layer.COMMENTS,
    Layer.ECO1,
    Layer.ECO2,
    Layer.USER1,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER2,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER3,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER4,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER5,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER6,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER7,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER8,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER9,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER10,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER11,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER12,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER13,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER14,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER15,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER16,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER17,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER18,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER19,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER20,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER21,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER22,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER23,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER24,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER25,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER26,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER27,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER28,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.USER29,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
]
LayerCopper = Literal[
    Layer.CU_F,
    Layer.CU_B,
    Layer.CU_IN1,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN2,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN3,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN4,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN5,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN6,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN7,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN8,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN9,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN10,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN11,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN12,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN13,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN14,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN15,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN16,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN17,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN18,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN19,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
    Layer.CU_IN20,  # type: ignore # ty:ignore[invalid-type-form, unresolved-attribute]
]

TL = TypeVar("TL", LayerUser, Layer)


class LayerSet(Generic[TL], set[TL]):
    __askiff_alias: ClassVar[set[str]] = {"layer", "layers"}

    def append(self, val: TL) -> None:
        if val.value.endswith("Cu") and Layer.CU_ALL in self:
            return
        self.add(val)

    def extend(self, val: Iterable[TL]) -> None:
        for v in val:
            self.append(v)

    def _askiff_key(self, name: str | None = None) -> str:
        return (
            name or "layer"
            if len(self) == (2 if Layer._KNOCKOUT in self else 1)
            and Layer.CU_ALL not in self
            and Layer.MASK_ALL not in self
            else "layers"
        )

    def serialize(self) -> GeneralizedSexpr:
        ser: set = self - {Layer._KNOCKOUT}
        return Sexpr(
            (
                *(Qstr(x.value) for x in sorted(ser, key=Layer.order_id)),
                *((str(Layer._KNOCKOUT.value),) if Layer._KNOCKOUT in self else ()),
            )
        )

    def serialize_nested(self) -> GeneralizedSexpr:
        ser: set = self - {Layer._KNOCKOUT}
        return tuple(("layer", Qstr(x.value)) for x in sorted(ser, key=Layer.order_id))


class BoardSide(Qstr, AutoSerdeEnum):
    """Indicates board side"""

    FRONT = "F.Cu"
    BACK = "B.Cu"


class Net(AutoSerde):
    number: int | None = F(positional=True)
    """Net identifier eg. `0` [Deprecated in K10]"""

    name: str | None = F(positional=True)
    """Net name eg. `"GND"`"""

    @classmethod
    def deserialize(cls, sexp: GeneralizedSexpr) -> Net:
        if isinstance(sexp[0], Qstr):
            return cls(name=sexp[0])
        return cls(int(sexp[0]), sexp[1] if len(sexp) > 1 else None)


###########################Zone############################


class SimplePolyFilled(BasePoly):
    _askiff_key: ClassVar[str] = "filled_polygon"
    layer: Layer = F(Layer.CU_F)
    _pts = F()


class ZoneOutlineHatchStyle(str, AutoSerdeEnum):
    NONE = "none"
    HATCH_EDGE = "edge"
    HATCH_FULL = "full"


class ZoneHatch(AutoSerde, positional=True):  # type: ignore
    style: ZoneOutlineHatchStyle = F(ZoneOutlineHatchStyle.HATCH_EDGE)
    pitch: float = 0.5


class ZoneTeardrop(AutoSerde):
    _askiff_key: ClassVar[str] = "teardrop"
    type: str = F(unquoted=True)


class ZoneKeepout(AutoSerde):
    tracks: bool = F(true_val="allowed", false_val="not_allowed")
    vias: bool = F(true_val="allowed", false_val="not_allowed")
    pads: bool = F(true_val="allowed", false_val="not_allowed")
    copperpour: bool = F(true_val="allowed", false_val="not_allowed")
    footprints: bool = F(true_val="allowed", false_val="not_allowed")


class ZonePlacement(AutoSerde):
    enabled: bool = False
    sheetname: str | None = None
    component_class: str | None = None
    """`component_class` & `sheetname` seem to be mutually exclusive"""


class ZoneFillMode(str, AutoSerdeEnum):
    HATCH = "hatch"
    SOLID = ""


class ZoneSmoothing(str, AutoSerdeEnum):
    CHAMFER = "chamfer"
    FILLET = "fillet"


class ZoneHatchSmoothing(str, AutoSerdeEnum):
    NONE = "0"
    CHAMFER = "1"
    ROUND = "2"
    ROUND_FINER = "3"


class ZoneIslandRemoval(str, AutoSerdeEnum):
    """Defines the island removal rule"""

    ALWAYS = "0"
    """Always remove islands"""
    NEVER = "1"
    """Never remove islands"""
    BELOW_AREA_LIMIT = "2"
    """Remove islands bellow area limit"""


class ZoneHatchBorderAlg(str, AutoSerdeEnum):
    """Indicates how zone border is handled with hatch fill"""

    HATCH_THICKNESS = "hatch_thickness"


class ZoneFill(AutoSerde):
    filled: bool = F(name="yes", flag=True, bare=True)
    """Has zone been filled? If yes, it likely has filled_polygon"""

    mode: ZoneFillMode = F(ZoneFillMode.SOLID)
    """Defines how the zone is filled"""

    thermal_gap: float | None = None
    """Distance from the zone to pad thermal relief connection"""

    thermal_bridge_width: float | None = None
    """Spoke width for pad thermal relief connection"""

    smoothing_style: ZoneSmoothing | None = F(name="smoothing")
    """Style of corner smoothing"""

    smoothing_radius: float | None = F(name="radius")
    """Radius of corner smoothing"""

    island_removal_mode: ZoneIslandRemoval | None = None
    """Defines the island removal rule"""

    island_area_min: float | None = None
    """Minimum allowed zone island area. Has effect only if `island_removal_mode` is set to `BELOW_AREA_LIMIT`"""

    hatch_thickness: float | None = None
    """Line thickness of hatch grid fill"""

    hatch_gap: float | None = None
    """Spacing between lines of hatch grid fill"""

    hatch_orientation: float | None = None
    """Line angle for hatched fills"""

    hatch_smoothing_level: ZoneHatchSmoothing | None = None
    """Defines how hatch outlines are smoothed"""

    hatch_smoothing_value: float | None = None
    """Ratio between the hole and the chamfer/fillet size.
    - 0 - no smoothing
    - 1 - max smoothing size (half of `hatch_gap`)"""

    hatch_border_algorithm: ZoneHatchBorderAlg | None = None
    """Defines if zone line thickness affects hatch fill border"""

    hatch_min_hole_area: float | None = None


class ZonePadConnectionStyle(str, AutoSerdeEnum):
    NO_CONNECT = "no"
    """Pads are not connect to zone"""

    THERMAL_RELIEF = ""
    """Pads are connected to zone using thermal reliefs"""

    SOLID = "yes"
    """Pads are connected to zone using solid fill"""

    THERMAL_RELIEF_THT = "thru_hole_only"
    """Only through hold pads are connected to zone using thermal reliefs"""


class ZonePadConnection(AutoSerde):
    style: ZonePadConnectionStyle = F(ZonePadConnectionStyle.THERMAL_RELIEF, positional=True)
    clearance: float | None = None
    """[Deprecated] Use `Zone` level `clearance`"""


class Zone(AutoSerde):
    net: Net | None = None
    net_name: str | None = None
    locked: bool | None = None
    layers: LayerSet[Layer] = F()
    uuid: Uuid | None = None
    name: str | None = None
    hatch: ZoneHatch = F()
    priority: int | None = None
    teardrop: ZoneTeardrop | None = F(name="attr", nested=True)
    connect_pads: ZonePadConnection = F()
    clearance: float = F(0.25, skip=True)
    min_thickness: float = 0.25
    filled_areas_thickness: bool | None = None
    keepout: ZoneKeepout | None = None
    placement: ZonePlacement | None = None
    fill: ZoneFill | None = None
    polygons: list[BasePoly] = F(name="polygon", flatten=True)
    filled_polygons: list[SimplePolyFilled] = F(name="filled_polygon", flatten=True)

    def _askiff_post_deser(self) -> None:
        if self.connect_pads.clearance:
            self.clearance = self.connect_pads.clearance

    def _askiff_pre_ser(self) -> Zone:
        if self.connect_pads.clearance:
            self.connect_pads.clearance = self.clearance
        return self


###########################Misc############################


class Point(AutoSerde):
    _askiff_key: ClassVar[str] = "point"
    position: Position = F(name="at")
    size: float = 1
    layer: Layer = F(Layer.DRAWINGS)
    uuid: Uuid = F()


class TeardropSettings(AutoSerde):
    best_length_ratio: float | None = None
    max_length: float | None = None
    best_width_ratio: float | None = None
    max_width: float | None = None
    curved_edges: bool | None = None
    filter_ratio: float | None = None
    enabled: bool | None = None
    allow_two_segments: bool | None = None
    prefer_zone_connections: bool | None = None
