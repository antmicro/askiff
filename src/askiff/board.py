from __future__ import annotations

import logging
from copy import copy, deepcopy
from typing import TYPE_CHECKING, Any, ClassVar, Final, Self, cast

from askiff._auto_serde import (
    AutoSerde,
    AutoSerdeDownCasting,
    AutoSerdeDownCastingAgg,
    AutoSerdeEnum,
    AutoSerdeFile,
    F,
    SerMode,
)
from askiff._sexpr import GeneralizedSexpr, Qstr, Sexpr
from askiff.common import BaseArc, BaseLine, BasePoly, EmbeddedFile, Group, Paper, Position, TitleBlock, Uuid
from askiff.common_pcb import (
    BaseLayer,
    Layer,
    LayerCopper,
    LayerFunction,
    LayerSet,
    LayerTech,
    Net,
    Point,
    Zone,
    _NetK9Simple,
)
from askiff.const import Version
from askiff.footprint import Footprint, FootprintBoard
from askiff.fp_pad import AfterDrill, DrillPostMatching, PadStackMode, TeardropSettings
from askiff.gritems import Barcode, Dimension, GrItemPCB, GrTablePCB

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore


log = logging.getLogger()


class StackupLayer(AutoSerdeDownCasting):
    """Represents a layer in a PCB stackup configuration.

    Class not intended for direct instantiation, instantiate via subclasses"""

    _askiff_key: Final[str] = "layer"
    _AutoSerdeDownCasting__downcast_field: ClassVar[str] = "type"

    layer: str = F("", positional=True)
    """Layer name in the PCB stackup configuration."""

    type: Final[str] = F()  # type: ignore  # ty:ignore[override-of-final-variable]
    """Type of layer in PCB stackup configuration."""


class StackupLayerDielectricSubLayer(AutoSerde):
    """Class representing a sublayer within a dielectric stackup layer"""

    color: str | None = None
    """Color of the sublayer."""

    thickness: float = 0.12
    """Sublayer thickness in millimeters"""

    locked: bool | None = F(skip=True)
    """Whether the sublayer properties are locked against changes."""

    material: str | None = None
    """Sublayer material"""

    epsilon_r: float = 4.2
    """Relative permittivity of the dielectric material."""

    loss_tangent: float = 0
    """Loss tangent of the dielectric material."""

    def _askiff_pre_ser(self) -> StackupLayerDielectricSubLayer:
        if self.locked:
            ret = copy(self)
            ret._AutoSerde__ser_field = deepcopy(self._AutoSerde__ser_field)  # type: ignore # ty:ignore[unresolved-attribute]
            ret._AutoSerde__ser_field["thickness"] = "thickness", (SerMode.SERIALIZE, None, True)  # type: ignore # ty:ignore[unresolved-attribute]
            ret.thickness = Sexpr((str(self.thickness), "locked"))  # type: ignore # ty:ignore[invalid-assignment]
            return ret
        return self


