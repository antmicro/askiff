from __future__ import annotations

import logging
from copy import copy, deepcopy
from typing import TYPE_CHECKING, Any, ClassVar, Final, Unpack, cast

from askiff.auto_serde import (
    AutoSerde,
    AutoSerdeAgg,
    AutoSerdeDownCasting,
    AutoSerdeEnum,
    AutoSerdeFile,
    F,
    SerdeOpt,
    SerMode,
)
from askiff.const import Version
from askiff.kistruct.common import BaseArc, BaseLine, BasePoly, EmbeddedFile, Group, Paper, Position, TitleBlock, Uuid
from askiff.kistruct.common_pcb import Layer, LayerCopper, LayerFunction, LayerSet, Net, Point, Zone
from askiff.kistruct.footprint import FootprintBoard
from askiff.kistruct.fp_pad import AfterDrill, DrillPostMatching, PadStackMode, TeardropSettings
from askiff.kistruct.gritems import Barcode, Dimension, GrItemPCB, GrTablePCB
from askiff.sexpr import GeneralizedSexpr, Qstr, Sexpr

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore


log = logging.getLogger()


class StackupLayer(AutoSerdeDownCasting):
    _askiff_key: Final[str] = "layer"
    _AutoSerdeDownCasting__downcast_field: ClassVar[str] = "type"
    layer: str = F("", positional=True)
    type: str = F()


class StackupLayerDielectricSubLayer(AutoSerde):
    color: str | None = None
    thickness: float = 0.12
    locked: bool | None = F(skip=True)
    material: str | None = None
    epsilon_r: float = 4.2
    loss_tangent: float = 0

    def _askiff_pre_ser(self) -> StackupLayerDielectricSubLayer:
        if self.locked:
            ret = copy(self)
            ret._AutoSerde__ser_field = deepcopy(self._AutoSerde__ser_field)  # type: ignore # ty:ignore[unresolved-attribute]
            ret._AutoSerde__ser_field["thickness"] = "thickness", (SerMode.SERIALIZE, None, True)  # type: ignore # ty:ignore[unresolved-attribute]
            ret.thickness = Sexpr((str(self.thickness), "locked"))  # type: ignore # ty:ignore[invalid-assignment]
            return ret
        return self


class StackupLayerDielectric(StackupLayer):
    layer: str = F("dielectric 1", positional=True)
    type: str = ""
    sublayers: list[StackupLayerDielectricSubLayer] = F(lambda: [StackupLayerDielectricSubLayer()])

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
                    assert isinstance(node_val[0], str)
                    ret.type = node_val[0]
                case "color" | "material":
                    setattr(ret.sublayers[-1], node_name, node_val[0])
                case "epsilon_r" | "loss_tangent":
                    assert isinstance(node_val[0], str)
                    setattr(ret.sublayers[-1], node_name, float(node_val[0]))
                case "thickness":
                    assert isinstance(node_val[0], str)
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
    layer: str = F("dielectric 1", positional=True)
    type: Final[str] = "core"  # type: ignore


class StackupLayerDielectricPrepreg(StackupLayerDielectric):
    layer: str = F("dielectric 1", positional=True)
    type: Final[str] = "prepreg"  # type: ignore


class StackupLayerCopper(StackupLayer):
    layer: LayerCopper = F(Layer.CU_F, positional=True)
    type: Final[str] = "copper"  # type: ignore
    thickness: float = 0.035


class StackupLayerMask(StackupLayer):
    type: str = ""
    color: str | None = None
    thickness: float = 0.01
    material: str | None = None
    epsilon_r: float | None = None
    loss_tangent: float | None = None


class StackupLayerMaskTop(StackupLayerMask):
    layer: Final[Layer] = F(Layer.MASK_F, positional=True, after="__begin__")  # type: ignore
    type: Final[str] = F("Top Solder Mask")  # type: ignore


