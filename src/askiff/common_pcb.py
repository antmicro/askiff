from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator, MutableSet
from typing import TYPE_CHECKING, Any, ClassVar, Final, Generic, TypeVar, cast

from askiff._auto_serde import AutoSerde, AutoSerdeEnum, AutoSerdeFile, F
from askiff._sexpr import GeneralizedSexpr, Qstr
from askiff.common import BasePoly, Position, Uuid
from askiff.const import KICAD_MAX_LAYER_CU, KICAD_MAX_LAYER_USER, Version

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore

log = logging.getLogger()

###########################Layer###########################


class LayerFunction(str, AutoSerdeEnum):
    SIGNAL = "signal"
    JUMPER = "jumper"
    POWER = "power"
    MIXED = "mixed"
    AUX = "user"
    AUX_F = "front"
    AUX_B = "back"


class BaseLayer:
    _value: str
    _order_id: int
    name_map: ClassVar[dict[str, BaseLayer]]
    all: ClassVar[LayerSet[BaseLayer]]

    class __PrivateGuard(int):
        pass

    def order_id(self) -> int:
        return self._order_id

    def validate_function(self, function: LayerFunction | None) -> LayerFunction:
        return function or LayerFunction.AUX

    def serialize(self) -> GeneralizedSexpr:
        return (Qstr(self._value),)

    def __init_subclass__(cls) -> None:
        cls.name_map = {}
        cls.all = LayerSet()
        if not hasattr(BaseLayer, "all"):
            BaseLayer.name_map = {}
            BaseLayer.all = LayerSet()

    def __init__(self, value: str, order_id: int, _guard: __PrivateGuard) -> None:
        self._value = value
        self._order_id = order_id
        for parent in self.__class__.__mro__:
            if not issubclass(parent, BaseLayer):
                continue
            parent.name_map[value] = self
            parent.all._layers.add(self)

    def __str__(self) -> str:
        return self._value

    @classmethod
    def deserialize_downcast(cls, sexp: GeneralizedSexpr) -> BaseLayer:
        val = sexp if isinstance(sexp, str) else sexp[0]
        if not isinstance(val, str):
            raise TypeError("Layer is expected to be represented by string")
        if val not in BaseLayer.name_map:
            log.warning(
                f" Downcast failed: `{val}` does not match child types ({BaseLayer.name_map.keys()})",
                extra={"amodule": cls.__name__},
            )
            log.debug(sexp, extra={"amodule": cls.__name__})
            return BaseLayer(val, 999, BaseLayer.__PrivateGuard())
        return BaseLayer.name_map[val]


TL = TypeVar("TL", bound=BaseLayer)


class LayerSet(Generic[TL], AutoSerde, MutableSet[TL]):
    __askiff_alias: ClassVar[set[str]] = {"layer", "layers"}
    _layers: set[TL] = F(positional=True)
    _knockout: bool = F(name="knockout", flag=True, bare=True)

    def __init__(self, *args: TL) -> None:
        self._layers = set(args)
        self._knockout = False

    def append(self, val: TL) -> None:
        self.add(val)

    def extend(self, val: Iterable[TL]) -> None:
        for v in val:
            self.append(v)

    def __contains__(self, x: object) -> bool:
        if isinstance(x, Iterable):
            return all(self.__contains__(v) for v in x)
        return (
            x in self._layers
            or (isinstance(x, LayerCopper) and Layer.CU_ALL in self._layers)
            or (isinstance(x, LayerCopperOuter) and Layer.CU_FB in self._layers)
            or (isinstance(x, LayerCopperInner) and Layer.CU_IN_ALL in self._layers)
            or (isinstance(x, LayerMask) and Layer.MASK_ALL in self._layers)
        )

    def __iter__(self) -> Iterator[TL]:
        return iter(self._layers)

    def __len__(self) -> int:
        return len(self._layers)

    def add(self, value: TL) -> None:
        if self.__contains__(value):  # ty:ignore[invalid-argument-type]
            return
        self._layers.add(value)

    def discard(self, value: TL) -> None:
        self._layers.discard(value)

    def __eq__(self, other: Any) -> bool:  # noqa: ANN401
        if isinstance(other, LayerSet):
            return self._layers == other._layers
        if isinstance(other, set):
            return self._layers == other
        if isinstance(other, Iterable):
            other_len = 0
            for o in other:
                other_len += 1
                if o not in self:
                    return False
            return other_len == len(self)
        if len(self._layers) == 1:
            # Note: here intently we do not consider cases CU_ALL (CU_F is in CU_ALL, but CU_F != CU_ALL)
            return other in self._layers
        return NotImplemented

    def __str__(self) -> str:
        ret = ",".join(str(layer) for layer in self._layers)
        return ret if len(self._layers) == 1 else "{" + ret + "}"

    def _askiff_key(self, name: str | None = None) -> str:
        return (
            name or "layer"
            if len(self._layers) <= 1 and all(not isinstance(layer, LayerSpecial) for layer in self._layers)
            else "layers"
        )

    def serialize(self) -> GeneralizedSexpr:
        return (
            *(Qstr(x._value) for x in sorted(self._layers, key=BaseLayer.order_id)),
            *(("knockout",) if self._knockout else ()),
        )

    def serialize_nested(self) -> GeneralizedSexpr:
        return tuple(("layer", Qstr(x._value)) for x in sorted(self._layers, key=BaseLayer.order_id))

    @classmethod
    def deserialize_nested(cls, sexp: GeneralizedSexpr) -> LayerSet:
        return LayerSet(*(BaseLayer.deserialize_downcast(s[1]) for s in sexp))