class StackupLayerDielectric(StackupLayer):
    """Represents a dielectric layer in a PCB stackup configuration.

    Instantiate via subclasses :class:`askiff.board.StackupLayerDielectricCore`
    and :class:`askiff.board.StackupLayerDielectricPrepreg`"""

    layer: str = F("dielectric 1", positional=True)
    """Layer name"""

    type: Final[str] = ""  # type: ignore  # ty:ignore[override-of-final-variable]
    """Type of dielectric layer"""

    sublayers: list[StackupLayerDielectricSubLayer] = F(lambda: [StackupLayerDielectricSubLayer()])
    """Sublayers within this layer."""

    @classmethod
    def deserialize(cls, sexp: GeneralizedSexpr) -> StackupLayerDielectric:
        ret = StackupLayerDielectric(layer="")  # type: ignore
        for node in sexp:
            if isinstance(node, str):
                if node == "addsublayer":
                    ret.sublayers.append(StackupLayerDielectricSubLayer())
                elif not ret.layer:
                    ret.layer = node
                else:
                    if ret._AutoSerde__extra_positional is None:  # type: ignore # ty:ignore[unresolved-attribute]
                        ret._AutoSerde__extra_positional = Sexpr()  # type: ignore # ty:ignore[unresolved-attribute]
                    ret._AutoSerde__extra_positional.append(node)  # type: ignore # ty:ignore[unresolved-attribute]
                    log.warning(f" Unexpected positional node: `{node}`", extra={"amodule": cls.__name__})
                continue
            node_name, *node_val = node
            match node_name:
                case "type":
                    if not isinstance(node_val[0], str):
                        raise TypeError("Stackup Layer type is expected to be string")
                    ret.type = node_val[0]  # type: ignore  # ty:ignore[invalid-assignment]
                case "color" | "material":
                    setattr(ret.sublayers[-1], node_name, node_val[0])
                case "epsilon_r" | "loss_tangent":
                    if not isinstance(node_val[0], str):
                        raise TypeError(f"Stackup Layer {node_name} is expected to be string convertible to float")
                    setattr(ret.sublayers[-1], node_name, float(node_val[0]))
                case "thickness":
                    if not isinstance(node_val[0], str):
                        raise TypeError("Stackup Layer thickness is expected to be string convertible to float")
                    ret.sublayers[-1].thickness = float(node_val[0])
                    if node_val[1:] and node_val[1] == "locked":
                        ret.sublayers[-1].locked = True
                case _:
                    if ret._AutoSerde__extra is None:  # type: ignore # ty:ignore[unresolved-attribute]
                        ret._AutoSerde__extra = Sexpr()  # type: ignore # ty:ignore[unresolved-attribute]
                    ret._AutoSerde__extra.append(node)  # type: ignore # ty:ignore[unresolved-attribute]
                    log.warning(f" Unexpected node: `{node_name}`", extra={"amodule": cls.__name__})
                    log.debug(node, extra={"amodule": cls.__name__})
        return ret

    def serialize(self) -> GeneralizedSexpr:
        ret = [
            Qstr(self.layer),
            *(self._AutoSerde__extra_positional or ()),  # type: ignore # ty:ignore[unresolved-attribute]
            ("type", Qstr(self.type)),
            *(self.sublayers[0].serialize()),
        ]
        for sublayer in self.sublayers[1:]:
            ret.extend(("addsublayer", *(sublayer.serialize())))
        ret.extend(self._AutoSerde__extra or ())  # type: ignore # ty:ignore[unresolved-attribute]
        return ret


class StackupLayerDielectricCore(StackupLayerDielectric):
    """Represents a dielectric core layer in a PCB stackup configuration."""

    layer: str = F("dielectric 1", positional=True)
    """Layer name"""

    type: Final[str] = "core"  # type: ignore  # ty:ignore[override-of-final-variable]
    """Type of dielectric layer, constant class keyword"""


class StackupLayerDielectricPrepreg(StackupLayerDielectric):
    """Represents a dielectric layer of type 'prepreg' in a KiCad PCB stackup configuration.
    Used to define prepreg materials, which are fibrous reinforcements impregnated with resin."""

    layer: str = F("dielectric 1", positional=True)
    """Layer name."""

    type: Final[str] = "prepreg"  # type: ignore  # ty:ignore[override-of-final-variable]
    """Type of dielectric layer, constant class keyword"""


class StackupLayerCopper(StackupLayer):
    """Represents a copper layer in a PCB stackup configuration."""

    layer: LayerCopper = F(Layer.CU_F, positional=True)  # type: ignore
    """Which standard KiCad layer this stackup layer maps to"""

    type: Final[str] = "copper"  # type: ignore  # ty:ignore[override-of-final-variable]
    """Type of layer, constant class keyword"""

    thickness: float = 0.035
    """Copper layer thickness in millimeters"""


class StackupLayerMask(StackupLayer):
    """Represents a mask layer in a PCB stackup configuration.

    Class not intended for direct instantiation, instantiate via subclasses"""

    type: Final[str] = ""  # type: ignore  # ty:ignore[override-of-final-variable]
    """Type of layer, constant class keyword"""

    color: str | None = None
    """Color of the mask layer."""

    thickness: float = 0.01
    """Mask layer thickness in millimeters"""

    material: str | None = None
    """Material of the mask layer."""

    epsilon_r: float | None = None
    """Relative permittivity of the mask layer material."""

    loss_tangent: float | None = None
    """Loss tangent of the mask layer material."""


class StackupLayerMaskTop(StackupLayerMask):
    """Represents the top solder mask layer in a PCB stackup configuration."""

    layer: Final[LayerTech] = F(Layer.MASK_F, positional=True, after="__begin__")  # type: ignore
    """Which standard KiCad layer this stackup layer maps to
    
    Constant for class, use other :class:`askiff.board.StackupLayer` subclasses for other standard layers"""

    type: Final[str] = F("Top Solder Mask")  # type: ignore  # ty:ignore[override-of-final-variable]
    """Type of layer, constant class keyword"""


