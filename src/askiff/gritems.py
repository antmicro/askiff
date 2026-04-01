from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence
from math import cos, sin
from typing import TYPE_CHECKING, Any, ClassVar, Final, Self, Unpack, cast

from askiff._auto_serde import AutoSerde, AutoSerdeDownCasting, AutoSerdeEnum, AutoSerdeFile, F, SerdeOpt
from askiff.common import (
    BaseArc,
    BaseBezier,
    BaseCircle,
    BaseLine,
    BasePoly,
    BaseRect,
    BaseShape,
    Color,
    DataBlock,
    Effects,
    Position,
    Size,
    Stroke,
    Uuid,
)
from askiff.common_pcb import BaseLayer, Layer, LayerCopperOuter, LayerSet, Net, _NetK9Simple
from askiff.const import Version

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore


class GrItem(AutoSerde):
    __askiff_childs: ClassVar[dict[str, type]]
    __askiff_order: ClassVar[list[str]] = [
        "private",
        "start",
        "mid",
        "center",
        "radius",
        "position",
        "end",
        "pts",
        "_pts",
        "scale",
        "stroke",
        "locked",
        "fill",
        "_layers",
        "solder_mask_margin",
        "net",
        "uuid",
        "data",
    ]

    @classmethod
    def __init_subclass__(cls, **kwargs: Unpack[SerdeOpt]) -> None:  # type: ignore
        super().__init_subclass__(**kwargs)
        base = (getattr(parent, f"_{parent.__name__}__askiff_childs", None) for parent in cls.__mro__[1:])
        base_filtr = [b for b in base if b is not None]
        if not base_filtr:
            setattr(cls, f"_{cls.__name__}__askiff_childs", {})
            return
        for base_askiff_childs in base_filtr:
            askiff_key = getattr(cls, "_askiff_key", None)
            if askiff_key:
                base_askiff_childs[askiff_key] = cls

    # added to forbid direct creation of base classes (child classes should assign value to _askiff_key)
    @property
    @abstractmethod
    def _askiff_key(self) -> str:
        pass


class GrShape(BaseShape):
    """GrShape is subclass of graphics that encompasses base shapes like lines, circles, polygons"""

    stroke: Stroke | None = None


####################Base Classes (file)####################
class GrItemFp(GrItem):
    uuid: Uuid = F()


class GrItemPCB(GrItem):
    uuid: Uuid = F()


class GrItemSch(GrItem):
    uuid: Uuid = F()


class GrItemSym(GrItem):
    private: bool = F(bare=True, flag=True)


class _GrShapePCBFp(GrShape):
    _layers: LayerSet[BaseLayer] = F()
    solder_mask_margin: float | None = None
    layer: BaseLayer = F(Layer.CU_F, skip=True)

    def _askiff_post_deser(self) -> None:
        self.layer = next((x for x in self._layers if isinstance(x, LayerCopperOuter)), next(x for x in self._layers))

    def _askiff_pre_ser(self) -> Self:
        self._layers = LayerSet(self.layer)
        if self.solder_mask_margin:
            if self.layer not in (Layer.CU_B, Layer.CU_F):
                self.solder_mask_margin = None
            else:
                self._layers.add(Layer.MASK_F if self.layer == Layer.CU_F else Layer.MASK_B)
        return self


class GrShapeFp(_GrShapePCBFp, GrItemFp):
    @abstractmethod
    def to_shape_pcb(self, fp_position: Position | None = None) -> GrShapePCB: ...


class GrShapePCB(_GrShapePCBFp, GrItemPCB):
    net: Net | None = F(serialize=_NetK9Simple._ser, deserialize=_NetK9Simple.deserialize)
    locked: bool | None = None


class GrShapeSch(GrShape, GrItemSch):
    pass


class GrShapeSym(GrShape, GrItemSym):
    pass


###########################Common##########################
class FillStylePCBEnum(str, AutoSerdeEnum):
    NONE = "no"
    HATCH = "hatch"
    HATCH_REVERSE = "reverse_hatch"
    HATCH_CROSS = "cross_hatch"
    SOLID = "yes"


class FillStyleSchEnum(str, AutoSerdeEnum):
    NONE = "none"
    HATCH = "hatch"
    HATCH_REVERSE = "reverse_hatch"
    HATCH_CROSS = "cross_hatch"
    SOLID = "color"