class LayerCopper(BaseLayer):
    def validate_function(self, function: LayerFunction | None) -> LayerFunction:
        valid_functions = [LayerFunction.SIGNAL, LayerFunction.JUMPER, LayerFunction.POWER, LayerFunction.MIXED]
        return function if function in valid_functions else LayerFunction.SIGNAL


class LayerCopperOuter(LayerCopper):
    pass


class LayerCopperInner(LayerCopper):
    pass


class LayerTech(BaseLayer):
    def validate_function(self, function: LayerFunction | None) -> LayerFunction:
        valid_functions = [LayerFunction.AUX, LayerFunction.AUX_B, LayerFunction.AUX_F]

        return function if function in valid_functions else LayerFunction.AUX


class LayerPaste(LayerTech):
    pass


class LayerSilkS(LayerTech):
    pass


class LayerMask(LayerTech):
    pass


class LayerAdhesive(LayerTech):
    pass


class LayerCourtyard(LayerTech):
    pass


class LayerFab(LayerTech):
    pass


class LayerUser(BaseLayer):
    def validate_function(self, function: LayerFunction | None) -> LayerFunction:
        valid_functions = [LayerFunction.AUX, LayerFunction.AUX_B, LayerFunction.AUX_F]

        return function if function in valid_functions else LayerFunction.AUX


class LayerSpecial(BaseLayer):
    pass


