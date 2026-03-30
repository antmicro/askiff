from __future__ import annotations

import base64
import textwrap
import uuid
from abc import abstractmethod
from collections.abc import Iterable, Sequence
from math import atan2, cos, hypot, pi, radians, sin, sqrt
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar, cast, overload

from askiff._auto_serde import AutoSerde, AutoSerdeEnum, F
from askiff._sexpr import GeneralizedSexpr, Qstr
from askiff.const import Version

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore

DEFAULT_DATA_CHUNK_LENGTH = 76


class Position(AutoSerde):
    _askiff_key: ClassVar[str] = "xy"
    x: float = F(positional=True)
    y: float = F(positional=True)
    angle: float | None = F(positional=True, precision=8)

    def serialize(self) -> GeneralizedSexpr:
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
        return hypot(self.x - to.x, self.y - to.y)

    def vector_angle(self, to: Position) -> float:
        """Finds normalized angle in radians between selected point and reference point"""
        angle = atan2(to.y - self.y, to.x - self.x)
        angle %= 2 * pi
        return angle

    def to_global(self, ref_pos: Position) -> Position:
        angle = radians(-ref_pos.angle if ref_pos.angle is not None else 0)
        sina, cosa = sin(angle), cos(angle)

        return Position(ref_pos.x + self.x * cosa - self.y * sina, ref_pos.y + self.x * sina + self.y * cosa)


class LibId(AutoSerde):
    library: str | None = None
    """The optional `library` token defines which library this footprint/symbol belongs to"""

    name: str = ""
    """The `name` token defines the actual name of the footprint/symbol"""

    def serialize(self) -> GeneralizedSexpr:
        if self.library:
            return (Qstr(f"{self.library}:{self.name}"),)
        return (Qstr(self.name),)

    @classmethod
    def deserialize(cls, sexp: GeneralizedSexpr) -> LibId:
        sexp = sexp if isinstance(sexp, str) else sexp[0]
        if not isinstance(sexp, str):
            raise TypeError("Library ID expected to be a string")
        spl = sexp.partition(":")
        return LibId(spl[0], spl[2]) if spl[1] else LibId(None, spl[0])


class Uuid(str):
    """Wrapper that stores kicad objects uuid (globally unique identifier)

    Note: Auto generates new Uuid on copy!"""

    def __new__(cls, value: str | None = None) -> Uuid:
        if value is None:
            value = str(uuid.uuid4())
        return cast(Uuid, value)

    # Override copy methods to ensure that when coping kicad objects, no duplicate uuid will be produced
    def __copy__(self) -> Uuid:
        return Uuid()

    def __deepcopy__(self, _) -> Uuid:  # type: ignore # noqa: ANN001
        return Uuid()


class Color(AutoSerde, positional=True):  # type: ignore
    R: int = 0
    G: int = 0
    B: int = 0
    A: float = F(precision=10)


class Size(AutoSerde, positional=True):  # type: ignore
    height: float = 1
    width: float = 1


class Font(AutoSerde):
    _askiff_key: ClassVar[str] = "font"
    face: str | None = None
    size: Size = F()
    thickness: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    line_spacing: bool | None = None
    color: Color | None = None


class JustifyV(str, AutoSerdeEnum):
    TOP = "top"
    CENTER = ""
    BOTTOM = "bottom"


class JustifyH(str, AutoSerdeEnum):
    LEFT = "left"
    CENTER = ""
    RIGHT = "right"


class Justify(AutoSerde, flag=True, bare=True):  # type: ignore
    horizontal: JustifyH = F(JustifyH.CENTER)
    vertical: JustifyV = F(JustifyV.CENTER)
    mirror: bool = False


class Effects(AutoSerde):
    font: Font = F()
    justify: Justify | None = F()
    hide: bool | None = F(skip=True).version(Version.K9.sch, skip=False)
    """Use `Property` level setting"""
    href: str | None = None


class StrokeStyle(str, AutoSerdeEnum):
    DEFAULT = "default"
    DOT = "dot"
    DASH = "dash"
    DASH_DOT = "dash_dot"
    DASH_DOT_DOT = "dash_dot_dot"
    SOLID = "solid"


class Stroke(AutoSerde):
    width: float = F()
    style: StrokeStyle = F(StrokeStyle.DEFAULT, name="type")
    color: Color | None = None