class FillStyleSch(AutoSerde):
    type: FillStyleSchEnum = F(FillStyleSchEnum.NONE)
    color: Color | None = F()


class FillStyleSym(AutoSerdeDownCasting):
    _AutoSerdeDownCasting__downcast_field: ClassVar[str] = "type"
    type: Final[str] = F(unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]


class FillStyleSymColor(FillStyleSym):
    type: Final[str] = F("color", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    color: Color = F()


class FillStyleSymBackground(FillStyleSym):
    type: Final[str] = F("background", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]


class FillStyleSymOutline(FillStyleSym):
    type: Final[str] = F("outline", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]


class FillStyleSymNone(FillStyleSym):
    type: Final[str] = F("none", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]


############################Arc############################


class GrArcFp(BaseArc, GrShapeFp):
    _askiff_key: ClassVar[str] = "fp_arc"

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrArcPCB:
        ret = GrArcPCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        ret.to_global(fp_position or Position())
        ret.uuid = Uuid()
        return ret


class GrArcPCB(BaseArc, GrShapePCB):
    _askiff_key: ClassVar[str] = "gr_arc"


class GrArcSch(BaseArc, GrShapeSch):
    _askiff_key: ClassVar[str] = "arc"
    fill: FillStyleSch | None = None
    uuid: Uuid = F().version(Version.K9.sch, unquoted=True)


class GrArcSym(BaseArc, GrShapeSym):
    _askiff_key: ClassVar[str] = "arc"
    fill: FillStyleSym | None = None


############################Line###########################


class GrLineFp(BaseLine, GrShapeFp):
    _askiff_key: ClassVar[str] = "fp_line"

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrLinePCB:
        ret = GrLinePCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        ret.to_global(fp_position or Position())
        ret.uuid = Uuid()
        return ret


class GrLinePCB(BaseLine, GrShapePCB):
    _askiff_key: ClassVar[str] = "gr_line"


##########################Polygon##########################


class GrPolyFp(BasePoly, GrShapeFp):
    _askiff_key: ClassVar[str] = "fp_poly"
    fill: FillStylePCBEnum | None = None

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrPolyPCB:
        ret = GrPolyPCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        ret.to_global(fp_position or Position())
        ret.uuid = Uuid()
        return ret


class GrPolyPCB(BasePoly, GrShapePCB):
    _askiff_key: ClassVar[str] = "gr_poly"
    fill: FillStylePCBEnum | None = None


class GrPolySch(BasePoly, GrShapeSch):
    _askiff_key: ClassVar[str] = "polyline"
    fill: FillStyleSch | None = None

    def _askiff_pre_ser(self) -> GrPolySch:
        if AutoSerdeFile._version <= Version.K9.sch and self.fill:
            self._AutoSerde__ser_field = _GrPolySchUnquoteUuid._AutoSerde__ser_field  # type: ignore  # ty:ignore[unresolved-attribute]
        else:
            self._AutoSerde__ser_field = GrPolySch._AutoSerde__ser_field  # type: ignore  # ty:ignore[unresolved-attribute]
        return self


class _GrPolySchUnquoteUuid(GrPolySch):
    uuid: Uuid = F().version(Version.K9.sch, unquoted=True)


class GrPolySym(BasePoly, GrShapeSym):
    _askiff_key: ClassVar[str] = "polyline"
    fill: FillStyleSym | None = None


###########################Bezier##########################


class GrCurveFp(BaseBezier, GrShapeFp):
    _askiff_key: ClassVar[str] = "fp_curve"
    fill: FillStylePCBEnum | None = None

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrCurvePCB:
        ret = GrCurvePCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        ret.to_global(fp_position or Position())
        ret.uuid = Uuid()
        return ret

    def _askiff_post_deser(self) -> None:
        _GrShapePCBFp._askiff_post_deser(self)
        BaseBezier._askiff_post_deser(self)

    def _askiff_pre_ser(self) -> Self:
        return _GrShapePCBFp._askiff_pre_ser(BaseBezier._askiff_pre_ser(self))  # type: ignore # ty:ignore[invalid-argument-type]


class GrCurvePCB(BaseBezier, GrShapePCB):
    _askiff_key: ClassVar[str] = "gr_curve"
    fill: FillStylePCBEnum | None = None

    def _askiff_post_deser(self) -> None:
        _GrShapePCBFp._askiff_post_deser(self)
        BaseBezier._askiff_post_deser(self)

    def _askiff_pre_ser(self) -> Self:
        return _GrShapePCBFp._askiff_pre_ser(BaseBezier._askiff_pre_ser(self))  # type: ignore # ty:ignore[invalid-argument-type]


class GrCurveSch(BaseBezier, GrShapeSch):
    _askiff_key: ClassVar[str] = "bezier"
    fill: FillStyleSch | None = None
    uuid: Uuid = F().version(Version.K9.sch, unquoted=True)


class GrCurveSym(BaseBezier, GrShapeSym):
    _askiff_key: ClassVar[str] = "bezier"
    fill: FillStyleSym | None = None


###########################Circle##########################


class GrCircleFp(BaseCircle, GrShapeFp):
    _askiff_key: ClassVar[str] = "fp_circle"
    fill: FillStylePCBEnum | None = F(FillStylePCBEnum.NONE)

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrCirclePCB:
        ret = GrCirclePCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        ret.to_global(fp_position or Position())
        ret.uuid = Uuid()
        return ret


class GrCirclePCB(BaseCircle, GrShapePCB):
    _askiff_key: ClassVar[str] = "gr_circle"
    fill: FillStylePCBEnum | None = F(FillStylePCBEnum.NONE)


class GrCircleSch(GrShapeSch):
    _askiff_key: ClassVar[str] = "circle"
    center: Position = F()
    radius: float = F()
    fill: FillStyleSch | None = F()

    def extrema_points(self) -> Sequence[Position]:
        return BaseCircle(self.center, Position(self.center.x + self.radius, self.center.y)).extrema_points()

    def to_global(self, ref_pos: Position) -> None:
        self.center = self.center.to_global(ref_pos)


class GrCircleSym(GrShapeSym):
    _askiff_key: ClassVar[str] = "circle"
    center: Position = F()
    radius: float = F()
    fill: FillStyleSym | None = F()

    def extrema_points(self) -> Sequence[Position]:
        return BaseCircle(self.center, Position(self.center.x + self.radius, self.center.y)).extrema_points()

    def to_global(self, ref_pos: Position) -> None:
        self.center = self.center.to_global(ref_pos)


#########################Rectangle#########################


class GrRectFp(BaseRect, GrShapeFp):
    _askiff_key: ClassVar[str] = "fp_rect"
    fill: FillStylePCBEnum | None = F(FillStylePCBEnum.NONE)

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrLinePCB:
        ret = GrLinePCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        ret.to_global(fp_position or Position())
        ret.uuid = Uuid()
        return ret


class GrRectPCB(BaseRect, GrShapePCB):
    _askiff_key: ClassVar[str] = "gr_rect"
    fill: FillStylePCBEnum | None = F(FillStylePCBEnum.NONE)


class GrRectSch(BaseRect, GrShapeSch):
    _askiff_key: ClassVar[str] = "rectangle"
    fill: FillStyleSch | None = F()
    uuid: Uuid = F().version(Version.K9.sch, unquoted=True)


class GrRectSym(BaseRect, GrShapeSym):
    _askiff_key: ClassVar[str] = "rectangle"
    fill: FillStyleSym | None = F()


############################Text###########################


class RenderCache(AutoSerde):
    text: str = F(positional=True)
    mode: int = F(positional=True)
    poly: list[BasePoly] = F(name="polygon", flatten=True)


class TextType(str, AutoSerdeEnum):
    USER = "user"


class GrText(AutoSerde):
    text: str = F(positional=True)
    effects: Effects = F()
    position: Position = F(name="at")


class GrTextPCBBase(GrText):
    __askiff_order: ClassVar[list[str]] = [
        "text",
        "locked",
        "position",
        "_layers",
        "uuid",
        "effects",
        "net",
        "render_cache",
    ]
    knockout: bool = F(skip=True)
    _layers: LayerSet[BaseLayer] = F()
    uuid: Uuid = F()
    layer: BaseLayer = F(Layer.COMMENTS, skip=True)

    def _askiff_post_deser(self) -> None:
        self.layer = next(x for x in self._layers)
        self.knockout = self._layers._knockout

    def _askiff_pre_ser(self) -> GrTextPCBBase:
        self._layers = LayerSet(self.layer)
        self._layers._knockout = self.knockout
        return self


class GrTextFp(GrTextPCBBase, GrItemFp):
    _askiff_key: ClassVar[str] = "fp_text"
    __askiff_order: ClassVar[list[str]] = [
        "type",
        "text",
        "position",
        "locked",
        "_layers",
        "uuid",
        "effects",
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
    __askiff_order: ClassVar[list[str]] = ["text", "exclude_from_sim", "locked", "position", "effects", "uuid"]
    exclude_from_sim: bool | None = None


class GrTextSym(GrText, GrItemSym):
    _askiff_key: ClassVar[str] = "text"
    __askiff_order: ClassVar[list[str]] = ["private", "text", "exclude_from_sim", "locked", "position", "effects"]
    private: bool = F(bare=True, flag=True)
    exclude_from_sim: bool | None = None


##########################TextBox##########################
class TextMargin(AutoSerde, positional=True):  # type:ignore
    left: float = 1.0025
    top: float = 1.0025
    right: float = 1.0025
    bottom: float = 1.0025


class RectTextBox(AutoSerde):
    margins: TextMargin | None = None


class RectTextBoxPCB(RectTextBox):
    _pts: list[Position] | None = F()
    _start: Position | None = F()
    _end: Position | None = F()
    margins: TextMargin | None = None
    _angle: float | None = F()

    def __set_from_pos_size(self, pos: Position, size: Size) -> None:
        if pos.angle:
            dx, dy = size.width / 2, size.height / 2
            local = [(-dx, -dy), (dx, -dy), (dx, dy), (-dx, dy)]
            cos_t, sin_t = cos(pos.angle), sin(pos.angle)

            self._pts = [Position(pos.x + lx * cos_t - ly * sin_t, pos.y + lx * sin_t + ly * cos_t) for lx, ly in local]
            self._angle = pos.angle
            self._end = None
            self._start = None
        else:
            self._pts = None
            self._angle = None
            self._end = Position(pos.x - size.width / 2, pos.y - size.height / 2)
            self._start = Position(pos.x + size.width / 2, pos.y + size.height / 2)

    @property
    def position(self) -> Position:
        if self._start is not None and self._end is not None:
            return Position((self._start.x + self._end.x) / 2, (self._start.y + self._end.y) / 2)
        if self._pts and self._angle is not None:
            x, y = 0.0, 0.0
            for p in self._pts:
                x += p.x
                y += p.y
            return Position(x / 4, y / 4, self._angle)
        return Position()

    @position.setter
    def position(self, val: Position) -> None:
        self.__set_from_pos_size(val, self.size)

    @property
    def size(self) -> Size:
        if self._start is not None and self._end is not None:
            return Size(abs(self._start.x - self._end.x), abs(self._start.y - self._end.y))
        if self._pts and self._angle is not None:
            return Size(
                self._pts[0].distance(self._pts[1]),
                self._pts[1].distance(self._pts[2]),
            )
        return Size()

    @size.setter
    def size(self, val: Size) -> None:
        self.__set_from_pos_size(self.position, val)


class RectTextBoxSch(RectTextBox):
    position: Position = F(name="at")
    size: Size = F()
    margins: TextMargin | None = None


class GrTextBox(AutoSerde):
    __askiff_order: ClassVar[list[str]] = []
    text: str = F(positional=True)
    border: bool | None = None
    border_stroke: Stroke | None = F(name="stroke")
    effects: Effects = F()
    box: RectTextBox = F(inline=True)


class _GrTextBoxFpPCB(GrTextBox):
    box: RectTextBoxPCB = F(inline=True, after="text")
    layer: BaseLayer = F(Layer.COMMENTS)
    uuid: Uuid = F()
    effects: Effects = F()
    render_cache: RenderCache | None = F(after="border_stroke")
    knockout: bool | None = None


class GrTextBoxFp(_GrTextBoxFpPCB, GrItemFp):
    _askiff_key: ClassVar[str] = "fp_text_box"


class GrTextBoxPCB(_GrTextBoxFpPCB, GrItemPCB):
    _askiff_key: ClassVar[str] = "gr_text_box"


class GrTextBoxSch(GrTextBox, GrItemSch):
    _askiff_key: ClassVar[str] = "text_box"
    exclude_from_sim: bool | None = F(after="text")
    box: RectTextBoxSch = F(inline=True)
    fill: FillStyleSch | None = F(after="border_stroke")
    uuid: Uuid = F(after="locked").version(Version.K9.sch, after="effects")


class GrTextBoxSym(GrTextBox, GrItemSym):
    _askiff_key: ClassVar[str] = "text_box"
    exclude_from_sim: bool | None = F(after="text")
    box: RectTextBoxSch = F(inline=True)
    fill: FillStyleSym | None = F(after="border_stroke")


###########################Image###########################
class ImagePCB(GrItemFp, GrItemPCB):
    _askiff_key: ClassVar[str] = "image"
    __askiff_order: ClassVar[list[str]] = []
    position: Position = F(name="at")
    scale: float | None = None
    layer: BaseLayer | None = None
    data: DataBlock = F(serialize=DataBlock.serialize_quoted, deserialize=DataBlock.deserialize_quoted)
    _uuid = F()


class ImageSch(GrItemSch):
    _askiff_key: ClassVar[str] = "image"
    __askiff_order: ClassVar[list[str]] = []
    position: Position = F(name="at")
    scale: float | None = None
    _uuid = F()
    data: DataBlock = F(serialize=DataBlock.serialize_quoted, deserialize=DataBlock.deserialize_quoted)


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
    layer: BaseLayer = F(Layer.SILKS_F)
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
    text: str = F(positional=True)
    box: RectTextBox = F(inline=True)
    span: list[int] = F()
    """Indicates expansion of this cell over others (cell merging)
    (span 2 1) means that this cell is merged with cell that is in next column"""
    uuid: Uuid = F()
    effects: Effects | None = None


class TableCellSch(TableCell):
    _askiff_key: ClassVar[str] = "table_cell"
    __askiff_order: ClassVar[list[str]] = [
        "text",
        "exclude_from_sim",
        "box.position",
        "box.size",
        "box.margins",
        "span",
        "fill",
        "effects",
        "uuid",
    ]
    box: RectTextBoxSch = F(inline=True)
    fill: FillStyleSym | None = None
    exclude_from_sim: bool = F()


class TableCellPCB(TableCell):
    _askiff_key: ClassVar[str] = "table_cell"
    __askiff_order: ClassVar[list[str]] = [
        "text",
        "box._start",
        "box._end",
        "box._pts",
        "box.margins",
        "box._angle",
        "span",
        "layer",
        "uuid",
        "fill",
        "effects",
        "render_cache",
    ]
    box: RectTextBoxPCB = F(inline=True)
    layer: BaseLayer | None = None
    render_cache: RenderCache | None = None


class GrTable(AutoSerde):
    column_count: int = F()
    uuid: Uuid | None = None
    locked: bool | None = None
    border: TableBorder = F()
    separators: TableSeparator = F()
    column_widths: list[float] = F()
    row_heights: list[float] = F()
    cells: list[TableCell] = F()


class GrTableSch(GrTable):
    _uuid = F()
    cells: list[TableCellSch] = F()  # type: ignore


class GrTablePCB(GrTable):
    layer: BaseLayer = F(Layer.COMMENTS, after="locked")
    cells: list[TableCellPCB] = F(after="row_heights")  # type: ignore


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

    keep_text_aligned: bool | None = F().version(Version.K8.pcb, bare=True, flag=True, after="__begin__")
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
    layer: BaseLayer = Layer.DRAWINGS
    uuid: Uuid = F()
    pts: list[Position] = F()
    style: DimensionStyle = F()


class DimensionCenter(Dimension):
    """Dimension that is just cross to mark center of sth"""

    type: Final[str] = F("center", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]


class DimensionAligned(Dimension):
    type: Final[str] = F("aligned", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    height: float = 0.0
    format: DimensionValueFormat = F()
    text: GrTextPCBBase = F(name="gr_text")


class DimensionOrthogonal(Dimension):
    type: Final[str] = F("orthogonal", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    height: float = 0.0
    orientation: DimensionOrthogonalOrientation = F(DimensionOrthogonalOrientation.HORIZONTAL)
    format: DimensionValueFormat = F()
    text: GrTextPCBBase = F(name="gr_text")


class DimensionLeader(Dimension):
    type: Final[str] = F("leader", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    format: DimensionValueFormat = F()
    text: GrTextPCBBase = F(name="gr_text")


class DimensionRadial(Dimension):
    type: Final[str] = F("radial", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    leader_length: float = 0.0
    format: DimensionValueFormat = F()
    text: GrTextPCBBase = F(name="gr_text")