class StackupLayerMaskBottom(StackupLayerMask):
    """Represents the bottom solder mask layer in a PCB stackup configuration."""

    layer: Final[LayerTech] = F(Layer.MASK_B, positional=True, after="__begin__")  # type: ignore
    """Which standard KiCad layer this stackup layer maps to
    
    Constant for class, use other :class:`askiff.board.StackupLayer` subclasses for other standard layers"""

    type: Final[str] = "Bottom Solder Mask"  # type: ignore  # ty:ignore[override-of-final-variable]
    """Type of layer, constant class keyword"""


class StackupLayerPasteTop(StackupLayer):
    """Represents the top solder paste layer in a KiCad PCB stackup configuration."""

    layer: Final[LayerTech] = F(Layer.PASTE_F, positional=True, after="__begin__")  # type: ignore
    """Which standard KiCad layer this stackup layer maps to
    
    Constant for class, use other :class:`askiff.board.StackupLayer` subclasses for other standard layers"""

    type: Final[str] = "Top Solder Paste"  # type: ignore  # ty:ignore[override-of-final-variable]
    """Type of layer, constant class keyword"""


class StackupLayerPasteBottom(StackupLayer):
    """Represents the bottom solder paste layer in a PCB stackup configuration."""

    layer: Final[LayerTech] = F(Layer.PASTE_B, positional=True, after="__begin__")  # type: ignore
    """Which standard KiCad layer this stackup layer maps to
    
    Constant for class, use other :class:`askiff.board.StackupLayer` subclasses for other standard layers"""

    type: Final[str] = "Bottom Solder Paste"  # type: ignore  # ty:ignore[override-of-final-variable]
    """Type of layer, constant class keyword"""


class StackupLayerSilks(StackupLayer):
    """Represents a silkscreen layer in a PCB stackup configuration.

    Class not intended for direct instantiation, instantiate via subclasses"""

    type: Final[str] = ""  # type: ignore  # ty:ignore[override-of-final-variable]
    """Type of layer, constant class keyword"""

    color: str | None = None
    """Color of the silkscreen layer."""

    material: str | None = None
    """Material of the silkscreen layer."""


class StackupLayerSilksTop(StackupLayerSilks):
    """Represents the top silkscreen layer in a KiCad PCB stackup configuration."""

    layer: Final[LayerTech] = F(Layer.SILKS_F, positional=True, after="__begin__")  # type: ignore
    """Which standard KiCad layer this stackup layer maps to
    
    Constant for class, use other :class:`askiff.board.StackupLayer` subclasses for other standard layers"""

    type: Final[str] = "Top Silk Screen"  # type: ignore  # ty:ignore[override-of-final-variable]
    """Type of layer, constant class keyword"""


class StackupLayerSilksBottom(StackupLayerSilks):
    """Represents the bottom silkscreen layer in a KiCad PCB stackup configuration."""

    layer: Final[LayerTech] = F(Layer.SILKS_B, positional=True, after="__begin__")  # type: ignore
    """Which standard KiCad layer this stackup layer maps to
    
    Constant for class, use other :class:`askiff.board.StackupLayer` subclasses for other standard layers"""

    type: Final[str] = "Bottom Silk Screen"  # type: ignore  # ty:ignore[override-of-final-variable]
    """Type of layer, constant class keyword"""


class StackupEdgeConn(str, AutoSerdeEnum):
    """Represents the manufacturing style of edge connectors"""

    BEVELLED = "bevelled"
    SIMPLE = "yes"
    NONE = ""


class StackupCopperFinish(Qstr, AutoSerdeEnum):
    """Enum representing available copper finish options for PCB.
    Used in KiCad's board design files to specify surface finish treatment"""

    ENIG = "ENIG"
    ENEPIG = "ENEPIG"
    USER_DEFINED = "User defined"
    NONE = "None"
    OSP = "OSP"
    HT_OSP = "HT_OSP"
    HAL_SN_PB = "HAL SnPb"
    HAL_LEAD_FREE = "HAL lead-free"
    HARD_GOLD = "Hard gold"
    IMMERSION_GOLD = "Immersion gold"
    IMMERSION_TIN = "Immersion tin"
    IMMERSION_NICKEL = "Immersion nickel"
    IMMERSION_SILVER = "Immersion silver"
    UNDEFINED = ""


class Stackup(AutoSerde):
    """PCB stackup configuration defining layer structure, copper finish, and manufacturing constraints."""

    layers: list[StackupLayer] = F(flatten=True, name="layer")
    """PCB stackup layers with layer thickness and material properties."""

    copper_finish: StackupCopperFinish = F(StackupCopperFinish.ENIG)
    """Copper finish type for the PCB surface"""

    dielectric_constraints: bool | None = None
    """Whether dielectric parameters are taken into account for constraints"""

    edge_connector: StackupEdgeConn = F(StackupEdgeConn.NONE)
    """Edge connectors style"""

    castellated_pads: bool | None = None
    """Whether castellated pads are enabled for the PCB"""

    edge_plating: bool | None = None
    """Whether edge plating is enabled for the PCB"""


