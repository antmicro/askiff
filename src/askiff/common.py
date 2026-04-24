from __future__ import annotations

import base64
import textwrap
import uuid
from abc import abstractmethod
from collections.abc import Iterable, Sequence
from math import atan2, cos, hypot, pi, radians, sin, sqrt
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar, cast, overload

from askiff._auto_serde import AutoSerde, AutoSerdeEnum, AutoSerdeFile, F
from askiff._sexpr import GeneralizedSexpr, Qstr
from askiff.const import Version

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore

DEFAULT_DATA_CHUNK_LENGTH = 76


class Position(AutoSerde):
    """Position represents a point in 2D space, optionally with an angle. Used for coordinates in KiCad files."""

    _askiff_key: ClassVar[str] = "xy"
    x: float = F(positional=True)
    """X coordinate of the position."""
    y: float = F(positional=True)
    """Y coordinate of the position."""
    angle: float | None = F(positional=True, precision=8)
    """Rotation angle of the position in degrees."""

    def serialize(self) -> GeneralizedSexpr:
        """Serializes the position into a generalized S-Expression format"""
        ang = self.angle
        extra = self._AutoSerde__extra  # type: ignore # ty:ignore[unresolved-attribute]
        if ang is None:
            return (f"{self.x:.6f}".rstrip("0").rstrip("."), f"{self.y:.6f}".rstrip("0").rstrip("."), *(extra or ()))
        return (
            f"{self.x:.6f}".rstrip("0").rstrip("."),
            f"{self.y:.6f}".rstrip("0").rstrip("."),
            f"{ang:.8f}".rstrip("0").rstrip("."),
            *(extra or ()),
        )

    @classmethod
    def deserialize(cls, sexp: GeneralizedSexpr) -> Position:
        """Deserializes a Position from a sexpr list"""
        x, y, *extra = sexp
        ret = Position(float(x), float(y))  # type: ignore
        if extra:
            try:
                ret.angle = float(extra[0])  # type: ignore
                extra = extra[1:]
            except ValueError:
                pass
            ret._AutoSerde__extra = extra  # type: ignore # ty:ignore[unresolved-attribute]
        return ret

    def distance(self, to: Position) -> float:
        """Compute the Euclidean distance between this position and another position.

        Example:
            >>> from askiff.board import Position
            >>> p1 = Position(0, 0)
            >>> p2 = Position(3, 4)
            >>> p1.distance(p2)
            5.0
        """
        return hypot(self.x - to.x, self.y - to.y)

    def vector_angle(self, to: Position) -> float:
        """Finds normalized angle in radians of vector between this point and another point.

        Example:
            >>> from askiff.common import Position
            >>> p1 = Position(0, 0)
            >>> p2 = Position(1, 1)
            >>> angle = p1.vector_angle(p2)
            >>> print(f"{angle:.4f}")
            0.7854
        """
        angle = atan2(to.y - self.y, to.x - self.x)
        angle %= 2 * pi
        return angle

    def to_global(self, ref_pos: Position) -> Position:
        """Converts this position to global coordinates using the given reference position as the origin and rotation.

        Example:
            >>> from askiff.board import Position
            >>> local = Position(10, 20, 45)
            >>> ref = Position(100, 200, 0)
            >>> global_pos = local.to_global(ref)
            >>> print(global_pos.x, global_pos.y)
            110.0 220.0
        """
        angle = radians(-ref_pos.angle if ref_pos.angle is not None else 0)
        sina, cosa = sin(angle), cos(angle)

        return Position(ref_pos.x + self.x * cosa - self.y * sina, ref_pos.y + self.x * sina + self.y * cosa)


class LibId(AutoSerde):
    """Library identifier for KiCad symbols and footprints"""

    library: str | None = None
    """Library name part of the identifier"""

    name: str = ""
    """Footprint or symbol name within the library"""

    def serialize(self) -> GeneralizedSexpr:
        """Serializes the library ID into a sexpr representation.
        Returns `library:name` if the library is set, otherwise just `name`"""
        if self.library:
            return (Qstr(f"{self.library}:{self.name}"),)
        return (Qstr(self.name),)

    @classmethod
    def deserialize(cls, sexp: GeneralizedSexpr) -> LibId:
        """Deserializes a KiCad library identifier from a sexpr string or list."""
        sexp = sexp if isinstance(sexp, str) else sexp[0]
        if not isinstance(sexp, str):
            raise TypeError("Library ID expected to be a string")
        spl = sexp.partition(":")
        return LibId(spl[0], spl[2]) if spl[1] else LibId(None, spl[0])