class StackupLayerMaskBottom(StackupLayerMask):
    layer: Final[Layer] = F(Layer.MASK_B, positional=True, after="__begin__")  # type: ignore
    type: Final[str] = "Bottom Solder Mask"  # type: ignore


class StackupLayerPasteTop(StackupLayer):
    layer: Final[Layer] = F(Layer.PASTE_F, positional=True, after="__begin__")  # type: ignore
    type: Final[str] = "Top Solder Paste"  # type: ignore


class StackupLayerPasteBottom(StackupLayer):
    layer: Final[Layer] = F(Layer.PASTE_B, positional=True, after="__begin__")  # type: ignore
    type: Final[str] = "Bottom Solder Paste"  # type: ignore


class StackupLayerSilks(StackupLayer):
    type: str = ""
    color: str | None = None
    material: str | None = None


class StackupLayerSilksTop(StackupLayerSilks):
    layer: Final[Layer] = F(Layer.SILKS_F, positional=True, after="__begin__")  # type: ignore
    type: Final[str] = "Top Silk Screen"  # type: ignore


class StackupLayerSilksBottom(StackupLayerSilks):
    layer: Final[Layer] = F(Layer.SILKS_B, positional=True, after="__begin__")  # type: ignore
    type: Final[str] = "Bottom Silk Screen"  # type: ignore


class StackupEdgeConn(str, AutoSerdeEnum):
    BEVELLED = "bevelled"
    SIMPLE = "yes"
    NONE = ""


class StackupCopperFinish(Qstr, AutoSerdeEnum):
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
    layers: list[StackupLayer] = F(flatten=True, name="layer")
    copper_finish: StackupCopperFinish = F(StackupCopperFinish.ENIG)
    dielectric_constraints: bool | None = None
    edge_connector: StackupEdgeConn = F(StackupEdgeConn.NONE)
    castellated_pads: bool | None = None
    edge_plating: bool | None = None


class LayerDef(AutoSerde, positional=True):  # type: ignore
    layer: Layer = F()
    function: LayerFunction = F()
    user_name: str | None = None

    def __init__(
        self, layer: Layer = Layer.CU_F, function: LayerFunction | None = None, user_name: str | None = None
    ) -> None:
        self.std_name = layer
        self.function = layer.validate_function(function)
        self.user_name = user_name

    def _askiff_key(self) -> str:
        return str(self.layer.order_id())


class TraceBase(AutoSerde):
    __askiff_childs: ClassVar[dict[str, type]] = {}
    locked: bool | None = None
    layers: LayerSet[Layer] = F()
    solder_mask_margin: float | None = None
    net: Net = F()
    uuid: Uuid = F()

    @classmethod
    def __init_subclass__(cls, **kwargs: Unpack[SerdeOpt]) -> None:  # type: ignore
        super().__init_subclass__(**kwargs)
        askiff_key = "_askiff_key"
        if hasattr(cls, askiff_key):
            TraceBase.__askiff_childs[getattr(cls, askiff_key)] = cls
        # Note that this is not copy, it is exactly the same memory as for GrItem
        setattr(cls, f"_{cls.__name__}__askiff_childs", TraceBase.__askiff_childs)


class TraceSegment(TraceBase, BaseLine):
    _askiff_key: ClassVar[str] = "segment"
    width: float = F(0.2, after="end")


class TraceArc(TraceBase, BaseArc):
    _askiff_key: ClassVar[str] = "arc"
    width: float = F(0.2, after="end")


class ViaType(str, AutoSerdeEnum):
    THRU = ""
    BLIND = "blind"
    MICRO = "micro"


class ViaSidedBool(AutoSerde):
    front: bool = False
    back: bool = False


class ViaTenting(AutoSerde):
    front: bool = F(false_val="none").version(Version.K9.pcb, bare=True, flag=True)
    back: bool = F(false_val="none").version(Version.K9.pcb, bare=True, flag=True)

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
    _askiff_key: ClassVar[str] = "layer"
    layer: Layer = F(Layer.CU_B, positional=True)
    size: float = 0.45


