from __future__ import annotations

import base64
import textwrap
import uuid
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar, cast

from askiff.auto_serde import AutoSerde, AutoSerdeEnum, F
from askiff.const import Version
from askiff.sexpr import GeneralizedSexpr, Qstr

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
        extra = self._AutoSerde__extra  # ty:ignore[unresolved-attribute]
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
        ret = Position(float(x), float(y))
        if extra:
            try:
                ret.angle = float(extra[0])
                extra = extra[1:]
            except ValueError:
                pass
            ret._AutoSerde__extra = extra  # ty:ignore[unresolved-attribute]
        return ret


class LibId(AutoSerde):
    library: str | None = None
    """The optional `library` token defines which library this footprint/symbol belongs to"""

    name: str = ""
    """The `name` token defines the actual name of the footprint/symbol"""

    def serialize(self) -> GeneralizedSexpr:
        if self.library:
            return Qstr(f"{self.library}:{self.name}")
        return Qstr(self.name)

    @classmethod
    def deserialize(cls, sexp: GeneralizedSexpr) -> LibId:
        assert isinstance(sexp, str)
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
    A: float = 0


class Size(AutoSerde, positional=True):  # type: ignore
    height: float = 1
    width: float = 1


class Font(AutoSerde):
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


class Justify(AutoSerde):
    horizontal: JustifyH = F(JustifyH.CENTER, positional=True)
    vertical: JustifyV = F(JustifyV.CENTER, positional=True)
    mirror: bool = F(flag=True, bare=True)

    @classmethod
    def deserialize(cls, sexp: GeneralizedSexpr) -> Justify:
        ret = cls()
        if "mirror" in sexp:
            ret.mirror = True
        for x in [JustifyV.TOP, JustifyV.BOTTOM]:
            if x.value in sexp:  # type: ignore
                ret.vertical = x  # type: ignore
        for x in [JustifyH.LEFT, JustifyH.RIGHT]:
            if x.value in sexp:  # type: ignore
                ret.horizontal = x  # type: ignore
        return ret


class Effects(AutoSerde):
    font: Font = F()
    justify: Justify | None = F()
    hide: bool | None = None
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

    name: str = F(positional=True)
    """Name of the property"""

    value: str = F(positional=True)
    """Value of the property"""

    hide: bool | None = None
    """[Deprecated] Defines if the text is hidden"""

    effects: Effects | None = None
    """Defines how text looks like, eg. font"""

    def _askiff_post_deser(self) -> None:
        if self.hide is not None:
            # this looks like serialization bug in some K9 versions
            self.effects = self.effects or Effects()
            self.effects.hide = self.hide
            self.hide = None


T = TypeVar("T", bound=Property)


class PropertyList(Generic[T], list[T]):
    """Stores properties as list, offering convenient by-name access"""

    @property
    def ref(self) -> T:
        return next(p for p in self if p.name == "Reference")

    def get(self, name: str) -> T | None:
        return next((prop for prop in self if prop.name == name), None)

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
        ret.extend(base64.b64decode(sexp[0].lstrip("|")))
        for s in sexp[1:-1]:
            ret.extend(base64.b64decode(s))
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


class TitleBlock(AutoSerde):
    pass


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
    TRISTATE = "tristate"


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


class BasePoly(AutoSerde):
    _askiff_key: ClassVar[str] = "polygon"
    pts: list[Position] = F()


class BaseCircle(AutoSerde):
    center: Position = F()
    end: Position = F()


class BaseLine(AutoSerde):
    start: Position = F()
    end: Position = F()


class BaseArc(AutoSerde):
    _askiff_key: ClassVar[str] = "arc"
    start: Position = F()
    mid: Position = F()
    end: Position = F()