class Uuid(str):
    """Wrapper that stores KiCad object UUIDs (globally unique identifiers).
    Note: Auto-generates new UUID on copy, ensuring uniqueness for each object.
    """

    def __new__(cls, value: str | None = None) -> Uuid:
        """Uuid factory for generating or wrapping UUID strings.
        If no value is provided, a new random UUID is generated.
        Example: `Uuid()` or `Uuid('12345678-1234-5678-1234-567812345678')`"""
        if value is None:
            value = str(uuid.uuid4())
        return cast(Uuid, value)

    # Override copy methods to ensure that when coping kicad objects, no duplicate uuid will be produced
    def __copy__(self) -> Uuid:
        return Uuid()

    def __deepcopy__(self, _) -> Uuid:  # type: ignore # noqa: ANN001
        return Uuid()


class Color(AutoSerde, positional=True):  # type: ignore
    """Color represents a RGBA color value used in KiCad files."""

    R: int = 0
    """Red component value, from 0 to 255"""
    G: int = 0
    """Green component value, from 0 to 255"""
    B: int = 0
    """Blue component value, from 0 to 255"""
    A: float = F(precision=10)
    """Alpha transparency level, from 0.0 to 1.0"""


class Size(AutoSerde, positional=True):  # type: ignore
    """Size represents a two-dimensional dimension with height and width attributes,
    typically used for defining the size of graphical elements in KiCad files"""

    height: float = 1
    """Height of an object"""
    width: float = 1
    """Width of an object"""


class Font(AutoSerde):
    """Text font configuration"""

    _askiff_key: ClassVar[str] = "font"
    face: str | None = None
    """Font face name for text elements"""
    size: Size = F()
    """Font size in millimeters"""
    thickness: float | None = None
    """Line thickness of the font"""
    bold: bool | None = None
    """Whether the font is bold"""
    italic: bool | None = None
    """Whether the font is italicized"""
    line_spacing: bool | None = None
    """Whether line spacing is enabled for the font"""
    color: Color | None = None
    """Text color"""


class JustifyV(str, AutoSerdeEnum):
    """Vertical text justification options for KiCad texts."""

    TOP = "top"
    CENTER = ""
    BOTTOM = "bottom"


class JustifyH(str, AutoSerdeEnum):
    """Horizontal text justification options for KiCad texts."""

    LEFT = "left"
    CENTER = ""
    RIGHT = "right"


class Justify(AutoSerde, flag=True, bare=True):  # type: ignore
    """Justification settings for text elements, specifying horizontal and vertical alignment along with mirroring."""

    horizontal: JustifyH = F(JustifyH.CENTER)
    """Horizontal text justification option."""
    vertical: JustifyV = F(JustifyV.CENTER)
    """Vertical text justification option."""
    mirror: bool = False
    """Whether the text is mirrored horizontally."""


class Effects(AutoSerde):
    """Visual formatting properties for text elements in KiCad schematics and boards.
    Controls font settings, text justification, and visibility state.
    """

    font: Font = F()
    """Font settings including size, thickness, and style."""
    justify: Justify | None = F()
    """Text alignment including horizontal, vertical alignment and mirroring."""
    hide: bool | None = F(skip=True).version(Version.K9.sch, skip=False)
    """Whether the text element is hidden."""
    href: str | None = None
    """URL reference for the text element."""


class StrokeStyle(str, AutoSerdeEnum):
    """Enumeration of (line) stroke  styles used in KiCad graphic items"""

    DEFAULT = "default"
    DOT = "dot"
    DASH = "dash"
    DASH_DOT = "dash_dot"
    DASH_DOT_DOT = "dash_dot_dot"
    SOLID = "solid"


class Stroke(AutoSerde):
    """Stroke represents the visual styling of lines"""

    width: float = F()
    """Line thickness in millimeters."""
    style: StrokeStyle = F(StrokeStyle.DEFAULT, name="type")
    """Line style, such as solid, dashed, or dotted."""
    color: Color | None = None
    """Line color. If None, the default color is used."""