class LayerDef(AutoSerde, positional=True):  # type: ignore
    """Layer definition, mapping a standard KiCad layer to its function and optional user-defined name."""

    layer: BaseLayer = F()
    """Standard KiCad layer"""

    function: LayerFunction = F()
    """Layer functional purpose"""

    user_name: str | None = None
    """User-defined name for the layer."""

    def __init__(
        self, layer: BaseLayer = Layer.CU_F, function: LayerFunction | None = None, user_name: str | None = None
    ) -> None:
        self.layer = layer
        self.function = layer.validate_function(function)
        self.user_name = user_name

    def _askiff_key(self) -> str:
        """Key used to identify the layer definition in a KiCad file. Derived from the layer's order identifier."""
        return str(self.layer.order_id())


class TraceBase(AutoSerdeDownCastingAgg):
    """Base class for KiCad trace objects

    Not intended for direct instantiation, use subclasses"""

    locked: bool | None = None
    """Whether the trace is locked."""

    solder_mask_margin: float | None = None
    """Margin for solder mask opening around the trace."""

    net: Net = F().version(Version.K9.pcb, serialize=_NetK9Simple._ser, deserialize=_NetK9Simple.deserialize)
    """Associated signal net"""

    uuid: Uuid = F()
    """Unique identifier"""


class TraceCopper(TraceBase):
    """Copper trace object"""

    _layers: LayerSet[BaseLayer] = F(after="locked")
    layer: LayerCopper = F(Layer.CU_F, skip=True)
    """Copper layer where the trace is placed."""

    def _askiff_post_deser(self) -> None:
        self.layer = next(x for x in self._layers if isinstance(x, LayerCopper))

    def _askiff_pre_ser(self) -> Self:
        """Prepares the trace for serialization by initializing its layer set and adjusting solder mask margin behavior.
        If `solder_mask_margin` is set, it is cleared unless the trace is on the top or bottom copper layer.
        In such cases, the corresponding mask layer is added to the layer set."""
        self._layers = LayerSet(self.layer)
        if self.solder_mask_margin:
            if self.layer not in (Layer.CU_B, Layer.CU_F):
                self.solder_mask_margin = None
            else:
                self._layers.add(Layer.MASK_F if self.layer == Layer.CU_F else Layer.MASK_B)
        return self


class TraceSegment(TraceCopper, BaseLine):
    """Represents a straight segment of a copper trace on PCB"""

    _askiff_key: ClassVar[str] = "segment"
    width: float = F(0.2, after="end")
    """Trace segment width in millimeters."""


class TraceArc(TraceCopper, BaseArc):
    """Represents a curved copper trace segment on PCB"""

    _askiff_key: ClassVar[str] = "arc"
    width: float = F(0.2, after="end")
    """Trace width in millimeters."""


class ViaType(str, AutoSerdeEnum):
    """Enum representing the type of a via"""

    THRU = ""
    BLIND = "blind"
    MICRO = "micro"


class ViaSidedBool(AutoSerde):
    """Boolean flags for front and back sides of a via"""

    front: bool = False
    """Whether the described property applies to the front side of the board"""
    back: bool = False
    """Whether the described property applies to the back side of the board"""


class ViaTenting(AutoSerde):
    """Represents via tenting configuration, controlling whether via is tented on front and/or back layer"""

    front: bool = F(false_val="none").version(Version.K9.pcb, bare=True, flag=True)
    """Whether via is tented on front layer."""
    back: bool = F(false_val="none").version(Version.K9.pcb, bare=True, flag=True)
    """Whether via is tented on the back layer."""

    def serialize(self) -> GeneralizedSexpr:
        if AutoSerdeFile._version <= Version.K9.pcb:
            return (
                *(("front",) if self.front else ()),
                *(("back",) if self.back else ()),
                *(self._AutoSerde__extra_positional or ()),  # type: ignore # ty:ignore[unresolved-attribute]
                *(self._AutoSerde__extra or ()),  # type: ignore # ty:ignore[unresolved-attribute]
            )

        if not self.front and not self.back:
            front, back = "no", "no"
        else:
            front = "yes" if self.front else "none"
            back = "yes" if self.back else "none"
        return (
            *(self._AutoSerde__extra_positional or ()),  # type: ignore # ty:ignore[unresolved-attribute]
            ("front", front),
            ("back", back),
            *(self._AutoSerde__extra or ()),  # type: ignore # ty:ignore[unresolved-attribute]
        )


