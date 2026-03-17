from __future__ import annotations

from abc import abstractmethod
from math import cos, radians, sin
from typing import TYPE_CHECKING, Any, ClassVar, Final, Unpack, cast

from askiff.auto_serde import AutoSerde, AutoSerdeDownCasting, AutoSerdeEnum, F, SerdeOpt
from askiff.kistruct.common import (
    BaseArc,
    BaseCircle,
    BaseLine,
    BasePoly,
    Color,
    DataBlockQuoted,
    Effects,
    Position,
    Size,
    Stroke,
    Uuid,
)
from askiff.kistruct.common_pcb import Layer, LayerSet, Net

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore


class GrItem(AutoSerde):
    __askiff_childs: ClassVar[dict[str, type]] = {}
    __askiff_order: ClassVar[list[str]] = [
        "private",
        "start",
        "mid",
        "center",
        "radius",
        "position",
        "end",
        "pts",
        "scale",
        "stroke",
        "locked",
        "fill",
        "layers",
        "solder_mask_margin",
        "net",
        "uuid",
        "data",
    ]
    uuid: Uuid | None = None

    @classmethod
    def __init_subclass__(cls, **kwargs: Unpack[SerdeOpt]) -> None:  # type: ignore
        super().__init_subclass__(**kwargs)
        askiff_key = "_askiff_key"
        if hasattr(cls, askiff_key):
            GrItem.__askiff_childs[getattr(cls, askiff_key)] = cls
        # Note that this is not copy, it is exactly the same memory as for GrItem
        setattr(cls, f"_{cls.__name__}__askiff_childs", GrItem.__askiff_childs)

    # added to forbid direct creation of base classes (child classes should assign value to _askiff_key)
    @property
    @abstractmethod
    def _askiff_key(self) -> str:
        pass


class GrShape(GrItem):
    """GrShape is subclass of graphics that encompasses base shapes like lines, circles, polygons"""

    stroke: Stroke | None = None


####################Base Classes (file)####################
class GrItemFp(GrItem):
    pass


class GrItemPCB(GrItem):
    pass


class GrItemSch(GrItem):
    uuid: Uuid | None = None
    private: bool = F(bare=True, flag=True)


class _GrShapePCBFp(GrShape):
    layers: LayerSet[Layer] = F()
    solder_mask_margin: float | None = None


def _to_glob_coordinate(pos: Position, fp_pos: Position) -> Position:
    angle = radians(-fp_pos.angle if fp_pos.angle is not None else 0)
    sina, cosa = sin(angle), cos(angle)

    return Position(fp_pos.x + pos.x * cosa - pos.y * sina, fp_pos.y + pos.x * sina + pos.y * cosa)


class GrShapeFp(_GrShapePCBFp, GrItemFp):
    @abstractmethod
    def to_shape_pcb(self, fp_position: Position | None = None) -> GrShapePCB: ...


class GrShapePCB(_GrShapePCBFp, GrItemPCB):
    net: Net | None = None
    locked: bool | None = None


###########################Common##########################
class FillStylePCB(str, AutoSerdeEnum):
    NONE = "no"
    HATCH = "hatch"
    HATCH_REVERSE = "reverse_hatch"
    HATCH_CROSS = "cross_hatch"
    SOLID = "yes"


class FillStyleSch(AutoSerdeDownCasting):
    _AutoSerdeDownCasting__downcast_field: ClassVar[str] = "type"
    type: str = F(unquoted=True)


class FillStyleSchColor(FillStyleSch):
    type: Final[str] = F("color", unquoted=True)  # type: ignore
    color: Color = F()


class FillStyleSchBackground(FillStyleSch):
    type: Final[str] = F("background", unquoted=True)  # type: ignore


class FillStyleSchOutline(FillStyleSch):
    type: Final[str] = F("outline", unquoted=True)  # type: ignore


class FillStyleSchNone(FillStyleSch):
    type: Final[str] = F("none", unquoted=True)  # type: ignore


############################Arc############################