class Property(AutoSerde):
    """Stores object metadata such as Reference, Value, Datasheet, .."""

    _askiff_key: ClassVar[str] = "property"

    name: str = F(positional=True)
    """Name of the property"""

    value: str = F(positional=True)
    """Value of the property"""

    position: Position = F(name="at")
    """Property text position"""

    hide: bool | None = None
    """Defines if the text is hidden"""

    effects: Effects | None = None
    """Defines how text looks like, eg. font"""


T = TypeVar("T", bound=Property)

TD = TypeVar("TD")


class PropertyList(Generic[T], list[T]):
    """Stores properties as list, offering convenient by-name access"""

    @property
    def ref(self) -> T:
        return next(p for p in self if p.name == "Reference")

    @overload
    def get(self, name: str) -> T | None: ...

    @overload
    def get(self, name: str, default: TD) -> TD | T: ...

    def get(self, name: str, default: TD | None = None) -> T | TD | None:
        return next((prop for prop in self if prop.name == name), default)

    @overload
    def get_value(self, name: str) -> str | None: ...

    @overload
    def get_value(self, name: str, default: str) -> str: ...

    def get_value(self, name: str, default: str | None = None) -> str | None:
        prop = next((prop for prop in self if prop.name == name), None)
        return prop.value if prop else default

    def pop(self, name: str) -> T | None:  # type: ignore  # ty:ignore[invalid-method-override]
        idx = next((idx for idx, prop in enumerate(self) if prop.name == name), None)
        return list.pop(self, idx) if idx else None


class LibEntry(AutoSerde):
    name: str = F()
    type: str = F("KiCad")
    uri: str = F()
    options: str = F()
    description: str = F(name="descr")


class LibTable(AutoSerde):
    version: int = Version.DEFAULT.lib_table
    """Defines the file format version"""

    lib: list[LibEntry] = F(flatten=True)
    """List of actual libraries"""


class DataBlock(bytearray):
    @classmethod
    def deserialize(cls, sexp: GeneralizedSexpr) -> DataBlock:
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
        b64 = base64.b64encode(self).decode("ascii")
        chunks = textwrap.wrap(b64, DEFAULT_DATA_CHUNK_LENGTH)
        if not chunks:
            return ["||"]
        chunks[0] = "|" + chunks[0]
        chunks[-1] = chunks[-1] + "|"
        return chunks


class DataBlockQuoted(bytearray):
    @classmethod
    def deserialize(cls, sexp: GeneralizedSexpr) -> DataBlockQuoted:
        ret = DataBlockQuoted()
        for s in sexp:
            if not isinstance(s, str):
                raise TypeError("Elements of data block are expected to be strings")
            ret.extend(base64.b64decode(s))
        return ret

    def serialize(self) -> GeneralizedSexpr:
        b64 = base64.b64encode(self).decode("ascii")
        chunks = textwrap.wrap(b64, DEFAULT_DATA_CHUNK_LENGTH)
        return [Qstr(chunk) for chunk in chunks]


class EmbeddedFileType(str, AutoSerdeEnum):
    FONT = "font"
    MODEL = "model"
    OTHER = "other"


class EmbeddedFile(AutoSerde):
    _askiff_key: ClassVar[str] = "file"
    name: str = F()
    type: EmbeddedFileType = F(EmbeddedFileType.OTHER)
    data: DataBlock | None = None
    checksum: str = F()


class Group(AutoSerde):
    name: str = F(positional=True)
    locked: bool | None = None
    uuid: Uuid = F()
    members: list[Uuid] = F()


class ComponentClass(AutoSerde):
    _askiff_key: ClassVar[str] = "class"
    name: str = F(positional=True)


class PaperSize(Qstr, AutoSerdeEnum):
    A3 = "A3"
    A4 = "A4"


class Paper(AutoSerde, positional=True):  # type:ignore
    size: PaperSize = F(PaperSize.A3)


class TitleBlockComment(AutoSerde, positional=True):  # type:ignore
    number: int = 1
    content: str = ""


class TitleBlock(AutoSerde):
    title: str | None = None
    date: str | None = None
    rev: str | None = None
    company: str | None = None
    comment: list[TitleBlockComment] = F(flatten=True)

    def __bool__(self) -> bool:
        return any((self.title, self.date, self.rev, self.company, self.comment))


