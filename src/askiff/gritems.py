from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence
from math import cos, sin
from typing import TYPE_CHECKING, Any, ClassVar, Final, Self, cast

from askiff._auto_serde import AutoSerde, AutoSerdeDownCasting, AutoSerdeDownCastingAgg, AutoSerdeEnum, AutoSerdeFile, F
from askiff._sexpr import GeneralizedSexpr
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


class GrItem(AutoSerdeDownCastingAgg):
    """Base class for KiCad graphic items, providing shared serde logic for PCB and schematic graphics.

    Do not use directly, use specific subclasses like `GrLinePCB`, `GrCirclePCB`, etc.

    During deserialization step `askiff` attempts to downcast each graphic object to the most specific of child classes.

    Multi level inheritance of graphic items works nicely for fine grained filtration of objects:

    * `isinstance(item, GrItem)` - all kind of graphics (PCB, schematic, footprint, symbol)
    * `isinstance(item, GrItemPCB)` - only Graphic items on PCB
    * `isinstance(item, GrShapePCB)` - only Graphic primitive shapes on PCB (e.g. circles, rectangles), \
        inherits also from :class:`askiff.common.BaseShape`
    * `isinstance(item, GrRectPCB)` - only rectangles on PCB

    Naming Scheme:

    * Gr **Rect** PCB -> graphic object type, e.g. rectangle, circle, image, text, ...
    * GrRect **PCB** -> target flavour (ensure that assigned flavour matches type hint in target structure)
        * `Sch` - item for usage in schematics, inherits :class:`askiff.gritems.GrItemSch`
        * `Sym` - item for usage in symbols, inherits :class:`askiff.gritems.GrItemSym`
        * `PCB` - item for usage in board files, inherits :class:`askiff.gritems.GrItemPCB`
        * `Fp` - item for usage in footprints, inherits :class:`askiff.gritems.GrItemFp`

    Examples:
        >>> # Get all rectangles in footprint
        >>> rectangles = (g for g in footprint.graphic_items if isinstance(g, GrRectFp))  # doctest: +SKIP
    """

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


class GrShape(BaseShape):
    """Base graphics shape class for lines, circles, and polygons."""

    stroke: Stroke | None = None
    """Visual styling configuration for the graphical shape's outline and stroke appearance."""


####################Base Classes (file)####################
class GrItemFp(GrItem):
    """Base class for graphic items in footprints.
    Not intended for direct instantiation; use specific subclasses like GrLineFp, GrCircleFp, etc."""

    uuid: Uuid = F()
    """Unique identifier for the footprint graphic item."""


class GrItemPCB(GrItem):
    """Base class for graphic items in PCBs.
    Not intended for direct instantiation; use subclasses like GrLinePCB, GrCirclePCB, etc."""

    uuid: Uuid = F()
    """Unique identifier for the graphical item."""


class GrItemSch(GrItem):
    """Base class for graphic items in schematics.
    Not intended for direct instantiation; use specific subclasses like GrRectSch or GrTextSch."""

    uuid: Uuid = F()
    """Unique identifier for the schematic graphic item."""


class GrItemSym(GrItem):
    """Base class for graphic items in symbols.
    Not intended for direct instantiation; use specific subclasses like GrRectSym or GrTextSym."""

    private: bool = F(bare=True, flag=True)
    """Whether the graphic item is private to the symbol definition."""


class _GrShapePCBFp(GrShape):
    """Graphic shape primitive on PCB or footprint, with layer handling and solder mask margin support.
    Used internally during for parts common between GrShapePCB & GrShapeFp.
    """

    _layers: LayerSet[BaseLayer] = F()
    """If there is solder mask opening, KiCad stores it as two layer, e.g. F.Cu & F.Mask
    `askiff` handles this during serde and exposes single layer to user via `layer` field"""
    solder_mask_margin: float | None = None
    """Solder mask margin value for the graphic shape"""
    layer: BaseLayer = F(Layer.CU_F, skip=True)
    """Layer where the graphic shape is placed"""

    def _askiff_post_deser(self) -> None:
        """Sets the layer field to the first outer copper layer found in `_layers`,
        or the first layer if none are outer copper."""
        self.layer = next((x for x in self._layers if isinstance(x, LayerCopperOuter)), next(x for x in self._layers))

    def _askiff_pre_ser(self) -> Self:
        """Updates internal `_layers` from askiff simplified `layer` field to match KiCad serialization format
        If `solder_mask_margin` is set, it is cleared unless the object is on the top or bottom copper layer.
        In such cases, the corresponding mask layer is added to the layer set."""
        self._layers = LayerSet(self.layer)
        if self.solder_mask_margin:
            if self.layer not in (Layer.CU_B, Layer.CU_F):
                self.solder_mask_margin = None
            else:
                self._layers.add(Layer.MASK_F if self.layer == Layer.CU_F else Layer.MASK_B)
        return self