class GrArcFp(BaseArc, GrShapeFp):
    _askiff_key: ClassVar[str] = "fp_arc"

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrArcPCB:
        ret = GrArcPCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        fp_position = fp_position or Position()
        ret.start = _to_glob_coordinate(ret.start, fp_position)
        ret.mid = _to_glob_coordinate(ret.mid, fp_position)
        ret.end = _to_glob_coordinate(ret.end, fp_position)
        ret.uuid = Uuid()
        return ret


class GrArcPCB(BaseArc, GrShapePCB):
    _askiff_key: ClassVar[str] = "gr_arc"


A = GrArcFp().to_shape_pcb()


class GrArcSch(GrItemSch, BaseArc, GrShape):
    _askiff_key: ClassVar[str] = "arc"
    fill: FillStyleSch | None = None


############################Line###########################


class GrLine(GrShape, BaseLine):
    pass


class GrLineFp(GrLine, GrShapeFp):
    _askiff_key: ClassVar[str] = "fp_line"

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrLinePCB:
        ret = GrLinePCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        fp_position = fp_position or Position()
        ret.start = _to_glob_coordinate(ret.start, fp_position)
        ret.end = _to_glob_coordinate(ret.end, fp_position)
        ret.uuid = Uuid()
        return ret


class GrLinePCB(GrLine, GrShapePCB):
    _askiff_key: ClassVar[str] = "gr_line"


##########################Polygon##########################
class GrPoly(BasePoly, GrShape):
    pass


class GrPolyFp(GrPoly, GrShapeFp):
    _askiff_key: ClassVar[str] = "fp_poly"
    fill: FillStylePCB | None = None

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrPolyPCB:
        ret = GrPolyPCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        fp_position = fp_position or Position()
        ret.pts = [_to_glob_coordinate(p, fp_position) for p in ret.pts]
        ret.uuid = Uuid()
        return ret


class GrPolyPCB(GrPoly, GrShapePCB):
    _askiff_key: ClassVar[str] = "gr_poly"
    fill: FillStylePCB | None = None


class GrPolySch(GrItemSch, GrPoly):
    _askiff_key: ClassVar[str] = "polyline"
    fill: FillStyleSch | None = None


###########################Bezier##########################
class GrCurveFp(GrPolyFp):
    _askiff_key: ClassVar[str] = "fp_curve"


class GrCurvePCB(GrPolyPCB):
    _askiff_key: ClassVar[str] = "gr_curve"


class GrCurveSch(GrPolySch):
    _askiff_key: ClassVar[str] = "bezier"


###########################Circle##########################


class GrCircleFp(BaseCircle, GrShapeFp):
    _askiff_key: ClassVar[str] = "fp_circle"
    fill: FillStylePCB | None = F(FillStylePCB.NONE)

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrCirclePCB:
        ret = GrCirclePCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        fp_position = fp_position or Position()
        ret.center = _to_glob_coordinate(ret.center, fp_position)
        ret.end = _to_glob_coordinate(ret.end, fp_position)
        ret.uuid = Uuid()
        return ret


class GrCirclePCB(BaseCircle, GrShapePCB):
    _askiff_key: ClassVar[str] = "gr_circle"
    fill: FillStylePCB | None = F(FillStylePCB.NONE)


class GrCircleSch(GrItemSch, GrShape):
    _askiff_key: ClassVar[str] = "circle"
    center: Position = F()
    radius: float = F()
    fill: FillStyleSch | None = F()


#########################Rectangle#########################
class GrRect(GrShape):
    start: Position = F()
    end: Position = F()


class GrRectFp(GrRect, GrShapeFp):
    _askiff_key: ClassVar[str] = "fp_rect"
    fill: FillStylePCB | None = F(FillStylePCB.NONE)

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrLinePCB:
        ret = GrLinePCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        fp_position = fp_position or Position()
        ret.start = _to_glob_coordinate(ret.start, fp_position)
        ret.end = _to_glob_coordinate(ret.end, fp_position)
        ret.uuid = Uuid()
        return ret


class GrRectPCB(GrRect, GrShapePCB):
    _askiff_key: ClassVar[str] = "gr_rect"
    fill: FillStylePCB | None = F(FillStylePCB.NONE)