class Property(AutoSerde):
    """Stores object metadata such as Reference, Value, Datasheet, etc."""

    _askiff_key: ClassVar[str] = "property"

    name: str = F(positional=True)
    """Property name such as Reference, Value, Datasheet"""

    value: str = F(positional=True)
    """Value of the property"""

    position: Position = F(name="at")
    """Property text position including optional angle"""

    hide: bool | None = None
    """Whether the property text is hidden."""

    effects: Effects | None = None
    """Text visual formatting properties including font, justification, and visibility"""


T = TypeVar("T", bound=Property)

TD = TypeVar("TD")


class PropertyList(Generic[T], list[T]):
    """Stores properties as list, offering convenient by-name access"""

    def __init__(self, inner_type: type[T]) -> None:
        super().__init__()
        self.__inner_type = inner_type

    @property
    def ref(self) -> T:
        """Returns 'Reference' property. Raises StopIteration if not found."""
        return next(p for p in self if p.name == "Reference")

    @overload
    def get(self, name: str) -> T | None:
        """Returns the first property with the given name, or default if not found."""
        ...

    @overload
    def get(self, name: str, default: TD) -> TD | T:
        """Returns the first property with the given name, or default if not found."""
        ...

    def get(self, name: str, default: TD | None = None) -> T | TD | None:
        """Returns the first property with the given name, or default if not found."""
        return next((prop for prop in self if prop.name == name), default)

    @overload
    def get_value(self, name: str) -> str | None:
        """Returns the value of the property with the given name, or default if not found."""
        ...

    @overload
    def get_value(self, name: str, default: str) -> str:
        """Returns the value of the property with the given name, or default if not found."""
        ...

    def get_value(self, name: str, default: str | None = None) -> str | None:
        """Returns the value of the property with the given name, or default if not found."""
        prop = next((prop for prop in self if prop.name == name), None)
        return prop.value if prop else default

    def set(self, name: str, value: str, **kwargs: Any) -> None:  # noqa: ANN401
        """Set the value of the property with the given name (create if necessary)."""
        prop = self.get(name)
        if prop is not None:
            prop.value = value
            return
        self.append(self.__inner_type(name=name, value=value, **kwargs))

    def pop(self, name: str) -> T | None:  # type: ignore  # ty:ignore[invalid-method-override]
        """Removes and returns the first property with the given name, or None if not found."""
        idx = next((idx for idx, prop in enumerate(self) if prop.name == name), None)
        return list.pop(self, idx) if idx else None


class LibEntry(AutoSerde):
    """Library entry definition for KiCad symbol libraries.
    Represents a single library entry with name, type, URI, options, and description."""

    name: str = F()
    """Library name"""
    type: str = F("KiCad")
    """Library type identifier"""
    uri: str = F()
    """URI/path of the library"""
    options: str = F()
    """Library options string"""
    description: str = F(name="descr")
    """Library description"""
    disabled: bool = F(flag=True)
    """Corresponds to `Enable`/`Active` checkbox in KiCad GUI"""
    hidden: bool = F(flag=True)
    """Corresponds to `Visible`/`Show` checkbox in KiCad GUI"""


class LibraryTable(AutoSerdeFile):
    """Library table, defining version and list of available libraries."""

    _askiff_key: ClassVar[str] = "lib_table"

    version: int = Version.DEFAULT.lib_table
    """Library table file format version number."""

    lib: list[LibEntry] = F(flatten=True)
    """List of libraries referenced in the table."""