class ViaPadStack(AutoSerde):
    mode: PadStackMode = F(PadStackMode.FRONT_INNER_BACK)
    layers: list[ViaPadStackLayer] = F(flatten=True, name="layer")


class Via(TraceBase):
    _askiff_key: ClassVar[str] = "via"
    type: ViaType = F(ViaType.THRU, positional=True)
    position: Position = F(name="at", after="__begin__")
    size: float = 0.45
    drill: float = 0.1
    backdrill: AfterDrill | None = None
    tertiary_drill: AfterDrill | None = None
    front_post_machining: DrillPostMatching | None = None
    back_post_machining: DrillPostMatching | None = None
    _layers = F()
    _locked = F()
    remove_unused_layers: bool | None = None
    keep_end_layers: bool | None = None
    free: bool | None = None
    zone_layer_connections: LayerSet[Layer] | None = F(name="zone_layer_connections", keep_empty=True)
    tenting: ViaTenting | None = None
    capping: bool | None = None
    covering: ViaSidedBool | None = None
    plugging: ViaSidedBool | None = None
    filling: bool | None = None
    padstack: ViaPadStack | None = None
    teardrops: TeardropSettings | None = None


class Generated(AutoSerdeDownCasting):
    _AutoSerdeDownCasting__downcast_field: ClassVar[str] = "type"
    uuid: Uuid = F()
    type: str = F(unquoted=True)


class GeneratedTuningInitialSide(Qstr, AutoSerdeEnum):
    RIGHT = "right"
    LEFT = "left"


class GeneratedTuningStatus(Qstr, AutoSerdeEnum):
    TOO_LONG = "too_long"
    TOO_SHORT = "too_short"
    TUNED = "tuned"


class GeneratedTuningMode(Qstr, AutoSerdeEnum):
    BETWEEN_PAIRS = "diff_pair"
    INSIDE_PAIR = "diff_pair_skew"
    SINGLE_TRACE = "single"


class GeneratedTuningPattern(Generated, Group):
    _uuid = F()
    type: Final[str] = F("tuning_pattern", unquoted=True)  # type: ignore

    name: str = "Tuning Pattern"

    layer: LayerCopper = F(Layer.CU_F)
    """Layer the track resides on"""

    _locked = F()

    base_line: BasePoly | None = None
    """Polygon that shows, how trace (_P in diff pair) will looks prior to tuning"""

    base_line_coupled: BasePoly | None = None
    """Polygon that shows, how coupled trace (_N in diff pair) will looks prior to tuning"""

    corner_radius_percent: int = 0
    """The ``cornerRadius`` token defines the radius of the corner"""

    end: Position = F(nested=True)
    """Ending point of tuning region"""

    initial_side: GeneratedTuningInitialSide = F(GeneratedTuningInitialSide.LEFT)
    """Indicates on which track side is first meander"""

    is_time_domain: bool | None = None
    """Is tunig is resolved in time domain (opposing to length domain)"""

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
    """Length of the tuned track (as of last tuning refresh)"""

    max_amplitude: float = 0
    """Maximal amplitude of meander"""

    min_amplitude: float = 0
    """Minimal amplitude of meander"""

    min_spacing: float = 0
    """Minimal spacing between meanders"""

    origin: Position = F(nested=True)
    """Starting point of tuning region"""

    override_custom_rules: bool = False

    rounded: bool = False
    """Defines if the meander is rounded/fillet based (opposed to chamfer based)"""

    single_sided: bool = False
    """Indicates that meanders should be on one side of track only"""

    target_delay: float | None = None

    target_delay_max: float | None = None

    target_delay_min: float | None = None

    target_length: float = 0

    target_length_max: float = 0

    target_length_min: float = 0

    target_skew: float = 0

    target_skew_max: float = 0

    target_skew_min: float = 0

    tuning_mode: GeneratedTuningMode = F(GeneratedTuningMode.SINGLE_TRACE)
    """Mode of tunig pattern"""

    _members = F()
    """Uuids of trace primitives that were generated by this object"""