class GrRectSch(GrItemSch, GrRect):
    _askiff_key: ClassVar[str] = "rectangle"
    fill: FillStyleSch | None = F()


############################Text###########################


class RenderCache(AutoSerde):
    text: str = F(positional=True)
    mode: int = F(positional=True)
    poly: list[BasePoly] = F(name="polygon", flatten=True)


class TextType(str, AutoSerdeEnum):
    USER = "user"


class GrText(GrItem):
    text: str = F(positional=True)
    effects: Effects = F()
    position: Position = F(name="at")


class GrTextPCBBase(GrText):
    __askiff_order: ClassVar[list[str]] = [
        "text",
        "locked",
        "position",
        "layers",
        "uuid",
        "effects",
        "solder_mask_margin",
        "net",
        "render_cache",
    ]
    knockout: bool = F(skip=True)
    layers: LayerSet[Layer] = F()

    def _askiff_post_deser(self) -> None:
        if Layer._KNOCKOUT in self.layers:
            self.layers -= {Layer._KNOCKOUT}
            self.knockout = True

    def _askiff_pre_ser(self) -> GrTextPCBBase:
        if self.knockout:
            self.layers.add(Layer._KNOCKOUT)
        return self


class GrTextFp(GrTextPCBBase, GrItemFp):
    _askiff_key: ClassVar[str] = "fp_text"
    __askiff_order: ClassVar[list[str]] = [
        "type",
        "text",
        "position",
        "locked",
        "layers",
        "uuid",
        "effects",
        "solder_mask_margin",
        "render_cache",
    ]
    type: TextType = F(TextType.USER, positional=True)
    render_cache: RenderCache | None = None
    locked: bool | None = F.unlocked()


class GrTextPCB(GrTextPCBBase, GrItemPCB):
    _askiff_key: ClassVar[str] = "gr_text"
    render_cache: RenderCache | None = None
    locked: bool | None = F()


class GrTextSch(GrText, GrItemSch):
    _askiff_key: ClassVar[str] = "text"
    __askiff_order: ClassVar[list[str]] = [
        "private",
        "text",
        "exclude_from_sim",
        "locked",
        "position",
        "uuid",
        "effects",
    ]
    private: bool = F(bare=True, flag=True)
    exclude_from_sim: bool | None = None
    uuid: Uuid | None = None


##########################TextBox##########################


class TextMargin(AutoSerde, positional=True):  # type:ignore
    left: float = 1.0025
    top: float = 1.0025
    right: float = 1.0025
    bottom: float = 1.0025


class GrTextBox(GrItem):
    __askiff_order: ClassVar[list[str]] = [
        "text",
        "pts",
        "start",
        "end",
        "margins",
        "angle",
        "locked",
        "layer",
        "uuid",
        "effects",
        "border",
        "border_stroke",
        "net",
        "render_cache",
        "knockout",
    ]
    text: str = F(positional=True)
    effects: Effects = F()
    margins: TextMargin | None = None
    border: bool | None = None
    border_stroke: Stroke | None = F(name="stroke")
    # TODO: textbox, size/position can be in 3 flavours in kicad files, but provide unified way to operate on them
    pts: list[Position] = F()
    angle: float | None = None
    start: Position | None = None
    end: Position | None = None
    knockout: bool | None = None


class GrTextBoxFp(GrTextBox, GrItemFp):
    _askiff_key: ClassVar[str] = "fp_text_box"
    render_cache: RenderCache | None = None
    layer: Layer = F(Layer.CU_F)


class GrTextBoxPCB(GrTextBox, GrItemPCB):
    _askiff_key: ClassVar[str] = "gr_text_box"
    render_cache: RenderCache | None = None
    layer: Layer = F(Layer.CU_F)