class DataBlock(bytearray):
    """Represents binary data in KiCad files, serialized as base64-encoded strings"""

    @classmethod
    def deserialize(cls, sexp: GeneralizedSexpr) -> DataBlock:
        """Converts sexpr data block into binary data.
        Strips pipe ('|') characters from first and last chunks before decoding.

        Args:
            sexp: List of base64-encoded strings.
        """
        ret = DataBlock()
        if not isinstance(sexp[0], str):
            raise TypeError("Elements of data block are expected to be strings")
        ret.extend(base64.b64decode(sexp[0].lstrip("|")))
        for s in sexp[1:-1]:
            if not isinstance(s, str):
                raise TypeError("Elements of data block are expected to be strings")
            ret.extend(base64.b64decode(s))
        if not isinstance(sexp[-1], str):
            raise TypeError("Elements of data block are expected to be strings")
        ret.extend(base64.b64decode(sexp[-1].rstrip("|")))
        return ret

    def serialize(self) -> GeneralizedSexpr:
        """Converts binary data into KiCad sexpr format with pipe-delimited base64 chunks"""
        b64 = base64.b64encode(self).decode("ascii")
        chunks = textwrap.wrap(b64, DEFAULT_DATA_CHUNK_LENGTH)
        if not chunks:
            return ["||"]
        chunks[0] = "|" + chunks[0]
        chunks[-1] = chunks[-1] + "|"
        return chunks

    @classmethod
    def deserialize_quoted(cls, sexp: GeneralizedSexpr) -> DataBlock:
        """Deserializes base64-encoded strings (quoted KiCad flavour) into a DataBlock instance.

        Args:
            sexp: List of base64-encoded strings.
        """
        ret = DataBlock()
        for s in sexp:
            if not isinstance(s, str):
                raise TypeError("Elements of data block are expected to be strings")
            ret.extend(base64.b64decode(s))
        return ret

    def serialize_quoted(self) -> GeneralizedSexpr:
        """Serializes byte data into chunked base64-encoded quoted strings"""
        b64 = base64.b64encode(self).decode("ascii")
        chunks = textwrap.wrap(b64, DEFAULT_DATA_CHUNK_LENGTH)
        return [Qstr(chunk) for chunk in chunks]


class EmbeddedFileType(str, AutoSerdeEnum):
    """Enumeration of supported embedded file types.
    Used to specify the kind of file embedded in a KiCad object, such as fonts, 3D models, or other resources.
    """

    FONT = "font"
    MODEL = "model"
    OTHER = "other"


class EmbeddedFile(AutoSerde):
    """Stores an embedded file within a KiCad file"""

    _askiff_key: ClassVar[str] = "file"
    name: str = F()
    """File name of the embedded object"""
    type: EmbeddedFileType = F(EmbeddedFileType.OTHER)
    """Type of embedded file."""
    data: DataBlock | None = None
    """Embedded file contents as bytes."""
    checksum: str = F()
    """Checksum of the embedded file contents."""


class Group(AutoSerde):
    """Group represents a named collection of items, used to organize and manage related components or elements"""

    name: str = F(positional=True)
    """Group name identifier"""
    locked: bool | None = None
    """Whether the group is locked."""
    uuid: Uuid = F()
    """Unique identifier for the group object."""
    members: list[Uuid] = F()
    """Items contained in the group"""


class ComponentClass(AutoSerde):
    """Represents a component class definition.
    Used to group components by their functional or logical class, enabling organization and filtering of components."""

    _askiff_key: ClassVar[str] = "class"
    name: str = F(positional=True)
    """Component class name"""


class PaperSize(Qstr, AutoSerdeEnum):
    """Represents available paper sizes."""

    A3 = "A3"
    A4 = "A4"


class Paper(AutoSerde, positional=True):  # type:ignore
    """Paper represents the paper/canvas on which schematic/board may be drawn"""

    size: PaperSize = F(PaperSize.A3)
    """Paper size setting"""


class TitleBlockComment(AutoSerde, positional=True):  # type:ignore
    """Represents a comment entry in a KiCad title block, with a comment number and content.
    Used to store additional text to be used in project frame/tittle block."""

    number: int = 1
    """Comment entry number in the title block."""
    content: str = ""
    """Comment text content in the title block."""


class TitleBlock(AutoSerde):
    """Title block for a schematic/pcb, containing basic metadata to be shown along design."""

    title: str | None = None
    """Document title."""
    date: str | None = None
    """Creation or modification date."""
    rev: str | None = None
    """Revision identifier."""
    company: str | None = None
    """Organization or company name."""
    comment: list[TitleBlockComment] = F(flatten=True)
    """Additional user defined texts"""

    def __bool__(self) -> bool:
        return any((self.title, self.date, self.rev, self.company, self.comment))