class PinType(Qstr, AutoSerdeEnum):
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
    base: PinType = F(PinType.UNSPECIFIED)
    connected: bool = False

    def serialize(self) -> GeneralizedSexpr:
        return (
            self.base.value
            if self.connected or self.base == PinType.NO_CONNECT
            else Qstr(self.base.value + "+no_connect"),
        )

    @classmethod
    def deserialize(cls, sexp: GeneralizedSexpr) -> PinTypePCB:
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
    @abstractmethod
    def extrema_points(self) -> Sequence[Position]:
        """Get extrema points of an object"""
        ...

    def to_global(self, ref_pos: Position) -> None:
        """Change object coordinates in place to global ones using `ref_pos` as current origin"""
        ...


class BasePoly(BaseShape):
    _askiff_key: ClassVar[str] = "polygon"
    pts: list[Position] = F()

    def extrema_points(self) -> Sequence[Position]:
        return self.pts

    def to_global(self, ref_pos: Position) -> None:
        """Change object coordinates in place to global ones using `ref_pos` as current origin"""
        self.pts = [p.to_global(ref_pos) for p in self.pts]


class BaseBezier(BaseShape):
    _pts: list[Position] = F(name="pts")

    start: Position = F(skip=True)

    start_handle: Position = F(skip=True)
    """End point for curve control handle starting in `start` point"""

    end_handle: Position = F(skip=True)
    """End point for curve control handle starting in `end` point"""

    end: Position = F(skip=True)

    def _askiff_post_deser(self) -> None:
        self.start, self.start_handle, self.end_handle, self.end = self._pts

    def _askiff_pre_ser(self) -> BaseBezier:
        self._pts = [self.start, self.start_handle, self.end_handle, self.end]
        return self

    def extrema_points(self) -> Sequence[Position]:
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
        """Change object coordinates in place to global ones using `ref_pos` as current origin"""
        self.start = self.start.to_global(ref_pos)
        self.start_handle = self.start_handle.to_global(ref_pos)
        self.end_handle = self.end_handle.to_global(ref_pos)
        self.end = self.end.to_global(ref_pos)


class BaseCircle(BaseShape):
    center: Position = F()
    end: Position = F()

    def extrema_points(self) -> Sequence[Position]:
        center = self.center
        r = center.distance(self.end)

        return (
            Position(center.x + r, center.y),
            Position(center.x, center.y + r),
            Position(center.x - r, center.y),
            Position(center.x, center.y - r),
        )

    def to_global(self, ref_pos: Position) -> None:
        """Change object coordinates in place to global ones using `ref_pos` as current origin"""
        self.center = self.center.to_global(ref_pos)
        self.end = self.end.to_global(ref_pos)


class BaseLine(BaseShape):
    start: Position = F()
    end: Position = F()

    def extrema_points(self) -> Sequence[Position]:
        return (self.start, self.end)

    def to_global(self, ref_pos: Position) -> None:
        """Change object coordinates in place to global ones using `ref_pos` as current origin"""
        self.start = self.start.to_global(ref_pos)
        self.end = self.end.to_global(ref_pos)


class BaseArc(BaseShape):
    _askiff_key: ClassVar[str] = "arc"
    start: Position = F()
    mid: Position = F()
    end: Position = F()

    def calculate_circle(self) -> BaseCircle:
        """Calculates center point and radius of the circle defined with an arc"""
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
        """Calculates arc extrema"""
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
        """Change object coordinates in place to global ones using `ref_pos` as current origin"""
        self.start = self.start.to_global(ref_pos)
        self.mid = self.mid.to_global(ref_pos)
        self.end = self.end.to_global(ref_pos)


class BaseRect(BaseShape):
    start: Position = F()
    end: Position = F()

    def extrema_points(self) -> Sequence[Position]:
        return (Position(self.end.x, self.start.y), self.start, Position(self.start.x, self.end.y), self.end)

    def to_global(self, ref_pos: Position) -> None:
        """Change object coordinates in place to global ones using `ref_pos` as current origin"""
        self.start = self.start.to_global(ref_pos)
        self.end = self.end.to_global(ref_pos)


class BBox(BaseRect):
    @classmethod
    def from_shapes(cls, shapes: Iterable[BaseShape]) -> BBox | None:
        extrema_points = cls.extrema_from_shapes(shapes)
        if not extrema_points:
            return None
        xs, ys = zip(*((p.x, p.y) for p in extrema_points), strict=True)
        return BBox(Position(min(xs), min(ys)), Position(max(xs), max(ys)))

    @classmethod
    def extrema_from_shapes(cls, shapes: Iterable[BaseShape]) -> Sequence[Position]:
        return [p for sh in shapes for p in sh.extrema_points()]