class PCBExportSettingsPlotMode(str, AutoSerdeEnum):
    STANDARD = "1"
    OUTLINE = "2"


class PCBExportSettingsOutputFormat(str, AutoSerdeEnum):
    GERBER = "0"
    POST_SCRIPT = "1"
    SVG = "2"
    DXF = "3"
    HPGL = "4"
    PDF = "5"


class PCBExportSettings(AutoSerde, name_case="lower"):  # type: ignore
    layer_selection: str = F(unquoted=True)
    """Hexadecimal bit flags of layers that shall be plotted"""

    plot_on_all_layers_selection: str | None = F("0x00000000_00000000_00000000_00000000", unquoted=True, name_case=None)
    """Hexadecimal bit flags of layers that shall be plotted on each plot"""

    disable_apert_macros: bool = False
    """Use aperture macros in gerber plots"""

    use_gerber_extensions: bool = False
    """Use Protel file name extensions for gerber plots"""

    use_gerber_attributes: bool = False
    """Use X2 extensions in gerber plots"""

    use_gerber_advanced_attributes: bool = False
    """Include netlist information in gerber plots"""

    create_gerber_job_file: bool = False
    """Whether to create job file when plotting gerber files"""

    dashed_line_dash_ratio: float = F(12, name_case=None).version(Version.K9.pcb, keep_trailing=True)
    """Dash size of dashed line (value of one is 0.05 mm)"""

    dashed_line_gap_ratio: float = F(3, name_case=None).version(Version.K9.pcb, keep_trailing=True)
    """Gap size of dashed line (value of one is 0.05 mm)"""

    svg_precision: float = 0.0
    """Precision used for plotting SVG"""

    plot_frame_ref: bool = False
    """Whether the border and title block should be plotted"""

    mode: PCBExportSettingsPlotMode = F(PCBExportSettingsPlotMode.STANDARD)
    """Plot mode"""

    use_aux_origin: bool = False
    """Determines if all coordinates are defined in relation to auxiliary origin"""

    hpgl_pen_number: int | None = None
    """Integer pen number used for HPGL plots"""

    hpgl_pen_speed: int | None = None
    """Integer pen speed used for HPGL plots"""

    hpgl_pen_diameter: float | None = F().version(Version.K9.pcb, keep_trailing=True)
    """Floating point pen size for HPGL plots"""

    pdf_front_fp_property_popups: bool = F(False, name_case=None)
    """Add interactive popups to generated PDF with part information for each footprint on front side"""

    pdf_back_fp_property_popups: bool = F(False, name_case=None)
    """Add interactive popups to generated PDF with part information for each footprint on back side"""

    pdf_metadata: bool = F(False, name_case=None)

    pdf_single_document: bool = F(False, name_case=None)

    dxf_polygon_mode: bool = False
    """Wheather to use polygon mode for DXF plots"""

    dxf_imperial_units: bool = False
    """Wheather to use imperial units for DXF plots"""

    dxf_use_pcbnew_font: bool = False
    """Wheather to use pcbnew(vector) font (opposed to default one) for DXF plots"""

    ps_negative: bool = False
    """Set for negative PostScript plots"""

    ps_a4_output: bool = False
    """Set for A4 sized PostScript plots"""

    plot_black_and_white: bool = F(False, name_case=None)
    """Ignore layer colors, plot in black & white"""

    plot_reference: bool | None = None
    """Whether to plot hidden reference field"""

    plot_value: bool | None = None
    """Whether to plot hidden value field"""

    plot_invisible_text: bool | None = None
    """Whether to plot other hidden text (not value, not reference)"""

    sketch_pads_on_fab: bool = False
    """Whether to plot pads in outline (sketch) mode"""

    plot_pad_numbers: bool = False

    hide_dnp_on_fab: bool = False
    """Whether to remove DNP components on *.Fab layer plot"""

    sketch_dnp_on_fab: bool = True
    """Whether to plot DNP components in outline mode on *.Fab layer plot"""

    cross_out_dnp_on_fab: bool = True
    """Whether to cross out DNP components on *.Fab layer plot"""

    subtract_mask_from_silk: bool = False
    """Whether to substract solder mask from silk screen layers in gerber plots"""

    output_format: PCBExportSettingsOutputFormat = F(PCBExportSettingsOutputFormat.GERBER)
    """Last used plot type/format"""

    mirror: bool = False
    """Whether to mirror the plot"""

    drill_shape: int = 0
    """Shape used to mark drills"""

    scale_selection: int = 1

    output_directory: str = ""
    """Relative path (to project path) where to save plot files"""

    plot_fp_text: bool | None = None
    """Whether to print footprint text in output"""