class PinType(Qstr, AutoSerdeEnum):
    """Represents the type/function of a pin in a KiCad schematic or footprint"""

    PASSIVE = "passive"
    PWR_IN = "power_in"
    PWR_OUT = "power_out"
    INPUT = "input"
    OUTPUT = "output"
    BIDIRECTIONAL = "bidirectional"
    OPEN_COLLECTOR = "open_collector"
    OPEN_EMITTER = "open_emmiter"
    FREE = "free"
    UNSPECIFIED = "unspecified"
    NO_CONNECT = "no_connect"
    TRI_STATE = "tri_state"


class PinTypePCB(AutoSerde):
    """Represents the type/function and connection state of a pin in a PCB"""

    base: PinType = F(PinType.UNSPECIFIED)
    """Base pin type for the PCB pin."""
    connected: bool = False
    """Whether the pin is connected to a net (on schematic)"""

    def serialize(self) -> GeneralizedSexpr:
        """Serializes the pin type,
        appending "+no_connect" to the base value if the pin is not connected and is not already a no-connect pin."""
        return (
            self.base.value
            if self.connected or self.base == PinType.NO_CONNECT
            else Qstr(self.base.value + "+no_connect"),
        )

    @classmethod
    def deserialize(cls, sexp: GeneralizedSexpr) -> PinTypePCB:
        """Deserializes a KiCad sexpr representation of a pin type into a PinTypePCB object."""
        s = sexp[0]
        if not isinstance(s, str):
            raise TypeError("PinType is expected to be a string")
        connected = True
        if "no_connect" in s:
            connected = False
            s = s.removesuffix("+no_connect")
        return PinTypePCB(PinType(s), connected)


########################Base Shapes########################


class BaseShape(AutoSerde):
    """BaseShape represents an abstract base class for geometric shapes in KiCad board and schematic files.
    Defines interface for computing extrema points and converting coordinates to global space."""

    @abstractmethod
    def extrema_points(self) -> Sequence[Position]:
        """Boundary points of the shape."""
        ...

    def to_global(self, ref_pos: Position) -> None:
        """Changes object coordinates in place to global ones using `ref_pos` as current origin."""
        ...


class BasePoly(BaseShape):
    """BasePoly represents a polygonal shape defined by a sequence of points"""

    _askiff_key: ClassVar[str] = "polygon"
    pts: list[Position] = F()
    """Points defining the polygon shape"""

    def extrema_points(self) -> Sequence[Position]:
        """Returns the sequence of points defining the polygon's extrema"""
        return self.pts

    def to_global(self, ref_pos: Position) -> None:
        """Changes object coordinates in place to global ones using `ref_pos` as current origin."""
        self.pts = [p.to_global(ref_pos) for p in self.pts]