class GrShapeFp(_GrShapePCBFp, GrItemFp):
    """Base class for primitive graphic shapes in KiCad footprint files.

    Provides the abstract method `to_shape_pcb()` for converting footprint shapes to their PCB equivalents.

    Not intended for direct instantiation; use specific subclasses like GrLineFp, GrCircleFp, etc."""

    @abstractmethod
    def to_shape_pcb(self, fp_position: Position | None = None) -> GrShapePCB:
        """Converts a footprint graphic shape to its corresponding PCB graphic shape representation.

        Args:
            fp_position: Optional position offset to apply when converting the shape's coordinates \
                from footprint to PCB space. If None, no offset is applied. Typically position field from footprint.

        Returns:
            A new GrShapePCB instance with the converted shape data.

        Example:
            >>> from askiff.gritems import GrRectFp, GrRectPCB, GrShapeFp
            >>> from askiff.common import Position
            >>> from askiff.footprint import FootprintBoard
            >>> fp = FootprintBoard(position=Position(5, 5,90))
            >>> fp.graphic_items.append(GrRectFp(start=Position(0, 0), end=Position(10, 20)))
            >>> shape_pcb = [g.to_shape_pcb(fp.position) for g in fp.graphic_items if isinstance(g, GrShapeFp)]
            >>> isinstance(shape_pcb[0], GrRectPCB)
            True
            >>> print(shape_pcb[0].start, shape_pcb[0].end)
            Position(x=5.0, y=5.0, angle=None) Position(x=25.0, y=-4.999999999999999, angle=None)
        """
        ...


class GrShapePCB(_GrShapePCBFp, GrItemPCB):
    """Base class for graphic shape objects in KiCad PCB files.

    Provides shared structure for PCB graphic elements that can have associated net and lock status.

    Not intended for direct instantiation; use specific subclasses like GrLinePCB, GrCirclePCB, etc."""

    net: Net | None = F().version(Version.K9.pcb, serialize=_NetK9Simple._ser, deserialize=_NetK9Simple.deserialize)
    """Net identifier for the graphic shape element."""
    locked: bool | None = None
    """Whether the graphic shape is locked against modifications."""


class GrShapeSch(GrShape, GrItemSch):
    """Represents shapes like lines, circles, or rectangles within schematics.

    Inherits base graphical properties from `GrShape` and symbol-specific context from `GrItemSch`.

    Not intended for direct instantiation; use specific subclasses like GrRectSch or GrPolySch."""

    pass


class GrShapeSym(GrShape, GrItemSym):
    """Represents shapes like lines, circles, or rectangles within a symbol definition.

    Inherits base graphical properties from `GrShape` and symbol-specific context from `GrItemSym`.

    Not intended for direct instantiation; use specific subclasses like GrRectSym or GrPolySym."""

    pass


###########################Common##########################
class FillStylePCBEnum(str, AutoSerdeEnum):
    """Enumeration of fill styles for PCB graphic items.
    Maps to KiCad's sexpr format for polygon and rectangle fill settings.
    """

    NONE = "no"
    HATCH = "hatch"
    HATCH_REVERSE = "reverse_hatch"
    HATCH_CROSS = "cross_hatch"
    SOLID = "yes"

    def ser_k8(self) -> GeneralizedSexpr:
        """Handle representation in K8 files"""
        match self:
            case FillStylePCBEnum.NONE:
                return ("none",)
            case (
                FillStylePCBEnum.SOLID
                | FillStylePCBEnum.HATCH
                | FillStylePCBEnum.HATCH_REVERSE
                | FillStylePCBEnum.HATCH_CROSS
            ):
                return ("solid",)
            case _:
                return (self.value,)

    @classmethod
    def deser_k8(cls, sexp: GeneralizedSexpr) -> FillStylePCBEnum:
        """Handle representation in K8 files"""
        sexp = sexp if isinstance(sexp, str) else sexp[0]
        if not isinstance(sexp, str):
            raise TypeError("PCB fill style in K8 expected be a string")

        match sexp:
            case "none":
                return FillStylePCBEnum.NONE
            case "solid":
                return FillStylePCBEnum.SOLID
            case _:
                return FillStylePCBEnum(sexp)


class FillStyleSchEnum(str, AutoSerdeEnum):
    """Enumeration of schematic fill styles for graphical items.
    Used in schematic elements such as rectangles and circles to define how the interior of the shape is filled."""

    NONE = "none"
    """No fill"""
    HATCH = "hatch"
    """Hatch fill with lines between bottom-left & top-right"""
    HATCH_REVERSE = "reverse_hatch"
    """Hatch fill with lines between bottom-right & top-left"""
    HATCH_CROSS = "cross_hatch"
    """Visually union of HATCH & HATCH_REVERSE fills"""
    SOLID = "color"
    """Solid color fill"""


class FillStyleSch(AutoSerde):
    """Fill style configuration for schematic elements."""

    type: FillStyleSchEnum = F(FillStyleSchEnum.NONE)
    """Schematic fill style type."""
    color: Color | None = F()
    """Fill color, or None for no color."""