class GrTextBoxSch(GrItemSch):
    _askiff_key: ClassVar[str] = "text_box"
    __askiff_order: ClassVar[list[str]] = []

    private: bool = F(bare=True, flag=True)
    text: str = F(positional=True)
    exclude_from_sim: bool | None = None
    position: Position = F(name="at")
    size: Size = F()
    margins: TextMargin | None = None
    border: bool | None = None
    border_stroke: Stroke | None = F(name="stroke")
    fill: FillStyleSch | None = None
    effects: Effects = F()
    uuid: Uuid | None = None


###########################Image###########################
class Image(GrItemFp, GrItemPCB, GrItemSch):
    _askiff_key: ClassVar[str] = "image"
    __askiff_order: ClassVar[list[str]] = []
    position: Position = F(name="at")
    scale: float | None = None
    layer: Layer | None = None
    data: DataBlockQuoted = F()
    _uuid = F()


##########################Barcode##########################
class BarcodeType(str, AutoSerdeEnum):
    QR = "qr"
    """QR Code (ISO 18004)"""
    MICRO_QR = "microqr"
    """Micro QR Code"""
    DATA_MATRIX = "datamatrix"
    """Data Matrix (ECC 200)"""
    CODE39 = "code39"
    """Code 39 (ISO 16388)"""
    CODE128 = "code128"
    """Code 128 (ISO 15417)"""


class BarcodeECCLevel(str, AutoSerdeEnum):
    L = "L"
    """~20% error correction"""
    M = "M"
    """~37% error correction"""
    Q = "Q"
    """~55% error correction"""
    H = "H"
    """~65% error correction"""


class Barcode(AutoSerde):
    _askiff_key: ClassVar[str] = "barcode"
    position: Position = F(name="at")
    layer: Layer = F(Layer.CU_F)
    size: Size = F()
    text: str = ""
    text_height: float = 1.5
    type: BarcodeType = F(BarcodeType.QR)
    ecc_level: BarcodeECCLevel = F(BarcodeECCLevel.M)
    """Error correction level (applicable only for qr)"""
    hide: bool = False
    knockout: bool = False
    uuid: Uuid = F()


###########################Table###########################
class TableBorder(AutoSerde):
    external: bool = False
    header: bool = False
    stroke: Stroke | None = None


class TableSeparator(AutoSerde):
    rows: bool = False
    cols: bool = False
    stroke: Stroke | None = None


class TableCell(AutoSerde):
    __askiff_order: ClassVar[list[str]] = [
        "text",
        "exclude_from_sim",
        "start",
        "end",
        "margins",
        "span",
        "layer",
        "uuid",
        "fill",
        "effects",
        "render_cache",
    ]

    text: str = F(positional=True)
    start: Position = F()
    end: Position = F()
    margins: TextMargin = F()
    span: list[int] = F()
    """Indicates expansion of this cell over others (cell merging)
    (span 2 1) means that this cell is merged with cell that is in next column"""
    uuid: Uuid = F()
    effects: Effects | None = None


class TableCellSch(TableCell):
    _askiff_key: ClassVar[str] = "table_cell"
    fill: FillStyleSch | None = None
    exclude_from_sim: bool = F()


class TableCellPCB(TableCell):
    _askiff_key: ClassVar[str] = "table_cell"
    layer: Layer | None = None
    render_cache: RenderCache | None = None


class GrTable(AutoSerde):
    __askiff_order: ClassVar[list[str]] = [
        "column_count",
        "uuid",
        "locked",
        "layer",
        "border",
        "separators",
        "column_widths",
        "row_heights",
        "cells",
    ]
    column_count: int = F()
    uuid: Uuid | None = None
    locked: bool | None = None
    border: TableBorder = F()
    separators: TableSeparator = F()
    column_widths: list[float] = F()
    row_heights: list[float] = F()
    cells: list[TableCell] = F()


class GrTableSch(GrTable):
    cells: list[TableCellSch] = F()  # type: ignore


class GrTablePCB(GrTable):
    layer: Layer = Layer.COMMENTS
    cells: list[TableCellPCB] = F()  # type: ignore


########################Dimensions#########################
class DimensionTextPosition(str, AutoSerdeEnum):
    OUTSIDE = "0"
    """Text outside the dimension line"""
    INLINE = "1"
    """Text in line with the dimension line"""
    MANUAL = "2"
    """Text manually placed by user"""