class BaseBezier(BaseShape):
    """BaseBezier represents a cubic Bézier curve"""

    _pts: list[Position] = F(name="pts")

    start: Position = F(skip=True)
    """Starting point of the Bézier curve."""

    start_handle: Position = F(skip=True)
    """End point for curve control handle starting in start point"""

    end_handle: Position = F(skip=True)
    """End point for curve control handle starting in end point"""

    end: Position = F(skip=True)
    """Endpoint of the Bézier curve."""

    def _askiff_post_deser(self) -> None:
        """Post-deser handler that unpacks the serialized points into named attributes"""
        self.start, self.start_handle, self.end_handle, self.end = self._pts

    def _askiff_pre_ser(self) -> BaseBezier:
        """Prepare curve for serialization by constructing the point list from start, handles, and end points."""
        self._pts = [self.start, self.start_handle, self.end_handle, self.end]
        return self

    def extrema_points(self) -> Sequence[Position]:
        """Returns the list of extremal points on the Bézier curve,
        That is start and end points, local maxima or minima in either x or y direction."""
        start, start_handle, end_handle, end = self.start, self.start_handle, self.end_handle, self.end

        def solve_quadratic(a: float, b: float, c: float) -> set[float]:
            # Solve a*t^2 + b*t + c = 0
            if abs(a) < 1e-12:  # Degenerate to linear
                if abs(b) < 1e-12:
                    return set()  # No solution
                t = -c / b
                return {t}
            delta = b * b - 4 * a * c
            delta_sqrt = sqrt(delta)
            t1 = (-b + delta_sqrt) / (2 * a)
            t2 = (-b - delta_sqrt) / (2 * a)
            return {t for t in (t1, t2)}

        def bezier(t: float, start: Position, start_handle: Position, end_handle: Position, end: Position) -> Position:
            # Evaluate cubic Bézier at t (in range 0 to 1, where 0 is the beginning, 1 is end)
            mt = 1 - t
            x = mt**3 * start.x + 3 * mt**2 * t * start_handle.x + 3 * mt * t**2 * end_handle.x + t**3 * end.x
            y = mt**3 * start.y + 3 * mt**2 * t * start_handle.y + 3 * mt * t**2 * end_handle.y + t**3 * end.y
            return Position(x, y)

        # Coefficients for dx/dt = 0
        ax = -3 * start.x + 9 * start_handle.x - 9 * end_handle.x + 3 * end.x
        bx = 6 * start.x - 12 * start_handle.x + 6 * end_handle.x
        cx = -3 * start.x + 3 * start_handle.x

        # Coefficients for dy/dt = 0
        ay = -3 * start.y + 9 * start_handle.y - 9 * end_handle.y + 3 * end.y
        by = 6 * start.y - 12 * start_handle.y + 6 * end_handle.y
        cy = -3 * start.y + 3 * start_handle.y

        # Remove duplicates, Always include endpoints
        ts = sorted({0.0, 1.0} | solve_quadratic(ax, bx, cx) | solve_quadratic(ay, by, cy))

        return [bezier(t, start, start_handle, end_handle, end) for t in ts if 0.0 <= t <= 1.0]

    def to_global(self, ref_pos: Position) -> None:
        """Changes object coordinates in place to global ones using `ref_pos` as current origin."""
        self.start = self.start.to_global(ref_pos)
        self.start_handle = self.start_handle.to_global(ref_pos)
        self.end_handle = self.end_handle.to_global(ref_pos)
        self.end = self.end.to_global(ref_pos)


class BaseCircle(BaseShape):
    """BaseCircle represents a circle defined by its center and a point on its circumference"""

    center: Position = F()
    """Center position of the circle."""
    end: Position = F()
    """Point on the circle's circumference."""

    def extrema_points(self) -> Sequence[Position]:
        """Returns the four extreme points of the circle: right, top, left, and bottom.
        Calculated from center and radius derived from the distance between center and end positions."""
        center = self.center
        r = center.distance(self.end)

        return (
            Position(center.x + r, center.y),
            Position(center.x, center.y + r),
            Position(center.x - r, center.y),
            Position(center.x, center.y - r),
        )

    def to_global(self, ref_pos: Position) -> None:
        """Changes object coordinates in place to global ones using `ref_pos` as current origin."""
        self.center = self.center.to_global(ref_pos)
        self.end = self.end.to_global(ref_pos)


class BaseLine(BaseShape):
    """BaseLine represents a line segment defined by start and end points in a KiCad file."""

    start: Position = F()
    """Starting point of the line segment."""
    end: Position = F()
    """End point of the line segment."""

    def extrema_points(self) -> Sequence[Position]:
        """Returns the start and end points of the line as a sequence."""
        return (self.start, self.end)

    def to_global(self, ref_pos: Position) -> None:
        """Changes object coordinates in place to global ones using `ref_pos` as current origin."""
        self.start = self.start.to_global(ref_pos)
        self.end = self.end.to_global(ref_pos)