class FillStyleSym(AutoSerdeDownCasting):
    """Fill style for symbols. Do not use directly, use one of child classes"""

    _AutoSerdeDownCasting__downcast_field: ClassVar[str] = "type"
    type: Final[str] = F(unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Class constant identifier of fill style"""


class FillStyleSymColor(FillStyleSym):
    """Fill style for symbols using custom color."""

    type: Final[str] = F("color", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Class constant identifier of fill style"""
    color: Color = F()
    """Color of the filled area."""


class FillStyleSymBackground(FillStyleSym):
    """Fill style for symbols using background color."""

    type: Final[str] = F("background", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Class constant identifier of fill style"""


class FillStyleSymOutline(FillStyleSym):
    """Fill style for symbols using outline color."""

    type: Final[str] = F("outline", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Class constant identifier of fill style"""


class FillStyleSymNone(FillStyleSym):
    """Fill style indicating no fill for symbols."""

    type: Final[str] = F("none", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Class constant identifier of fill style"""


############################Arc############################


class GrArcFp(BaseArc, GrShapeFp):
    """Graphic arc item in a KiCad footprint file. Represents an arc segment defined by start, mid, and end points."""

    _askiff_key: ClassVar[str] = "fp_arc"

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrArcPCB:
        """Converts the footprint arc to a PCB arc representation. See :meth:`askiff.gritems.GrShapeFp.to_shape_pcb`"""
        ret = GrArcPCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        ret.to_global(fp_position or Position())
        ret.uuid = Uuid()
        return ret


class GrArcPCB(BaseArc, GrShapePCB):
    """Graphic arc element on a KiCad PCB. Represents an arc segment defined by start, mid, and end points"""

    _askiff_key: ClassVar[str] = "gr_arc"


class GrArcSch(BaseArc, GrShapeSch):
    """Graphic arc item in a KiCad schematic."""

    _askiff_key: ClassVar[str] = "arc"
    fill: FillStyleSch | None = None
    """Fill style for the arc, or None for no fill."""
    uuid: Uuid = F().version(Version.K9.sch, unquoted=True)
    """Unique identifier"""


class GrArcSym(BaseArc, GrShapeSym):
    """Graphic arc item in a KiCad symbol."""

    _askiff_key: ClassVar[str] = "arc"
    fill: FillStyleSym | None = None
    """Fill style for the arc, or None for no fill."""


############################Line###########################


class GrLineFp(BaseLine, GrShapeFp):
    """Represents a straight line segment in footprint defined by start and end points."""

    _askiff_key: ClassVar[str] = "fp_line"

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrLinePCB:
        """Converts this footprint line to a PCB line. See :meth:`askiff.gritems.GrShapeFp.to_shape_pcb`"""
        ret = GrLinePCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        ret.to_global(fp_position or Position())
        ret.uuid = Uuid()
        return ret


class GrLinePCB(BaseLine, GrShapePCB):
    """Represents a straight line segment on PCB defined by start and end points."""

    _askiff_key: ClassVar[str] = "gr_line"


##########################Polygon##########################


class GrPolyFp(BasePoly, GrShapeFp):
    """Graphic polygon shape in a KiCad footprint, supporting filled areas."""

    _askiff_key: ClassVar[str] = "fp_poly"
    fill: FillStylePCBEnum | None = F().version(
        Version.K8.pcb, serialize=FillStylePCBEnum.ser_k8, deserialize=FillStylePCBEnum.deser_k8
    )
    """Fill style for the polygon shape."""

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrPolyPCB:
        """Converts a footprint polygon to a PCB polygon  See :meth:`askiff.gritems.GrShapeFp.to_shape_pcb`"""
        ret = GrPolyPCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        ret.to_global(fp_position or Position())
        ret.uuid = Uuid()
        return ret


class GrPolyPCB(BasePoly, GrShapePCB):
    """Graphic polygon shape in a KiCad PCB, supporting filled areas."""

    _askiff_key: ClassVar[str] = "gr_poly"
    fill: FillStylePCBEnum | None = F().version(
        Version.K8.pcb, serialize=FillStylePCBEnum.ser_k8, deserialize=FillStylePCBEnum.deser_k8
    )
    """Fill style for the polygon element."""


class GrPolySch(BasePoly, GrShapeSch):
    """Graphic polyline item in a KiCad schematic."""

    _askiff_key: ClassVar[str] = "polyline"
    fill: FillStyleSch | None = None
    """Fill style"""

    def _askiff_pre_ser(self) -> GrPolySch:
        """Prepares the object for serialization by selecting the appropriate field serialization strategy \
            based on the file version and fill property."""
        if AutoSerdeFile._version <= Version.K9.sch and self.fill:
            self._AutoSerde__ser_field = _GrPolySchUnquoteUuid._AutoSerde__ser_field  # type: ignore  # ty:ignore[unresolved-attribute]
        else:
            self._AutoSerde__ser_field = GrPolySch._AutoSerde__ser_field  # type: ignore  # ty:ignore[unresolved-attribute]
        return self


class _GrPolySchUnquoteUuid(GrPolySch):
    """Graphic polyline item in KiCad schematics with unquoted UUIDs.
    Used internally for correct serialization of UUID fields in schematic files in K9 and earlier."""

    uuid: Uuid = F().version(Version.K9.sch, unquoted=True)
    """Unique identifier for the schematic polyline item."""


class GrPolySym(BasePoly, GrShapeSym):
    """Graphic polygon item in a KiCad schematic symbol file."""

    _askiff_key: ClassVar[str] = "polyline"
    fill: FillStyleSym | None = None
    """Fill style for the polygon"""


###########################Bezier##########################


class GrCurveFp(BaseBezier, GrShapeFp):
    """Represents a cubic Bézier curve in footprint with optional fill style."""

    _askiff_key: ClassVar[str] = "fp_curve"
    fill: FillStylePCBEnum | None = F().version(
        Version.K8.pcb, serialize=FillStylePCBEnum.ser_k8, deserialize=FillStylePCBEnum.deser_k8
    )
    """Fill style for the curve item."""

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrCurvePCB:
        """Converts a footprint curve to a PCB curve with global coordinates. \
            See :meth:`askiff.gritems.GrShapeFp.to_shape_pcb`"""
        ret = GrCurvePCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        ret.to_global(fp_position or Position())
        ret.uuid = Uuid()
        return ret

    def _askiff_post_deser(self) -> None:
        """Post-deserialization handler for GrCurveFp.
        Invokes parent class handlers to ensure proper initialization of graphic curve properties \
            and Bezier curve data after deserialization."""
        _GrShapePCBFp._askiff_post_deser(self)
        BaseBezier._askiff_post_deser(self)

    def _askiff_pre_ser(self) -> Self:
        """Prepares the GrCurveFp instance for serialization by applying base bezier and shape preprocessing."""
        return _GrShapePCBFp._askiff_pre_ser(BaseBezier._askiff_pre_ser(self))  # type: ignore # ty:ignore[invalid-argument-type]


class GrCurvePCB(BaseBezier, GrShapePCB):
    """Represents a cubic Bézier curve on PCB with optional fill style."""

    _askiff_key: ClassVar[str] = "gr_curve"
    fill: FillStylePCBEnum | None = F().version(
        Version.K8.pcb, serialize=FillStylePCBEnum.ser_k8, deserialize=FillStylePCBEnum.deser_k8
    )
    """Fill style for the curve element."""

    def _askiff_post_deser(self) -> None:
        """Post-deserialization handler.
        Ensures proper initialization of graphic curve properties and Bezier curve data after deserialization."""
        _GrShapePCBFp._askiff_post_deser(self)
        BaseBezier._askiff_post_deser(self)

    def _askiff_pre_ser(self) -> Self:
        """Prepares the instance for serialization by applying base bezier and shape preprocessing."""
        return _GrShapePCBFp._askiff_pre_ser(BaseBezier._askiff_pre_ser(self))  # type: ignore # ty:ignore[invalid-argument-type]


class GrCurveSch(BaseBezier, GrShapeSch):
    """Graphic cubic Bézier curve item in a KiCad schematic."""

    _askiff_key: ClassVar[str] = "bezier"
    fill: FillStyleSch | None = None
    """Fill style for the curve, or None for no fill."""
    uuid: Uuid = F().version(Version.K9.sch, unquoted=True)
    """Unique identifier for the curve item."""


class GrCurveSym(BaseBezier, GrShapeSym):
    """Graphic cubic Bézier curve item in a KiCad symbols."""

    _askiff_key: ClassVar[str] = "bezier"
    fill: FillStyleSym | None = None
    """Fill style"""


###########################Circle##########################


class GrCircleFp(BaseCircle, GrShapeFp):
    """Graphic circle item in a KiCad footprint, defined by its center and a point on its circumference."""

    _askiff_key: ClassVar[str] = "fp_circle"
    fill: FillStylePCBEnum | None = F(FillStylePCBEnum.NONE).version(
        Version.K8.pcb, serialize=FillStylePCBEnum.ser_k8, deserialize=FillStylePCBEnum.deser_k8
    )
    """Fill style for the circle shape."""

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrCirclePCB:
        """Converts this footprint circle to a PCB circle,  See :meth:`askiff.gritems.GrShapeFp.to_shape_pcb`"""
        ret = GrCirclePCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        ret.to_global(fp_position or Position())
        ret.uuid = Uuid()
        return ret


class GrCirclePCB(BaseCircle, GrShapePCB):
    """Graphic circle item in a KiCad PCB, defined by its center and a point on its circumference."""

    _askiff_key: ClassVar[str] = "gr_circle"
    fill: FillStylePCBEnum | None = F(FillStylePCBEnum.NONE).version(
        Version.K8.pcb, serialize=FillStylePCBEnum.ser_k8, deserialize=FillStylePCBEnum.deser_k8
    )
    """Fill style for the circle element."""


class GrCircleSch(GrShapeSch):
    """Represents a circle in schematic with center position, radius, and optional fill style."""

    _askiff_key: ClassVar[str] = "circle"
    center: Position = F()
    """Center position of the circle"""
    radius: float = F()
    """Circle radius"""
    fill: FillStyleSch | None = F()
    """Fill style configuration"""

    def extrema_points(self) -> Sequence[Position]:
        """Returns the top, bottom, left, and rightmost points on the circle's circumference"""
        return BaseCircle(self.center, Position(self.center.x + self.radius, self.center.y)).extrema_points()

    def to_global(self, ref_pos: Position) -> None:
        """Converts the circle's center coordinates from local to global space using the given reference position."""
        self.center = self.center.to_global(ref_pos)


class GrCircleSym(GrShapeSym):
    """Represents a circle in symbol with center position, radius, and optional fill style."""

    _askiff_key: ClassVar[str] = "circle"
    center: Position = F()
    """Center position of the circle in schematic coordinates."""
    radius: float = F()
    """Circle radius in world coordinates."""
    fill: FillStyleSym | None = F()
    """Fill style for the schematic symbol circle."""

    def extrema_points(self) -> Sequence[Position]:
        """Returns the top, bottom, left, and rightmost points on the circle's circumference"""
        return BaseCircle(self.center, Position(self.center.x + self.radius, self.center.y)).extrema_points()

    def to_global(self, ref_pos: Position) -> None:
        """Changes circle center coordinates in place to global ones using ref_pos as current origin."""
        self.center = self.center.to_global(ref_pos)


#########################Rectangle#########################


class GrRectFp(BaseRect, GrShapeFp):
    """Graphic rectangle item in a KiCad footprint file."""

    _askiff_key: ClassVar[str] = "fp_rect"
    fill: FillStylePCBEnum | None = F(FillStylePCBEnum.NONE).version(
        Version.K8.pcb, serialize=FillStylePCBEnum.ser_k8, deserialize=FillStylePCBEnum.deser_k8
    )
    """Fill style"""

    def to_shape_pcb(self, fp_position: Position | None = None) -> GrRectPCB:
        """Converts this footprint rectangle to a PCB rectangle. See :meth:`askiff.gritems.GrShapeFp.to_shape_pcb`"""
        ret = GrRectPCB(**{k: v for k, v in self.__dict__.items() if k in self._GrItem__askiff_order})  # type: ignore  # ty:ignore[unresolved-attribute]
        ret.to_global(fp_position or Position())
        ret.uuid = Uuid()
        return ret


class GrRectPCB(BaseRect, GrShapePCB):
    """Graphic rectangle item on a KiCad PCB."""

    _askiff_key: ClassVar[str] = "gr_rect"
    fill: FillStylePCBEnum | None = F(FillStylePCBEnum.NONE).version(
        Version.K8.pcb, serialize=FillStylePCBEnum.ser_k8, deserialize=FillStylePCBEnum.deser_k8
    )
    """Fill style"""


class GrRectSch(BaseRect, GrShapeSch):
    """Graphic rectangle item in a KiCad schematic."""

    _askiff_key: ClassVar[str] = "rectangle"
    fill: FillStyleSch | None = F()
    """Fill style"""
    uuid: Uuid = F().version(Version.K9.sch, unquoted=True)
    """Unique identifier"""


class GrRectSym(BaseRect, GrShapeSym):
    """Graphic rectangle item in a KiCad symbol."""

    _askiff_key: ClassVar[str] = "rectangle"
    fill: FillStyleSym | None = F()
    """Fill style"""


############################Text###########################


class RenderCache(AutoSerde):
    """Cached rendering entry for KiCad text item"""

    text: str = F(positional=True)
    """Text content"""
    mode: int = F(positional=True)
    """Render mode"""
    poly: list[BasePoly] = F(name="polygon", flatten=True)
    """Polygons of rendered entry."""


class TextType(str, AutoSerdeEnum):
    """Enumeration for KiCad text type in footprint"""

    USER = "user"


class GrText(AutoSerde):
    """Base class for graphic text item on a KiCad schematic or PCB.
    Do not use directly, use one of child classes"""

    text: str = F(positional=True)
    """Text content."""
    effects: Effects = F()
    """Text element formatting properties including font, justification, and visibility."""
    position: Position = F(name="at")
    """Text element position and optional rotation angle."""


class GrTextPCBBase(GrText):
    """Base for graphic text item on a KiCad PCB or Footprint
    Do not use directly, use one of child classes
    """

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
    """Whether the text has a knockout effect applied."""
    _layers: LayerSet[BaseLayer] = F()
    uuid: Uuid = F()
    """Unique identifier"""
    layer: BaseLayer = F(Layer.COMMENTS, skip=True)
    """PCB layer where the text item is rendered."""

    def _askiff_post_deser(self) -> None:
        """Handle KiCad way of serializing `knockout` token"""
        self.layer = next(x for x in self._layers)
        self.knockout = self._layers._knockout

    def _askiff_pre_ser(self) -> GrTextPCBBase:
        """Handle KiCad way of serializing `knockout` token"""
        self._layers = LayerSet(self.layer)
        self._layers._knockout = self.knockout
        return self


class GrTextFp(GrTextPCBBase, GrItemFp):
    """Graphic text item with footprint specific attributes"""

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
        "_hide",
    ]
    type: TextType = F(TextType.USER, positional=True)
    """Text element type"""
    render_cache: RenderCache | None = None
    """Cached rendering data"""
    locked: bool | None = F.unlocked()
    """Whether the text item is locked in the footprint editor."""
    _hide: bool | None = F(skip=True).version(Version.K8.fp, skip=False)
    """[K9: Deprecated] K9 largely replaced text usage with properties, this was K8 way of handling properties"""


class GrTextPCB(GrTextPCBBase, GrItemPCB):
    """Graphic text item with board specific attributes"""

    _askiff_key: ClassVar[str] = "gr_text"
    render_cache: RenderCache | None = None
    """Cached rendering data for the text item"""
    locked: bool | None = F()
    """Whether the text item is locked against modifications."""


class GrTextSch(GrText, GrItemSch):
    """Graphic text item on a KiCad schematic. May be used for simulation directives."""

    _askiff_key: ClassVar[str] = "text"
    __askiff_order: ClassVar[list[str]] = ["text", "exclude_from_sim", "locked", "position", "effects", "uuid"]
    exclude_from_sim: bool | None = None
    """Whether the text item is excluded from simulation."""


class GrTextSym(GrText, GrItemSym):
    """Graphic text item in a KiCad symbol"""

    _askiff_key: ClassVar[str] = "text"
    __askiff_order: ClassVar[list[str]] = ["private", "text", "exclude_from_sim", "locked", "position", "effects"]
    private: bool = F(bare=True, flag=True)
    """Whether the text is private to the symbol"""
    exclude_from_sim: bool | None = None
    """Whether the text is excluded from simulation."""


##########################TextBox##########################
class TextMargin(AutoSerde, positional=True):  # type:ignore
    """Text margin configuration for boxed text elements.
    Defines spacing around text in four directions: left, top, right, and bottom.
    Values are in millimeters and default to 1.0025 mm each."""

    left: float = 1.0025
    """Left text margin in millimeters."""
    top: float = 1.0025
    """Top text margin in millimeters."""
    right: float = 1.0025
    """Right text margin in millimeters."""
    bottom: float = 1.0025
    """Bottom text margin in millimeters."""


class RectTextBox(AutoSerde):
    """Boxed text, used for tables and texts with frame"""

    margins: TextMargin | None = None
    """Spacing around text content within the box in millimeters"""


class RectTextBoxPCB(RectTextBox):
    """Represents a rectangular text box on a KiCad PCB, used for annotations or labels.
    Supports both axis-aligned and rotated orientations via unified `position` and `size` properties.

    # Dev Notes:
    Reason for this class is that KiCad serializes rectangle on PCB differently depending if it is rotated or not
    This class provides unified way of handling this, and maintains the same API as schematic counterpart
    """

    _pts: list[Position] | None = F()
    _start: Position | None = F()
    _end: Position | None = F()
    margins: TextMargin | None = None
    """Spacing around text content within the box in millimeters"""
    _angle: float | None = F()

    def __set_from_pos_size(self, pos: Position, size: Size) -> None:
        """Sets the position and size of a PCB rectangle or textbox,
        updating internal point coordinates based on whether the object is rotated.
        If the position includes an angle, the method calculates rotated corner points;
        otherwise, it sets the start and end coordinates directly."""
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
        """Position of rectangle center and its rotation"""
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
        """Position of rectangle center and its rotation"""
        self.__set_from_pos_size(val, self.size)

    @property
    def size(self) -> Size:
        """Size of rectangle"""
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
        """Size of rectangle"""
        self.__set_from_pos_size(self.position, val)


class RectTextBoxSch(RectTextBox):
    """Represents a rectangular text box in a KiCad schematic."""

    position: Position = F(name="at")
    """Position of the text box in the schematic"""
    size: Size = F()
    """Size of the text box"""
    margins: TextMargin | None = None
    """Spacing around text content within the box in millimeters"""


class GrTextBox(AutoSerde):
    """Graphic text box item with frame on a KiCad schematic or PCB."""

    __askiff_order: ClassVar[list[str]] = []
    text: str = F(positional=True)
    """Text content"""
    border: bool | None = None
    """Whether the text box has a border."""
    border_stroke: Stroke | None = F(name="stroke")
    """Border stroke styling including thickness, line style, and color."""
    effects: Effects = F()
    """Text visual formatting properties including font, justification, and visibility."""
    box: RectTextBox = F(inline=True)
    """Rectangle defining text box boundaries and margins."""


class _GrTextBoxFpPCB(GrTextBox):
    """Base for graphic text box item on a KiCad footprint or PCB."""

    box: RectTextBoxPCB = F(inline=True, after="text")
    """Rectangle defining text box boundaries and margins."""
    layer: BaseLayer = F(Layer.COMMENTS)
    """Layer on which the text box is placed"""
    uuid: Uuid = F()
    """Unique identifier"""
    effects: Effects = F()
    """Text visual formatting properties including font, justification, and visibility."""
    render_cache: RenderCache | None = F(after="border_stroke")
    """Cached rendered text"""
    knockout: bool | None = None
    """Whether the text has a knockout effect."""


class GrTextBoxFp(_GrTextBoxFpPCB, GrItemFp):
    """Graphic text box (text with frame) item on a KiCad footprint."""

    _askiff_key: ClassVar[str] = "fp_text_box"


class GrTextBoxPCB(_GrTextBoxFpPCB, GrItemPCB):
    """Graphic text box (text with frame) item on a KiCad PCB."""

    _askiff_key: ClassVar[str] = "gr_text_box"


class GrTextBoxSch(GrTextBox, GrItemSch):
    """Graphic text box item (text with frame) on a KiCad schematic."""

    _askiff_key: ClassVar[str] = "text_box"
    exclude_from_sim: bool | None = F(after="text")
    """Whether the text box is ignored during simulation"""
    box: RectTextBoxSch = F(inline=True)
    """Rectangle defining text box boundaries and optional margins."""
    fill: FillStyleSch | None = F(after="border_stroke")
    """Fill style configuration"""
    uuid: Uuid = F(after="locked").version(Version.K9.sch, after="effects")
    """Unique identifier"""


class GrTextBoxSym(GrTextBox, GrItemSym):
    """Graphic text box item (text with frame) on a KiCad schematic symbol."""

    _askiff_key: ClassVar[str] = "text_box"
    exclude_from_sim: bool | None = F(after="text")
    """Whether the text box is ignored during simulation"""
    box: RectTextBoxSch = F(inline=True)
    """Rectangle defining text box boundaries and margins."""
    fill: FillStyleSym | None = F(after="border_stroke")
    """Fill style for the text box"""


###########################Image###########################
class ImagePCB(GrItemFp, GrItemPCB):
    """Represents an image in a KiCad PCB or footprint."""

    _askiff_key: ClassVar[str] = "image"
    __askiff_order: ClassVar[list[str]] = []
    position: Position = F(name="at")
    """Image position on the PCB board"""
    scale: float | None = None
    """Image scaling factor; None for default size."""
    layer: BaseLayer | None = None
    """Layer on which the image is placed"""
    data: DataBlock = F(serialize=DataBlock.serialize_quoted, deserialize=DataBlock.deserialize_quoted)
    """Embedded image data"""
    _uuid = F()


class ImageSch(GrItemSch):
    """Represents an image in a KiCad Schematic file."""

    _askiff_key: ClassVar[str] = "image"
    __askiff_order: ClassVar[list[str]] = []
    position: Position = F(name="at")
    """Position of the image in the schematic."""
    scale: float | None = None
    """Image scaling factor in schematic; None for default size."""
    _uuid = F()
    data: DataBlock = F(serialize=DataBlock.serialize_quoted, deserialize=DataBlock.deserialize_quoted)
    """Embedded image data"""


##########################Barcode##########################
class BarcodeType(str, AutoSerdeEnum):
    """Represents supported barcode types"""

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
    """Represents supported QR codecorrection levels"""

    L = "L"
    """~20% error correction"""
    M = "M"
    """~37% error correction"""
    Q = "Q"
    """~55% error correction"""
    H = "H"
    """~65% error correction"""


class Barcode(AutoSerde):
    """Barcode represents a barcode graphic element in a board or footprint."""

    _askiff_key: ClassVar[str] = "barcode"
    position: Position = F(name="at")
    """Position of the barcode anchor point"""
    layer: BaseLayer = F(Layer.SILKS_F)
    """PCB layer on which the barcode is placed"""
    size: Size = F()
    """Size of the barcode graphic element"""
    text: str = ""
    """Text content of the barcode."""
    text_height: float = 1.5
    """Text height for text under the barcode."""
    type: BarcodeType = F(BarcodeType.QR)
    """Barcode type, such as QR or EAN."""
    ecc_level: BarcodeECCLevel = F(BarcodeECCLevel.M)
    """Error correction level for QR code"""
    hide: bool = False
    """Whether the barcode is hidden."""
    knockout: bool = False
    """Whether the barcode fill is inverted (knockout effect)."""
    uuid: Uuid = F()
    """Unique identifier"""


###########################Table###########################
class TableBorder(AutoSerde):
    """Represents a border in a KiCad table, defining its visual properties and position."""

    external: bool = False
    """Whether table external border is enabled."""
    header: bool = False
    """Whether table header border is enabled."""
    stroke: Stroke | None = None
    """Line styling information for the border outline."""


class TableSeparator(AutoSerde):
    """Represents a table separator in a KiCad schematic,
    defining how table cells are divided by horizontal and vertical lines."""

    rows: bool = False
    """Whether the separator between rows is enabled"""
    cols: bool = False
    """Whether the separator between columns is enabled"""
    stroke: Stroke | None = None
    """Line style and thickness of the table separator."""


class TableCell(AutoSerde):
    """Represents a cell within a KiCad table structure"""

    text: str = F(positional=True)
    """Text content of the table cell."""
    box: RectTextBox = F(inline=True)
    """Bounding box coordinates of the table cell."""
    span: list[int] = F()
    """Cell merging span in table layout:
    
    * [1,1] - no cell merging
    * [2,1] - merge cell with one from next column
    """
    uuid: Uuid = F()
    """Unique identifier for the table cell."""
    effects: Effects | None = None
    """Visual formatting properties for the table cell's text content"""


class TableCellSch(TableCell):
    """Represents a cell within a KiCad schematic table structure."""

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
    """Bounding box coordinates and size of the table cell."""
    fill: FillStyleSym | None = None
    """Fill style for the table cell."""
    exclude_from_sim: bool = F()
    """Whether the cell content is ignored during simulation."""


class TableCellPCB(TableCell):
    """Represents a table cell on a PCB or footprint"""

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
    """Bounding box defining cell's position and size on the PCB."""
    layer: BaseLayer | None = None
    """Layer on which the table cell is placed."""
    render_cache: RenderCache | None = None
    """Cached rendering data for the cells text"""


class GrTable(AutoSerde):
    """Represents a graphical table in KiCad schematics or boards."""

    column_count: int = F()
    """Number of columns in the table."""
    uuid: Uuid | None = None
    """Unique identifier for the table item."""
    locked: bool | None = None
    """Whether the table is locked against modifications."""
    border: TableBorder = F()
    """Table border configuration including style and positioning."""
    separators: TableSeparator = F()
    """Whether table separators are enabled"""
    column_widths: list[float] = F()
    """Column widths in the table."""
    row_heights: list[float] = F()
    """Row heights in the table."""
    cells: list[TableCell] = F()
    """Cells within the table structure."""


class GrTableSch(GrTable):
    """Represents a graphical table in KiCad schematics"""

    _uuid = F()
    cells: list[TableCellSch] = F()  # type: ignore
    """Cells within the schematic table structure."""


class GrTablePCB(GrTable):
    """Represents a graphical table in KiCad boards or footprints."""

    layer: BaseLayer = F(Layer.COMMENTS, after="locked")
    """PCB layer where the table is placed."""
    cells: list[TableCellPCB] = F(after="row_heights")  # type: ignore
    """List of table cells with PCB-specific properties."""


########################Dimensions#########################
class DimensionTextPosition(str, AutoSerdeEnum):
    """Enum for specifying the position of dimension text in KiCad drawings"""

    OUTSIDE = "0"
    """Text outside the dimension line"""
    INLINE = "1"
    """Text in line with the dimension line"""
    MANUAL = "2"
    """Text manually placed by user"""


class DimensionArrowDirection(str, AutoSerdeEnum):
    """Enumeration for specifying the direction of dimension arrows in KiCad."""

    OUT = "outward"
    IN = "inward"


class DimensionTextFrame(str, AutoSerdeEnum):
    """Style of the frame around the dimension text"""

    NONE = "0"
    RECTANGLE = "1"
    CIRCLE = "2"


class DimensionUnit(str, AutoSerdeEnum):
    """Enumeration for KiCad dimension unit"""

    INCH = "0"
    MILS = "1"
    MM = "2"
    AUTO = "3"


class DimensionUnitStyle(str, AutoSerdeEnum):
    """Enum representing the style of unit display in KiCad dimension text"""

    SKIP = "0"
    """Skip adding units"""
    BARE = "1"
    """Add bare unit string"""
    PARENTHESIS = "2"
    """Wrap unit in parenthesis"""


class DimensionStyle(AutoSerde):
    """Style configuration for dimension components in PCB or footprint."""

    thickness: float = 0.0
    """Line/arrow thickness"""

    arrow_length: float = 0.0
    """Length of dimension arrows"""

    text_position_mode: DimensionTextPosition = DimensionTextPosition.OUTSIDE  # type: ignore
    """Positioning of dimension text relative to the dimension line"""

    arrow_direction: DimensionArrowDirection | None = None
    """Direction of dimension arrows"""

    extension_height: float | None = None
    """Length of the extension lines past the dimension crossbar"""

    text_frame: DimensionTextFrame | None = None
    """Style of frame around dimension text. Leader dimensions only"""

    extension_offset: float | None = None
    """Distance between feature point and extension line"""

    keep_text_aligned: bool | None = F().version(Version.K8.pcb, bare=True, flag=True, after="__begin__")
    """If true dimension text will always be left2right or bottom2top"""


class DimensionValueFormat(AutoSerde):
    """Format specification for dimension text values. Controls how dimension measurements are displayed,
    including units, precision, prefixes, suffixes, and zero suppression"""

    prefix: str = ""
    """Text prepended to dimension value"""

    suffix: str = ""
    """Text appended to dimension value"""

    units: DimensionUnit = DimensionUnit.AUTO  # type: ignore
    """Units to display after dimension value"""

    units_format: DimensionUnitStyle = DimensionUnitStyle.BARE  # type: ignore
    """How the unit's suffix is formatted in dimension annotations"""

    precision: int = 4
    """Number of significant digits to display in dimension value"""

    override_value: str | None = None
    """Override value of the dimension's physical measurement"""

    suppress_zeroes: bool | None = None
    """Whether trailing zeros are removed from dimension value"""


class DimensionOrthogonalOrientation(str, AutoSerdeEnum):
    """Enum representing the orientation of an orthogonal dimension"""

    HORIZONTAL = "0"
    VERTICAL = "1"


class Dimension(AutoSerdeDownCasting):
    """Base class for KiCad dimension objects,
    automatically down casting to specific types like DimensionOrthogonal or DimensionRadial during deserialization.
    Use subclasses for type-safe handling of different dimension styles."""

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
    """Whether the dimension item is locked"""
    layer: BaseLayer = Layer.DRAWINGS
    """Layer on which the dimension is drawn"""
    uuid: Uuid = F()
    """Unique identifier for the dimension object"""
    pts: list[Position] = F()
    """Points defining features the dimension describes"""
    style: DimensionStyle = F()
    """Style configuration for dimension text"""


class DimensionCenter(Dimension):
    """Dimension that is just cross to mark center of something."""

    type: Final[str] = F("center", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Class constant serialized dimension type keyword"""


class DimensionAligned(Dimension):
    """Aligned dimension object (both extension lines of the same length)"""

    type: Final[str] = F("aligned", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Class constant serialized dimension type keyword"""
    height: float = 0.0
    """Dimension height (from feature points to dimension crossbar)."""
    format: DimensionValueFormat = F()
    """Format of dimension text"""
    text: GrTextPCBBase = F(name="gr_text")
    """Text content of the dimension measurement."""


class DimensionOrthogonal(Dimension):
    """Orthogonal dimension item,
    representing linear measurements with horizontal or vertical orientation."""

    type: Final[str] = F("orthogonal", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Class constant serialized dimension type keyword"""
    height: float = 0.0
    """Dimension height (from feature points to dimension crossbar)."""
    orientation: DimensionOrthogonalOrientation = F(DimensionOrthogonalOrientation.HORIZONTAL)
    """Orientation of the orthogonal dimension line."""
    format: DimensionValueFormat = F()
    """Format of dimension text"""
    text: GrTextPCBBase = F(name="gr_text")
    """Text content of the dimension measurement."""


class DimensionLeader(Dimension):
    """Represents a leader dimension with a leader line pointing to the dimensioned feature"""

    type: Final[str] = F("leader", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Class constant serialized dimension type keyword"""
    format: DimensionValueFormat = F()
    """Format of dimension text"""
    text: GrTextPCBBase = F(name="gr_text")
    """Text content of the dimension."""


class DimensionRadial(Dimension):
    """Radial dimension object, used to represent radial measurements with leader lines"""

    type: Final[str] = F("radial", unquoted=True)  # type: ignore  # ty:ignore[override-of-final-variable]
    """Class constant serialized dimension type keyword"""
    leader_length: float = 0.0
    """Length of the leader line"""
    format: DimensionValueFormat = F()
    """Format of dimension text"""
    text: GrTextPCBBase = F(name="gr_text")
    """Text content of the dimension measurement."""