class ViaPadStackLayer(AutoSerde):
    """Represents a layer in a via's pad stack, defining the copper layer and pad size."""

    _askiff_key: ClassVar[str] = "layer"
    layer: LayerCopper = F(Layer.CU_F, positional=True)
    """Copper layer of the via pad stack."""
    size: float = 0.45
    """Pad size for the via on this layer."""


class ViaPadStack(AutoSerde):
    """ViaPadStack represents a via's pad stack configuration in KiCad, defining its mode and layer structure."""

    mode: PadStackMode = F(PadStackMode.FRONT_INNER_BACK)
    """Via pad stack mode configuration."""
    layers: list[ViaPadStackLayer] = F(flatten=True, name="layer")
    """Layers of the via's pad stack."""


class ViaSpanLayers(AutoSerde, positional=True):  # type: ignore
    """Represents via span layers for drill start and stop layers"""

    start_layer: LayerCopper = F(Layer.CU_F)
    """Drill start layer (for buried via, board side for through via)"""
    stop_layer: LayerCopper = F(Layer.CU_B)
    """stop layer / how deep should drill extend"""


class Via(TraceBase):
    """Via represents instance o via along its physical features."""

    _askiff_key: ClassVar[str] = "via"
    type: ViaType = F(ViaType.THRU, positional=True)
    """Via type, such as through-hole, blind, or micro."""
    position: Position = F(name="at", after="__begin__")
    """Position of the via on PCB"""
    size: float = 0.45
    """Via diameter including annular ring."""
    drill: float = 0.1
    """Via drill diameter."""
    backdrill: AfterDrill | None = None
    """Backdrill parameters"""
    tertiary_drill: AfterDrill | None = None
    """Additional drill configuration after initial drilling operation"""
    front_post_machining: DrillPostMatching | None = None
    """Front post-machining settings"""
    back_post_machining: DrillPostMatching | None = None
    """Back post-machining settings"""
    layers: ViaSpanLayers = F()
    """Via layers span including start and stop layers."""
    _locked = F()
    remove_unused_layers: bool | None = None
    """Whether to add annular ring on layers that are unconnected."""
    keep_end_layers: bool | None = None
    """Whether `remove_unused_layers` affects also start/end layer of via"""
    free: bool | None = None
    """Whether the via is net is auto updated"""
    zone_layer_connections: LayerSet[LayerCopper] | None = F(name="zone_layer_connections", keep_empty=True)
    """Copper layers via is currently attached to"""
    tenting: ViaTenting | None = None
    """Via tenting configuration."""
    capping: bool | None = None
    """Whether via has a capping mask applied."""
    covering: ViaSidedBool | None = None
    """Whether the via is covered"""
    plugging: ViaSidedBool | None = None
    """Whether the via is plugged on front or back side"""
    filling: bool | None = None
    """Whether the via is filled"""
    padstack: ViaPadStack | None = None
    """Via pad stack configuration including mode and layers."""
    teardrops: TeardropSettings | None = None
    """Configure how connections to via should create teardrops"""