class BoardSetupZoneDefault(AutoSerde):
    _askiff_key: ClassVar[str] = "property"
    layer: LayerCopper = F(Layer.CU_F)
    hatch_position: Position = F(nested=True)


class BoardSetup(AutoSerde):
    stackup: Stackup = F()
    """Definition of physial PCB stackup"""

    pad_to_mask_clearance: float = 0.0
    """Default solder mask expansion"""

    solder_mask_min_width: float | None = None
    """Mminimum allowed solder mask width (slivers thinner than this will be removed)"""

    pad_to_paste_clearance: float | None = None
    """Default difference between pad size and solder paste size for all pads"""

    pad_to_paste_clearance_ratio: float | None = None
    """Default percentage of the pad size used for solder paste for all pads"""

    allow_soldermask_bridges_in_footprints: bool | None = None
    """Allow footprints to have pads bridged with soldermask"""

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

    aux_axis_origin: Position | None = None
    """Auxiliary origin if other than (0,0)."""

    grid_origin: Position | None = None
    """Grid origin if other than (0,0)"""

    export_settings: PCBExportSettings | None = F(name="pcbplotparams")
    """Defines board exports settings"""


class Board(AutoSerdeFile):
    _askiff_key: ClassVar[str] = "kicad_pcb"

    version: int = Version.DEFAULT.pcb
    """Defines the file format version"""

    generator: str = Version.generator
    """Defines the program used to write the file"""

    generator_version: str = Version.generator_ver
    """Defines the program version used to write the file"""

    general: Sexpr = F()

    paper: Paper = F()

    title_block: TitleBlock = F()
    layer_map: list[LayerDef] = F(name="layers")
    setup: BoardSetup = F()
    nets: list[Net] = F(flatten=True, name="net")
    footprints: list[FootprintBoard] = F(flatten=True, name="footprint")

    graphic_items: AutoSerdeAgg[GrItemPCB] = F(flatten=True)
    """List of graphical objects (lines, circles, arcs, texts, ...) in the footprint"""

    tables: list[GrTablePCB] = F(name="table", flatten=True)
    """Defines list of tables and their contents"""

    barcodes: list[Barcode] = F(name="barcode", flatten=True)
    """List of barcodes in the footprint"""

    dimensions: list[Dimension] = F(name="dimension", flatten=True)
    """List of dimensions in the footprint"""

    traces: AutoSerdeAgg[TraceBase] = F(flatten=True)
    """Traces and vias"""

    points: list[Point] = F(name="point", flatten=True)
    """List of points (these are empty/non-physical reference points) in the footprint"""

    zones: list[Zone] = F(flatten=True, name="zone")
    """List of keep out zones in the footprint"""

    groups: list[Group] = F(flatten=True, name="group")
    """List of object groups in the footprint"""

    generated: list[Generated] = F(flatten=True)
    """List of generated objects (eg. tuning patterns) in the footprint"""

    embedded_fonts: bool = F()
    """Indicates whether there are fonts embedded into this component"""

    embedded_files: list[EmbeddedFile] = F()
    """Stores data of embedded files, eg. fonts, 3d-models"""