class DimensionArrowDirection(str, AutoSerdeEnum):
    OUT = "outward"
    IN = "inward"


class DimensionTextFrame(str, AutoSerdeEnum):
    """Style of the frame around the dimension text"""

    NONE = "0"
    RECTANGLE = "1"
    CIRCLE = "2"


class DimensionUnit(str, AutoSerdeEnum):
    INCH = "0"
    MILS = "1"
    MM = "2"
    AUTO = "3"


class DimensionUnitStyle(str, AutoSerdeEnum):
    SKIP = "0"
    """Skip adding units"""
    BARE = "1"
    """Add bare unit string"""
    PARENTHESIS = "2"
    """Wrap unit in parenthesis"""


class DimensionStyle(AutoSerde):
    thickness: float = 0.0
    """Line/arrow thickness"""

    arrow_length: float = 0.0
    """Length of dimension arrows"""

    text_position_mode: DimensionTextPosition = DimensionTextPosition.OUTSIDE  # type: ignore
    """Positioning of dimension text"""

    arrow_direction: DimensionArrowDirection | None = None
    """Direction of dimension arrows"""

    extension_height: float | None = None
    """Length of the extension lines past the dimension crossbar"""

    text_frame: DimensionTextFrame | None = None
    """Style of frame around dimension text. Leader dimensions only"""

    extension_offset: float | None = None
    """Distance between feature point & extension line"""

    keep_text_aligned: bool | None = None
    """If true dimension text will always be left2right or bottom2top"""


class DimensionValueFormat(AutoSerde):
    prefix: str = ""
    """Dimension text prefix"""

    suffix: str = ""
    """Dimension text suffix"""

    units: DimensionUnit = DimensionUnit.AUTO  # type: ignore
    """Units used to display the dimension text"""

    units_format: DimensionUnitStyle = DimensionUnitStyle.BARE  # type: ignore
    """Defines how the unit's suffix is formatted"""

    precision: int = 4
    """Number of significant digits to display"""

    override_value: str | None = None
    """Text to override actual physical dimension"""

    suppress_zeroes: bool | None = None
    """If true removes all trailing zeros from the dimension text"""


class DimensionOrthogonalOrientation(str, AutoSerdeEnum):
    HORIZONTAL = "0"
    VERTICAL = "1"


class Dimension(AutoSerdeDownCasting):
    _AutoSerdeDownCasting__downcast_field: ClassVar[str] = "type"
    __askiff_order: ClassVar[list[str]] = [
        "type",
        "locked",
        "layer",
        "uuid",
        "pts",
        "height",
        "orientation",
        "leader_length",
        "format",
        "style",
        "text",
    ]

    locked: bool | None = None
    layer: Layer = Layer.DRAWINGS
    uuid: Uuid = F()
    pts: list[Position] = F()
    style: DimensionStyle = F()


class DimensionCenter(Dimension):
    """Dimension that is just cross to mark center of sth"""

    type: Final[str] = F("center", unquoted=True)


class DimensionAligned(Dimension):
    type: Final[str] = F("aligned", unquoted=True)
    height: float = 0.0
    format: DimensionValueFormat = F()
    text: GrTextPCBBase = F(name="gr_text")


class DimensionOrthogonal(Dimension):
    type: Final[str] = F("orthogonal", unquoted=True)
    height: float = 0.0
    orientation: DimensionOrthogonalOrientation = F(DimensionOrthogonalOrientation.HORIZONTAL)
    format: DimensionValueFormat = F()
    text: GrTextPCBBase = F(name="gr_text")


class DimensionLeader(Dimension):
    type: Final[str] = F("leader", unquoted=True)
    format: DimensionValueFormat = F()
    text: GrTextPCBBase = F(name="gr_text")


class DimensionRadial(Dimension):
    type: Final[str] = F("radial", unquoted=True)
    leader_length: float = 0.0
    format: DimensionValueFormat = F()
    text: GrTextPCBBase = F(name="gr_text")