class Layer:
    __PrivateGuard = BaseLayer._BaseLayer__PrivateGuard  # type: ignore  # ty:ignore[unresolved-attribute]
    CU_F: Final[LayerCopperOuter] = LayerCopperOuter("F.Cu", 0, __PrivateGuard())
    CU_B: Final[LayerCopperOuter] = LayerCopperOuter("B.Cu", 2, __PrivateGuard())
    ADHESIVE_F: Final[LayerAdhesive] = LayerAdhesive("F.Adhes", 9, __PrivateGuard())
    ADHESIVE_B: Final[LayerAdhesive] = LayerAdhesive("B.Adhes", 11, __PrivateGuard())
    PASTE_F: Final[LayerPaste] = LayerPaste("F.Paste", 13, __PrivateGuard())
    PASTE_B: Final[LayerPaste] = LayerPaste("B.Paste", 15, __PrivateGuard())
    SILKS_F: Final[LayerSilkS] = LayerSilkS("F.SilkS", 5, __PrivateGuard())
    SILKS_B: Final[LayerSilkS] = LayerSilkS("B.SilkS", 7, __PrivateGuard())
    MASK_F: Final[LayerMask] = LayerMask("F.Mask", 1, __PrivateGuard())
    MASK_B: Final[LayerMask] = LayerMask("B.Mask", 3, __PrivateGuard())
    EDGE_CUTS: Final[LayerTech] = LayerTech("Edge.Cuts", 25, __PrivateGuard())
    MARGIN: Final[LayerTech] = LayerTech("Margin", 27, __PrivateGuard())
    COURTYARD_F: Final[LayerCourtyard] = LayerCourtyard("F.CrtYd", 31, __PrivateGuard())
    COURTYARD_B: Final[LayerCourtyard] = LayerCourtyard("B.CrtYd", 29, __PrivateGuard())
    FAB_F: Final[LayerFab] = LayerFab("F.Fab", 35, __PrivateGuard())
    FAB_B: Final[LayerFab] = LayerFab("B.Fab", 33, __PrivateGuard())
    DRAWINGS: Final[LayerUser] = LayerUser("Dwgs.User", 17, __PrivateGuard())
    COMMENTS: Final[LayerUser] = LayerUser("Cmts.User", 19, __PrivateGuard())
    ECO1: Final[LayerUser] = LayerUser("Eco1.User", 21, __PrivateGuard())
    ECO2: Final[LayerUser] = LayerUser("Eco2.User", 23, __PrivateGuard())

    CU_ALL: Final[LayerSpecial] = LayerSpecial("*.Cu", 0, __PrivateGuard())
    CU_FB: Final[LayerSpecial] = LayerSpecial(
        "F&B.Cu", 0, __PrivateGuard()
    )  # used in tht pads that are top&bottom only
    CU_IN_ALL: Final[LayerSpecial] = LayerSpecial("Inner", 1, __PrivateGuard())
    """Only used inside pad stack; all inner copper layers"""

    MASK_ALL: Final[LayerSpecial] = LayerSpecial("*.Mask", 1, __PrivateGuard())

    @staticmethod
    def CU_IN(number: int) -> LayerCopperInner:  # noqa: N802
        if 1 <= number <= KICAD_MAX_LAYER_CU:
            return LayerCopperInner(f"In{number}.Cu", 2 + 2 * number, Layer.__PrivateGuard())
        raise ValueError(f"In{number}.Cu is not supported, number should be between 1 & {KICAD_MAX_LAYER_CU}")

    @staticmethod
    def USER(number: int) -> LayerUser:  # noqa: N802
        if 1 <= number <= KICAD_MAX_LAYER_USER:
            return LayerUser(f"User.{number}", 37 + 2 * number, Layer.__PrivateGuard())
        raise ValueError(f"User.{number} is not supported, number should be between 1 & {KICAD_MAX_LAYER_USER}")


# Cycle procedural layers, so that they are added in BaseLayer._know_layers
for i in range(1, KICAD_MAX_LAYER_CU + 1):
    Layer.CU_IN(i)
for i in range(1, KICAD_MAX_LAYER_USER + 1):
    Layer.USER(i)


class BoardSide(Qstr, AutoSerdeEnum):
    """Indicates board side"""

    FRONT = "F.Cu"
    BACK = "B.Cu"


class NetBase:
    name: str


class Net(NetBase, AutoSerde):
    _number: int | None = F(positional=True, skip=True).version(Version.K9.pcb, skip=False)
    """Net identifier eg. `0` [Deprecated in K10]"""

    name: str = F(positional=True)
    """Net name eg. `"GND"`"""


class NetSimple(NetBase, AutoSerde):
    _number: int | None = F(positional=True, skip=True).version(Version.K9.pcb, skip=False)
    """Net identifier eg. `0` [Deprecated in K10]"""
    name: str = F(positional=True).version(Version.K9.pcb, skip=True)  # type: ignore
    """Net name eg. `"GND"`"""

    def _askiff_post_deser(self) -> None:
        AutoSerdeFile._post_final_deser_objects.append(self)

    def _post_final_deser(self, root_object) -> None:  # type: ignore # noqa: ANN001
        """Retrieve net name from board level net map, after whole board is deserialized"""
        # Note: annotation skipped to prevent circular imports
        if self.name is not None or not hasattr(root_object, "nets"):
            return
        nr = self._number
        self.name = next((net.name for net in root_object.nets or () if net._number == nr), "Unknown")


###########################Zone############################


class SimplePolyFilled(BasePoly):
    _askiff_key: ClassVar[str] = "filled_polygon"
    layer: LayerCopper = F(Layer.CU_F)
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
    net: NetSimple | None = None
    net_name: str | None = None
    locked: bool | None = None
    layers: LayerSet[BaseLayer] = F()
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
    layer: BaseLayer = F(Layer.DRAWINGS)
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