class Generated(AutoSerdeDownCasting):
    """Base class for KiCad "generated" items, such as those found in schematic and board files.

    Class not designed for direct instantiation, use subclasses"""

    _AutoSerdeDownCasting__downcast_field: ClassVar[str] = "type"
    uuid: Uuid = F()
    """Unique identifier"""
    type: Final[str] = F(unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Type of generated KiCad item."""


class GeneratedTuningInitialSide(Qstr, AutoSerdeEnum):
    """Enum for specifying the initial side of a generated tuning parameter"""

    RIGHT = "right"
    LEFT = "left"


class GeneratedTuningStatus(Qstr, AutoSerdeEnum):
    """Enum representing the tuning status of generated items, such as tracks or vias, in KiCad.
    Indicates whether an item is too long, too short, or properly tuned."""

    TOO_LONG = "too_long"
    TOO_SHORT = "too_short"
    TUNED = "tuned"


class GeneratedTuningMode(Qstr, AutoSerdeEnum):
    """Enum representing the generated tuning mode"""

    BETWEEN_PAIRS = "diff_pair"
    INSIDE_PAIR = "diff_pair_skew"
    SINGLE_TRACE = "single"


class GeneratedTuningPattern(Generated, Group):
    """A generated tuning pattern object, represents a tuning region with meandered paths for trace delay control"""

    _uuid = F()
    type: Final[str] = F("tuning_pattern", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """KiCad keyword, class constant"""

    name: str = "Tuning Pattern"
    """Name of the tuning pattern object"""

    layer: LayerCopper = F(Layer.CU_F)
    """Layer the track resides on."""

    _locked = F()

    base_line: BasePoly | None = None
    """Base polygon representing the original trace shape before tuning modifications."""

    base_line_coupled: BasePoly | None = None
    """Base polygon representing the original coupled trace shape before tuning adjustments."""

    corner_radius_percent: int = 0
    """Corner radius of the tuning pattern as a percentage of the trace width."""

    end: Position = F(nested=True)
    """Ending point of the tuning region."""

    initial_side: GeneratedTuningInitialSide = F(GeneratedTuningInitialSide.LEFT)
    """Indicates on which track side is first meander"""

    is_time_domain: bool | None = None
    """Whether tuning is resolved in time domain vs length domain"""

    last_diff_pair_gap: float = 0
    """Gap of diff pair of the tuned track (as of last tuning refresh)"""

    last_netname: str = ""
    """Net name of track (as of last tuning refresh)"""

    last_status: GeneratedTuningStatus = F(GeneratedTuningStatus.TUNED)
    """Status of the tuned track (as of last tuning refresh)"""

    last_track_width: float = 0
    """Width of the tuned track (as of last tuning refresh)"""

    last_tuning: str | None = None
    """[K10:Deprecated] Length of the tuned track (as of last tuning refresh), 
    stores sth like `"20.8195 mm (too short)"`"""

    last_tuning_length: float | None = None
    """Length of the tuned track from the last tuning operation."""

    max_amplitude: float = 0
    """Maximum amplitude of the meander pattern"""

    min_amplitude: float = 0
    """Minimal amplitude of meander"""

    min_spacing: float = 0
    """Minimum spacing between meander curves in the tuning pattern"""

    origin: Position = F(nested=True)
    """Starting point of tuning region"""

    override_custom_rules: bool = False
    """Whether custom rules are overridden for this tuning pattern"""

    rounded: bool = False
    """Whether the meander is rounded rather than chamfered."""

    single_sided: bool = False
    """Whether meanders are on one side of the track only"""

    target_delay: float | None = None
    """Target delay setting for the tuning pattern."""

    target_delay_max: float | None = None
    """Maximum target delay for the tuning pattern."""

    target_delay_min: float | None = None
    """Minimum target delay for the tuning pattern."""

    target_length: float = 0
    """Target length for the tuning pattern in millimeters."""

    target_length_max: float = 0
    """Maximum target length for the tuning pattern."""

    target_length_min: float = 0
    """Minimum target length for the tuning pattern meander."""

    target_skew: float = 0
    """Target skew value for differential trace impedance control."""

    target_skew_max: float = 0
    """Maximum target skew for the tuning pattern."""

    target_skew_min: float = 0
    """Minimum target skew for differential trace tuning."""

    tuning_mode: GeneratedTuningMode = F(GeneratedTuningMode.SINGLE_TRACE)
    """Mode of tuning pattern application"""

    _members = F()
    """Uuids of trace primitives that were generated by this object"""


class PCBExportSettingsPlotMode(str, AutoSerdeEnum):
    """Enumeration for KiCad's PCB plot mode settings, used in export configurations"""

    STANDARD = "1"
    OUTLINE = "2"


class PCBExportSettingsOutputFormat(str, AutoSerdeEnum):
    """Enumeration of output formats supported for PCB export settings"""

    GERBER = "0"
    POST_SCRIPT = "1"
    SVG = "2"
    DXF = "3"
    HPGL = "4"
    PDF = "5"


class PCBExportSettings(AutoSerde, name_case="lower"):  # type: ignore
    """Class representing KiCad PCB export settings for controlling plot output behavior.
    Configures layer selection, plot modes, file formats, and export options including gerber, SVG, DXF, and PDF."""

    layer_selection: str = F(unquoted=True)
    """Hexadecimal bit flags of layers that shall be plotted"""

    plot_on_all_layers_selection: str | None = F("0x00000000_00000000_00000000_00000000", unquoted=True, name_case=None)
    """Hexadecimal bit flags of layers that shall be plotted on each plot"""

    disable_apert_macros: bool = False
    """Whether to disable use of aperture macros in gerber plots"""

    use_gerber_extensions: bool = False
    """Whether Protel file name extensions are used for gerber plots"""

    use_gerber_attributes: bool = False
    """Whether X2 extensions are used in gerber plots"""

    use_gerber_advanced_attributes: bool = False
    """Whether advanced attributes are included in gerber plot output"""

    create_gerber_job_file: bool = False
    """Whether to create a job file when plotting gerber files"""

    dashed_line_dash_ratio: float = F(12, name_case=None).version(Version.K9.pcb, keep_trailing=True)
    """Dash size of dashed line, where value of one is 0.05 mm"""

    dashed_line_gap_ratio: float = F(3, name_case=None).version(Version.K9.pcb, keep_trailing=True)
    """Ratio of gap size for dashed lines, where one unit equals 0.05 mm"""

    svg_precision: float = 0.0
    """SVG plotting precision setting."""

    plot_frame_ref: bool = False
    """Whether the border and title block should be included in the plot output."""

    mode: PCBExportSettingsPlotMode = F(PCBExportSettingsPlotMode.STANDARD)
    """PCB plot mode setting controlling standard or outline-only rendering."""

    use_aux_origin: bool = False
    """Whether all coordinates are defined in relation to auxiliary origin"""

    hpgl_pen_number: int | None = None
    """HPGL plot pen number to use for plotting"""

    hpgl_pen_speed: int | None = None
    """HPGL plot pen speed setting"""

    hpgl_pen_diameter: float | None = F().version(Version.K9.pcb, keep_trailing=True)
    """HPGL plot pen size value"""

    pdf_front_fp_property_popups: bool = F(False, name_case=None)
    """Whether interactive popups with part information are added for the front side in the generated PDF"""

    pdf_back_fp_property_popups: bool = F(False, name_case=None)
    """Whether interactive popups with part information are added for the back side in the generated PDF"""

    pdf_metadata: bool = F(False, name_case=None)
    """Whether PDF metadata is included in exported plots."""

    pdf_single_document: bool = F(False, name_case=None)
    """Whether to export all layers into a single PDF document."""

    dxf_polygon_mode: bool = False
    """Whether polygon mode is enabled for DXF plot output."""

    dxf_imperial_units: bool = False
    """Whether imperial units are used for DXF plot output."""

    dxf_use_pcbnew_font: bool = False
    """Whether to use the pcbnew vector font for DXF plots instead of the default font."""

    ps_negative: bool = False
    """Whether PostScript output uses negative logic."""

    ps_a4_output: bool = False
    """Whether A4 sized PostScript plots are enabled."""

    plot_black_and_white: bool = F(False, name_case=None)
    """Whether to ignore layer colors and plot in black and white"""

    plot_reference: bool | None = None
    """Whether to plot hidden reference field"""

    plot_value: bool | None = None
    """Whether to plot hidden value field"""

    plot_invisible_text: bool | None = None
    """Whether to plot other hidden text (not value, not reference)"""

    sketch_pads_on_fab: bool = False
    """Whether pads are plotted in outline (sketch) mode"""

    plot_pad_numbers: bool = False
    """Whether pad numbers are included in the plot output."""

    hide_dnp_on_fab: bool = False
    """Whether to remove DNP components on Fab layer plots"""

    sketch_dnp_on_fab: bool = True
    """Whether to plot DNP components in outline mode on Fab layer plots"""

    cross_out_dnp_on_fab: bool = True
    """Whether to cross out DNP components on Fab layer plots"""

    subtract_mask_from_silk: bool = False
    """Whether solder mask is subtracted from silk screen layers in gerber plots"""

    output_format: PCBExportSettingsOutputFormat = F(PCBExportSettingsOutputFormat.GERBER)
    """Output format for PCB export settings."""

    mirror: bool = False
    """Whether the plot output is mirrored during export."""

    drill_shape: int = 0
    """Shape used to mark drills"""

    scale_selection: int = 1
    """Scale selection for PCB plot output."""

    output_directory: str = ""
    """Directory path for saving plot output files relative to project folder"""

    plot_fp_text: bool | None = None
    """Whether to print footprint text in output"""

    viasonmask: bool | None = F(skip=True).version(Version.K8.pcb, name="viasonmask", skip=False)
    """[K9: Deprecated]"""


class BoardSetupZoneDefault(AutoSerde):
    """Represents default zone setup properties for a KiCad board"""

    _askiff_key: ClassVar[str] = "property"
    layer: LayerCopper = F(Layer.CU_F)
    """Copper layer for the default zone setup."""
    hatch_position: Position = F(nested=True)
    """Hatch pattern position within the zone."""


class BoardSetup(AutoSerde):
    """BoardSetup defines the electrical and physical configuration of a KiCad PCB,
    including stackup, solder mask and paste settings, via options, and export parameters."""

    stackup: Stackup = F()
    """PCB physical  stackup configuration including layers and manufacturing constraints"""

    pad_to_mask_clearance: float = 0.0
    """Default solder mask expansion"""

    solder_mask_min_width: float | None = None
    """Minimum allowed solder mask width, slivers thinner than this are removed"""

    pad_to_paste_clearance: float | None = None
    """Default difference between pad size and solder paste size for all pads"""

    pad_to_paste_clearance_ratio: float | None = None
    """Default percentage of the pad size used for solder paste for all pads"""

    allow_soldermask_bridges_in_footprints: bool | None = None
    """Whether solder mask bridges between pads in footprints are allowed"""

    tenting: ViaTenting | None = None
    """Boardwide via tenting options"""

    covering: ViaSidedBool | None = None
    """Boardwide via covering options"""

    plugging: ViaSidedBool | None = None
    """Boardwide via plugging options"""

    capping: bool | None = None
    """Boardwide via capping option"""

    filling: bool | None = None
    """Boardwide via filling option"""

    zone_defaults: list[BoardSetupZoneDefault] = F(nested=True)
    """Default zone setup properties for the board."""

    aux_axis_origin: Position | None = None
    """Auxiliary axis origin point if not at default (0, 0)"""

    grid_origin: Position | None = None
    """Grid origin position if other than default (0, 0)"""

    export_settings: PCBExportSettings | None = F(name="pcbplotparams")
    """Board export settings for controlling plot output behavior and configuration."""


class Board(AutoSerdeFile):
    """Represents a `.kicad_pcb` file
    with typed access to all PCB elements including footprints, traces, zones, and graphical items.
    Supports loading, editing, and saving while preserving file integrity and enabling round-trip editing.
    """

    _askiff_key: ClassVar[str] = "kicad_pcb"

    version: int = Version.DEFAULT.pcb
    """Defines the file format version"""

    generator: str = Version.generator
    """Program that generated the file."""

    generator_version: str = Version.generator_ver
    """Version of program that generated the file."""

    general: Sexpr = F()
    """General PCB settings and metadata container."""

    paper: Paper = F()
    """Paper size configuration for the board layout."""

    title_block: TitleBlock = F()
    """Title block containing project metadata like title, date, revision, and comments."""
    layer_map: list[LayerDef] = F(name="layers")
    """Layer definitions mapping base layers to their functions and optional user-defined names."""
    setup: BoardSetup = F()
    """PCB configuration settings including stackup, solder mask, paste, and via options."""
    nets: list[Net] = F(flatten=True, name="net")
    """Nets in the PCB file linking electrical connections between components."""
    footprints: list[FootprintBoard] = F(flatten=True, name="footprint")
    """Footprints instances on PCB"""

    graphic_items: list[GrItemPCB] = F(flatten=True)
    """Graphic objects like lines, circles, and texts on the PCB."""

    tables: list[GrTablePCB] = F(name="table", flatten=True)
    """List of tables and their contents on the PCB."""

    barcodes: list[Barcode] = F(name="barcode", flatten=True)
    """List of barcode graphic elements in the PCB."""

    dimensions: list[Dimension] = F(name="dimension", flatten=True)
    """List of dimensions in the PCB."""

    traces: list[TraceBase] = F(flatten=True)
    """Traces and vias on the PCB."""

    points: list[Point] = F(name="point", flatten=True)
    """List of points (these are empty/non-physical reference points) in the PCB"""

    zones: list[Zone] = F(flatten=True, name="zone")
    """List of zones in the PCB."""

    groups: list[Group] = F(flatten=True, name="group")
    """List of object groups in the board."""

    generated: list[Generated] = F(flatten=True)
    """List of generated objects in the board."""

    embedded_fonts: bool = F()
    """Whether fonts are embedded into this board file."""

    embedded_files: list[EmbeddedFile] = F()
    """Embedded files data including fonts and 3D models."""

    def add_footprint(self, fp: Footprint, reference: str | None = None, position: Position | None = None) -> None:
        """Add a footprint to the board, optionally setting its reference and position.

        Args:
            fp: The footprint to add.
            reference: Optional reference label for the footprint.
            position: Optional position for the footprint on the board.
        """
        # Note: deepcopy is used to regenerate uuid's
        fp_brd = FootprintBoard(
            **{k: deepcopy(v) for k, v in fp.__dict__.items() if k in FootprintBoard.__dataclass_fields__}
        )
        if reference:
            fp_brd.properties.ref.value = reference
        fp_brd.position = position or Position()
        self.footprints.append(fp_brd)