class BaseArc(BaseShape):
    """BaseArc represents an arc segment defined by start, mid, and end points"""

    _askiff_key: ClassVar[str] = "arc"
    start: Position = F()
    """Starting point of the arc segment."""
    mid: Position = F()
    """Middle point defining the arc's curvature."""
    end: Position = F()
    """End point of the arc segment."""

    def calculate_circle(self) -> BaseCircle:
        """Calculates center point and radius of the circle, the arc belongs to"""
        start, mid, end = self.start, self.mid, self.end
        # Squared distance of triangle points to origin
        a = pow(start.x, 2) + pow(start.y, 2)
        b = pow(mid.x, 2) + pow(mid.y, 2)
        c = pow(end.x, 2) + pow(end.y, 2)
        # Determinant
        det = (mid.x - start.x) * (end.y - start.y) - (end.x - start.x) * (mid.y - start.y)
        # Circle center calculated based on circumcircle equations - perpendicular bisectors of a triangle
        # sides are intersecting in center point of the circle circumscribed on that triangle.
        circle_x = -((mid.y - start.y) * (c - a) - (end.y - start.y) * (b - a)) / (2 * det)
        circle_y = -((end.x - start.x) * (b - a) - (mid.x - start.x) * (c - a)) / (2 * det)
        return BaseCircle(Position(circle_x, circle_y), end)

    def extrema_points(self) -> Sequence[Position]:
        """Calculates the extrema points of the arc
        That is start, mid and end points & any additional extrema from the enclosing circle that belongs to arc."""
        start, mid, end = self.start, self.mid, self.end
        circle = self.calculate_circle()
        center = circle.center

        # Calculates angles for arc defining points
        start_angle = center.vector_angle(start)
        end_angle = center.vector_angle(end)

        def in_range(angle: float, start_angle: float, end_angle: float) -> bool:
            """Verifies if angle is in range [start_angle, end_angle] in cartesian system"""
            if start_angle <= end_angle:
                return start_angle <= angle <= end_angle
            return angle >= start_angle or angle <= end_angle

        valid_circle_extrema = (
            ext for ext in circle.extrema_points() if in_range(center.vector_angle(ext), start_angle, end_angle)
        )

        return (start, mid, end, *valid_circle_extrema)

    def to_global(self, ref_pos: Position) -> None:
        """Changes object coordinates in place to global ones using `ref_pos` as current origin."""
        self.start = self.start.to_global(ref_pos)
        self.mid = self.mid.to_global(ref_pos)
        self.end = self.end.to_global(ref_pos)


class BaseRect(BaseShape):
    """BaseRect represents a rectangle defined by two diagonal corners, start and end."""

    start: Position = F()
    """Starting corner position of the rectangle."""
    end: Position = F()
    """Ending corner position of the rectangle."""

    def extrema_points(self) -> Sequence[Position]:
        """Returns the four corner points of the rectangle in order: top-right, start, bottom-left, end."""
        return (Position(self.end.x, self.start.y), self.start, Position(self.start.x, self.end.y), self.end)

    def to_global(self, ref_pos: Position) -> None:
        """Changes object coordinates in place to global ones using `ref_pos` as current origin."""
        self.start = self.start.to_global(ref_pos)
        self.end = self.end.to_global(ref_pos)


class BBox(BaseRect):
    """Bounding box defined by two diagonal corners. Provides factory methods to construct a bounding box from shapes"""

    @classmethod
    def from_shapes(cls, shapes: Iterable[BaseShape]) -> BBox | None:
        """Creates a bounding box from an iterable of shapes

        Args:
            shapes: An iterable of BaseShape objects.

        Returns:
            A BBox instance representing the minimal bounding box enclosing all input shapes,
            or None if the input is empty or contains no extrema points.

        Example:
            >>> from askiff.gritems import GrRectPCB
            >>> from askiff.common import Position, BBox
            >>> rect = GrRectPCB(start=Position(0, 0), end=Position(10, 10))
            >>> bbox = BBox.from_shapes([rect])
            >>> print((bbox.start.x, bbox.start.y), (bbox.end.x, bbox.end.y))
            (0, 0) (10, 10)
        """
        extrema_points = cls.extrema_from_shapes(shapes)
        if not extrema_points:
            return None
        xs, ys = zip(*((p.x, p.y) for p in extrema_points), strict=True)
        return BBox(Position(min(xs), min(ys)), Position(max(xs), max(ys)))

    @classmethod
    def extrema_from_shapes(cls, shapes: Iterable[BaseShape]) -> Sequence[Position]:
        """Computes all extrema points from an iterable of shapes.

        Args:
            shapes: An iterable of BaseShape objects.

        Returns:
            A sequence of Position objects representing the extreme coordinates.

        Example:
            >>> from askiff.gritems import GrCircleSym
            >>> from askiff.common import Position, BBox
            >>> circle = GrCircleSym(center=Position(0, 0), radius=5)
            >>> extrema = BBox.extrema_from_shapes([circle])
            >>> print(extrema)
            [Position(x=5.0, y=0, angle=None), Position(x=0, y=5.0, angle=None), Position(x=-5.0, y=0, angle=None), Position(x=0, y=-5.0, angle=None)]
        """  # noqa: E501
        return [p for sh in shapes for p in sh.extrema_points()]
