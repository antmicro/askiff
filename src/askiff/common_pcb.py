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
    """Layer function types used in PCB design. Represents the functional purpose of a PCB layer."""
    SIGNAL = "signal"
    JUMPER = "jumper"
    POWER = "power"
    MIXED = "mixed"
    AUX = "user"
    AUX_F = "front"
    AUX_B = "back"


class BaseLayer:
    """`BaseLayer` abstracts layer keywords used in KiCad files.

    Typical usage: Library users should use pre-instantiated values from :class:`askiff.common_pcb.Layer`
    
    Inheritance is used to differentiate between layer types, eg. all cooper layers are inherited from LayerCopper.
    During deserialization there is automatic down casting to most specific subclass

    Examples:
        # Check if layer is of specific type:
        >>> isinstance(Layer.CU_F, LayerCopper)
        True
        >>> Layer.CU_F in LayerCopper.all
        True
        >>> isinstance(Layer.CU_F, LayerCopperOuter)
        True
        >>> isinstance(Layer.CU_F, LayerCopperInner)
        False

        # Iterate layers of specific type:
        >>> for layer in LayerCopperOuter.all: print(type(layer), layer)
        <class 'askiff.common_pcb.LayerCopperOuter'> B.Cu
        <class 'askiff.common_pcb.LayerCopperOuter'> F.Cu
    """
    _value: str
    _order_id: int
    name_map: ClassVar[dict[str, BaseLayer]]
    """Mapping of names (serialization keywords) to layer instances for efficient lookup."""
    all: ClassVar[LayerSet[BaseLayer]]
    """All registered layers of specific type."""

    class __PrivateGuard(int):
        """Private sentinel type for validating BaseLayer constructor calls.
        Prevents external code from directly instantiating BaseLayer subclasses."""
        pass

    def order_id(self) -> int:
        """Returns the layer identifier, used for ordering during serialization."""
        return self._order_id

    def validate_function(self, function: LayerFunction | None) -> LayerFunction:
        """Validates if function matches layer type and returns a LayerFunction, defaulting to AUX if None."""
        return function or LayerFunction.AUX

    def serialize(self) -> GeneralizedSexpr:
        """Serializes the layer's value into a generalized sexpr tuple."""
        return (Qstr(self._value),)

    def __init_subclass__(cls) -> None:
        cls.name_map = {}
        cls.all = LayerSet()
        if not hasattr(BaseLayer, "all"):
            BaseLayer.name_map = {}
            BaseLayer.all = LayerSet()

    def __init__(self, value: str, order_id: int, _guard: __PrivateGuard) -> None:
        """Library users should use pre-instantiated values from :class:`askiff.common_pcb.Layer`
        
        # Dev notes:
        * Initialize a BaseLayer instance with a unique value and order ID.
        * _guard uses private type __PrivateGuard to prevent instantiation by user
        """
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
        """Deserializes a generalized sexpr into a Layer instance, attempting a downcast to the appropriate subclass."""
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
    """A set-like container for managing layers with special handling for copper and mask layer groups."""

    __askiff_alias: ClassVar[set[str]] = {"layer", "layers"}
    """Alias names for layer identification during deserialization"""
    _layers: set[TL] = F(positional=True)
    _knockout: bool = F(name="knockout", flag=True, bare=True)
    """Internal use only, use text level setting.
    
    KiCad stores text knockout token inside layer set, defined here so that AutoSerde can handle it"""

    def __init__(self, *args: TL) -> None:
        """Initialize a LayerSet with optional initial layers."""
        self._layers = set(args)
        self._knockout = False

    def append(self, val: TL) -> None:
        """Alias to :meth:`LayerSet.add`."""
        self.add(val)

    def extend(self, val: Iterable[TL]) -> None:
        """Extend the layer set with elements from an iterable, adding each only if not already present."""
        for v in val:
            self.append(v)

    def __contains__(self, x: object) -> bool:
        """Checks if layer `x` is in set, handling also compound layers such as `*.Cu`

        If `x` is iterable, checks if all objects in it are in set

        Examples:
            >>> Layer.CU_F in LayerSet(Layer.CU_F, Layer.CU_F)
            True
            >>> Layer.CU_F in LayerSet(Layer.CU_ALL)
            True
            >>> LayerSet(Layer.CU_F) in LayerSet(Layer.CU_F, Layer.B_CU)
            True
            >>> LayerSet(Layer.CU_F) in LayerCopperOuter.all # same as above
            True
            >>> LayerSet(Layer.CU_F, Layer.MASK_F) in LayerCopperOuter.all
            False
        """
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
        """Add a layer to the set if not already present."""
        if self.__contains__(value):  # ty:ignore[invalid-argument-type]
            return
        self._layers.add(value)

    def discard(self, value: TL) -> None:
        """Remove the specified layer from the set if present."""
        self._layers.discard(value)

    def __eq__(self, other: Any) -> bool:  # noqa: ANN401
        """Supports equation checks with:
        * LayerSet/generic set/BaseLayer iterable 
        * BaseLayer - True if set has exactly this one and only one layer
        """
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
        """Determine the appropriate key for serialization based on layer count."""
        return (
            name or "layer"
            if len(self._layers) <= 1 and all(not isinstance(layer, LayerSpecial) for layer in self._layers)
            else "layers"
        )

    def serialize(self) -> GeneralizedSexpr:
        """Serialize the layer set into a generalized sexpr tuple with quoted layer values and optional knockout marker."""
        return (
            *(Qstr(x._value) for x in sorted(self._layers, key=BaseLayer.order_id)),
            *(("knockout",) if self._knockout else ()),
        )

    def serialize_nested(self) -> GeneralizedSexpr:
        """Serialize the layer set into a nested sexpr tuple with each layer as a ('layer', value) pair."""
        return tuple(("layer", Qstr(x._value)) for x in sorted(self._layers, key=BaseLayer.order_id))

    @classmethod
    def deserialize_nested(cls, sexp: GeneralizedSexpr) -> LayerSet:
        """Deserialize a LayerSet from a nested sexpression structure."""
        return LayerSet(*(BaseLayer.deserialize_downcast(s[1]) for s in sexp))


class LayerCopper(BaseLayer):
    """LayerCopper represents a specialized layer type for copper components in a layered trace system. It inherits from BaseLayer and provides validation for layer functions specific to copper, ensuring only valid function types are accepted."""
    def validate_function(self, function: LayerFunction | None) -> LayerFunction:
        """Validates that the provided function is one of the allowed layer functions. Returns the function if valid, otherwise defaults to LayerFunction.SIGNAL."""
        valid_functions = [LayerFunction.SIGNAL, LayerFunction.JUMPER, LayerFunction.POWER, LayerFunction.MIXED]
        return function if function in valid_functions else LayerFunction.SIGNAL


class LayerCopperOuter(LayerCopper):
    """Layer representing an outer copper layer in a multi-layered PCB design. Inherits all functionality from LayerCopper and maintains validation for copper-specific layer functions."""
    pass


class LayerCopperInner(LayerCopper):
    """Layer representing inner copper layers in a PCB design. Used for layers between the outer copper layers."""
    pass


class LayerTech(BaseLayer):
    """Specialized layer in a trace system for technical operations with restricted function types. Inherits from BaseLayer and enforces validation of layer functions to ensure only allowed types are used."""
    def validate_function(self, function: LayerFunction | None) -> LayerFunction:
        """Validates that the provided function is one of the allowed layer functions. Returns the function if it is valid, otherwise defaults to LayerFunction.AUX."""
        valid_functions = [LayerFunction.AUX, LayerFunction.AUX_B, LayerFunction.AUX_F]

        return function if function in valid_functions else LayerFunction.AUX


class LayerPaste(LayerTech):
    """LayerPaste represents a specialized layer type for paste operations within trace systems. Inherits validation rules from LayerTech and enforces restricted function types suitable for paste operations."""
    pass


class LayerSilkS(LayerTech):
    """Layer representing the Silk Screen layer for technical trace operations. Used for defining silkscreen features in PCB design. Inherits validation rules from LayerTech."""
    pass


class LayerMask(LayerTech):
    """LayerMask represents a specialized layer type for masking operations in trace systems. Inherits from LayerTech and enforces validation of layer functions for masking workflows."""
    pass


class LayerAdhesive(LayerTech):
    """LayerAdhesive represents a specialized layer type for adhesive operations in trace systems. Inherits validation rules from LayerTech while enforcing specific constraints for adhesive layer functions."""
    pass


class LayerCourtyard(LayerTech):
    """LayerCourtyard represents a specialized layer type for defining physical boundaries and constraints in technical trace systems. Inherits validation rules from LayerTech and enforces restrictions suitable for courtyard definitions."""
    pass


class LayerFab(LayerTech):
    """LayerFab represents a fabrication layer in a trace system, inheriting from LayerTech. Used to define technical operations with restricted function types for manufacturing processes."""
    pass


class LayerUser(BaseLayer):
    """LayerUser represents a user-defined layer in a layered trace system. Supports type-safe instantiation and serialization to/from generalized sexpr formats. Identified by name and numeric identifier. Valid functions are AUX, AUX_B, and AUX_F."""
    def validate_function(self, function: LayerFunction | None) -> LayerFunction:
        """Validates that the provided function is one of the allowed layer functions. Returns the function if valid, otherwise defaults to LayerFunction.AUX."""
        valid_functions = [LayerFunction.AUX, LayerFunction.AUX_B, LayerFunction.AUX_F]

        return function if function in valid_functions else LayerFunction.AUX


class LayerSpecial(BaseLayer):
    """Specialized layer type for marking nodes requiring special handling during serialization or processing. Acts as a semantic marker inheriting all functionality from BaseLayer."""
    pass


class Layer:
    """Class representing KiCad layer definitions. Provides access to standard layers and methods to construct inner copper and user-defined layers.

    Layers are organized by function:
    - Copper layers: F.Cu, B.Cu, and inner layers InN.Cu
    - Adhesive layers: F.Adhes, B.Adhes
    - Paste layers: F.Paste, B.Paste
    - Silk screen layers: F.SilkS, B.SilkS
    - Mask layers: F.Mask, B.Mask
    - Technical layers: Edge.Cuts, Margin
    - Courtyard layers: F.CrtYd, B.CrtYd
    - Fabrication layers: F.Fab, B.Fab
    - User layers: Dwgs.User, Cmts.User, Eco1.User, Eco2.User

    Special layers:
    - *.Cu: All copper layers
    - F&B.Cu: Top and bottom copper layers only
    - Inner: All inner copper layers
    - *.Mask: All mask layers

    Use static methods CU_IN() and USER() to create inner copper and user-defined layers.

    Example:
    ```python
    from kicad_layer import Layer

    # Access predefined layers
    top_copper = Layer.CU_F
    bottom_copper = Layer.CU_B

    # Create inner copper layer
    inner_layer = Layer.CU_IN(3)

    # Create user layer
    user_layer = Layer.USER(5)
    ```
    """
    __PrivateGuard = BaseLayer._BaseLayer__PrivateGuard  # type: ignore  # ty:ignore[unresolved-attribute]
    CU_F: Final[LayerCopperOuter] = LayerCopperOuter("F.Cu", 0, __PrivateGuard())
    """Front copper layer definition"""
    CU_B: Final[LayerCopperOuter] = LayerCopperOuter("B.Cu", 2, __PrivateGuard())
    """Bottom outer copper layer definition"""
    ADHESIVE_F: Final[LayerAdhesive] = LayerAdhesive("F.Adhes", 9, __PrivateGuard())
    """Front adhesive layer definition"""
    ADHESIVE_B: Final[LayerAdhesive] = LayerAdhesive("B.Adhes", 11, __PrivateGuard())
    """Bottom adhesive layer definition"""
    PASTE_F: Final[LayerPaste] = LayerPaste("F.Paste", 13, __PrivateGuard())
    """Front paste layer definition"""
    PASTE_B: Final[LayerPaste] = LayerPaste("B.Paste", 15, __PrivateGuard())
    """Bottom paste layer definition"""
    SILKS_F: Final[LayerSilkS] = LayerSilkS("F.SilkS", 5, __PrivateGuard())
    """Front silk screen layer definition"""
    SILKS_B: Final[LayerSilkS] = LayerSilkS("B.SilkS", 7, __PrivateGuard())
    """Silk screen layer for bottom technical trace operations."""
    MASK_F: Final[LayerMask] = LayerMask("F.Mask", 1, __PrivateGuard())
    """Front layer mask definition"""
    MASK_B: Final[LayerMask] = LayerMask("B.Mask", 3, __PrivateGuard())
    """Bottom layer mask definition"""
    EDGE_CUTS: Final[LayerTech] = LayerTech("Edge.Cuts", 25, __PrivateGuard())
    """Layer for board outline and cutting paths."""
    MARGIN: Final[LayerTech] = LayerTech("Margin", 27, __PrivateGuard())
    """Layer for margin definitions used in PCB design"""
    COURTYARD_F: Final[LayerCourtyard] = LayerCourtyard("F.CrtYd", 31, __PrivateGuard())
    """Front courtyard layer definition"""
    COURTYARD_B: Final[LayerCourtyard] = LayerCourtyard("B.CrtYd", 29, __PrivateGuard())
    """Back courtyard layer definition"""
    FAB_F: Final[LayerFab] = LayerFab("F.Fab", 35, __PrivateGuard())
    """Front fabrication layer definition."""
    FAB_B: Final[LayerFab] = LayerFab("B.Fab", 33, __PrivateGuard())
    """Bottom fabrication layer definition"""
    DRAWINGS: Final[LayerUser] = LayerUser("Dwgs.User", 17, __PrivateGuard())
    """User-defined drawings layer for custom graphics and annotations."""
    COMMENTS: Final[LayerUser] = LayerUser("Cmts.User", 19, __PrivateGuard())
    """User-defined comments layer for schematic annotations"""
    ECO1: Final[LayerUser] = LayerUser("Eco1.User", 21, __PrivateGuard())
    """User-defined layer ECO1 for custom annotations and notes."""
    ECO2: Final[LayerUser] = LayerUser("Eco2.User", 23, __PrivateGuard())
    """User-defined layer ECO2 with index 23."""

    CU_ALL: Final[LayerSpecial] = LayerSpecial("*.Cu", 0, __PrivateGuard())
    """All copper layers marker"""
    CU_FB: Final[LayerSpecial] = LayerSpecial(
    """Front and back copper layer identifier"""
        "F&B.Cu", 0, __PrivateGuard()
    )  # used in tht pads that are top&bottom only
    CU_IN_ALL: Final[LayerSpecial] = LayerSpecial("Inner", 1, __PrivateGuard())
    """All inner copper layers in the pad stack"""

    MASK_ALL: Final[LayerSpecial] = LayerSpecial("*.Mask", 1, __PrivateGuard())
    """All mask layers combination"""

    @staticmethod
    def CU_IN(number: int) -> LayerCopperInner:  # noqa: N802
        """Factory method to create inner copper layers.

        Creates a LayerCopperInner instance for a specified inner copper layer number.
        Valid layer numbers are 1 through KICAD_MAX_LAYER_CU (inclusive).

        Args:
            number: Inner copper layer number (1 to KICAD_MAX_LAYER_CU)

        Returns:
            LayerCopperInner: New inner copper layer instance

        Raises:
            ValueError: If number is outside the valid range [1, KICAD_MAX_LAYER_CU]

        Example:
            >>> layer = Layer.CU_IN(3)
            >>> print(layer.name)
            In3.Cu
        """
        if 1 <= number <= KICAD_MAX_LAYER_CU:
            return LayerCopperInner(f"In{number}.Cu", 2 + 2 * number, Layer.__PrivateGuard())
        raise ValueError(f"In{number}.Cu is not supported, number should be between 1 & {KICAD_MAX_LAYER_CU}")

    @staticmethod
    def USER(number: int) -> LayerUser:  # noqa: N802
        """Creates a LayerUser instance for a user-defined layer with the given number.

        Args:
            number: User layer number, must be between 1 and KICAD_MAX_LAYER_USER (inclusive).

        Returns:
            LayerUser: A user-defined layer with the specified number.

        Raises:
            ValueError: If the layer number is outside the supported range.

        Example:
            >>> layer = Layer.USER(5)
            >>> print(layer.name)
            User.5
            >>> print(layer.index)
            47
        """
        if 1 <= number <= KICAD_MAX_LAYER_USER:
            return LayerUser(f"User.{number}", 37 + 2 * number, Layer.__PrivateGuard())
        raise ValueError(f"User.{number} is not supported, number should be between 1 & {KICAD_MAX_LAYER_USER}")


# Cycle procedural layers, so that they are added in BaseLayer._know_layers
for i in range(1, KICAD_MAX_LAYER_CU + 1):
    Layer.CU_IN(i)
for i in range(1, KICAD_MAX_LAYER_USER + 1):
    Layer.USER(i)


class BoardSide(Qstr, AutoSerdeEnum):
    """Indicates board side for PCB layers."""

    FRONT = "F.Cu"
    BACK = "B.Cu"


class NetBase:
    """Base class for network-related objects. Provides common functionality and attributes for network components."""
    name: str
    """Network component name identifier."""


class Net(NetBase, AutoSerde):
    """Net represents a network connection in a PCB design, identified by a number and name. The number field is deprecated in K10 and should not be used. The name field is required and positional."""
    _number: int | None = F(positional=True, skip=True).version(Version.K9.pcb, skip=False)
    """Net identifier eg. `0` [Deprecated in K10]"""

    name: str = F(positional=True)
    """Net name eg. `GND`"""


class NetSimple(NetBase, AutoSerde):
    """Simple network representation with identifier and name. Used in PCB designs to map connections between components."""
    _number: int | None = F(positional=True, skip=True).version(Version.K9.pcb, skip=False)
    """Net identifier eg. `0` [Deprecated in K10]"""
    name: str = F(positional=True).version(Version.K9.pcb, skip=True)  # type: ignore
    """Net name, e.g., "GND"."""

    def _askiff_post_deser(self) -> None:
        """Registers this instance for post-processing after deserialization is complete. Called automatically during deserialization."""
        AutoSerdeFile._post_final_deser_objects.append(self)

    def _post_final_deser(self, root_object) -> None:  # type: ignore # noqa: ANN001
        """Populates net name from board-level net map after deserialization.

        # Dev notes:
        Summary: Post-process deserialized object to populate net name from board-level net map.
        """
        # Note: annotation skipped to prevent circular imports
        if self.name is not None or not hasattr(root_object, "nets"):
            return
        nr = self._number
        self.name = next((net.name for net in root_object.nets or () if net._number == nr), "Unknown")


###########################Zone############################


class SimplePolyFilled(BasePoly):
    """Represents a filled polygon shape defined by a list of points. Inherits from BasePoly and provides methods to compute extreme points and convert point coordinates to global space. The polygon is rendered on the top copper layer by default."""
    _askiff_key: ClassVar[str] = "filled_polygon"
    layer: LayerCopper = F(Layer.CU_F)
    """Copper layer where the polygon is placed"""
    _pts = F()


class ZoneOutlineHatchStyle(str, AutoSerdeEnum):
    """Enumeration representing the hatch style for zone outline rendering."""
    NONE = "none"
    HATCH_EDGE = "edge"
    HATCH_FULL = "full"


class ZoneHatch(AutoSerde, positional=True):  # type: ignore
    """Configuration for zone hatch patterns used in drawing outlines."""
    style: ZoneOutlineHatchStyle = F(ZoneOutlineHatchStyle.HATCH_EDGE)
    """Hatch style for zone outline rendering."""
    pitch: float = 0.5
    """Distance between hatch lines in zone pattern."""


class ZoneTeardrop(AutoSerde):
    """Class representing a teardrop zone in a PCB design, used for defining curved or rounded shapes in zone definitions."""
    _askiff_key: ClassVar[str] = "teardrop"
    type: str = F(unquoted=True)
    """Type of teardrop shape used in PCB zone definitions."""


class ZoneKeepout(AutoSerde):
    """Class representing a zone keepout configuration for PCB design. Defines which types of elements are allowed or not allowed in a keepout zone."""
    tracks: bool = F(true_val="allowed", false_val="not_allowed")
    """Whether tracks are allowed in the keepout zone."""
    vias: bool = F(true_val="allowed", false_val="not_allowed")
    """Whether vias are allowed in the keepout zone."""
    pads: bool = F(true_val="allowed", false_val="not_allowed")
    """Whether pads are allowed in the keepout zone."""
    copperpour: bool = F(true_val="allowed", false_val="not_allowed")
    """Whether copper pour is allowed in the keepout zone."""
    footprints: bool = F(true_val="allowed", false_val="not_allowed")
    """Whether footprints are allowed in the keepout zone."""


class ZonePlacement(AutoSerde):
    """Configuration for zone placement in a layout. Controls whether a zone is enabled and specifies its placement details."""
    enabled: bool = False
    """Whether the zone placement is enabled."""
    sheetname: str | None = None
    """Sheet name for the zone placement. Mutually exclusive with component_class."""
    component_class: str | None = None
    """Component class for the zone placement. Mutually exclusive with sheetname."""


class ZoneFillMode(str, AutoSerdeEnum):
    """Enumeration of zone fill modes for graphical elements. Used to specify how areas within a zone should be filled when rendered."""
    HATCH = "hatch"
    SOLID = ""


class ZoneSmoothing(str, AutoSerdeEnum):
    """Enumeration for defining zone smoothing types used in geometric operations. Supports serialization and deserialization through AutoSerdeEnum mixin."""
    CHAMFER = "chamfer"
    FILLET = "fillet"


class ZoneHatchSmoothing(str, AutoSerdeEnum):
    """Enumeration for defining hatch smoothing styles in Zone entities. Supports serialization and deserialization."""
    NONE = "0"
    CHAMFER = "1"
    ROUND = "2"
    ROUND_FINER = "3"


class ZoneIslandRemoval(str, AutoSerdeEnum):
    """Defines zone island removal rules for polygon processing. Controls when islands (holes) within zones are removed during serialization."""

    ALWAYS = "0"
    """Always remove islands"""
    NEVER = "1"
    """Never remove islands"""
    BELOW_AREA_LIMIT = "2"
    """Remove islands bellow area limit"""


class ZoneHatchBorderAlg(str, AutoSerdeEnum):
    """Indicates how zone border is handled with hatch fill. Controls the algorithm for processing zone boundaries when applying hatch patterns."""

    HATCH_THICKNESS = "hatch_thickness"


class ZoneFill(AutoSerde):
    """Configuration for zone filling operations.

    # Dev notes:
    Summary: ZoneFill configures how a zone is filled and its thermal properties. It accepts filled status, fill mode, and thermal connection parameters including gap distance and bridge width. The class inherits serialization behavior from AutoSerde and supports various zone filling configurations.
    """
    filled: bool = F(name="yes", flag=True, bare=True)
    """Whether the zone has been filled."""

    mode: ZoneFillMode = F(ZoneFillMode.SOLID)
    """How the zone is filled graphically"""

    thermal_gap: float | None = None
    """Distance from zone to pad thermal relief connection"""

    thermal_bridge_width: float | None = None
    """Width of thermal bridge connecting zone to pad"""

    smoothing_style: ZoneSmoothing | None = F(name="smoothing")
    """Style of corner smoothing for zone filling operations"""

    smoothing_radius: float | None = F(name="radius")
    """Corner smoothing radius for zone boundaries"""

    island_removal_mode: ZoneIslandRemoval | None = None
    """Whether island removal is enabled and how it's applied during zone processing"""

    island_area_min: float | None = None
    """Minimum allowed zone island area threshold for removal optimization"""

    hatch_thickness: float | None = None
    """Hatch grid line thickness for zone filling"""

    hatch_gap: float | None = None
    """Spacing between lines of hatch grid fill"""

    hatch_orientation: float | None = None
    """Angle of the hatch pattern lines for zone filling"""

    hatch_smoothing_level: ZoneHatchSmoothing | None = None
    """Hatch outline smoothing level for zone filling"""

    hatch_smoothing_value: float | None = None
    """Ratio controlling hatch smoothing between hole and chamfer size."""

    hatch_border_algorithm: ZoneHatchBorderAlg | None = None
    """How zone border is processed when applying hatch fill patterns"""

    hatch_min_hole_area: float | None = None
    """Minimum hole area for hatch filling pattern."""


class ZonePadConnectionStyle(str, AutoSerdeEnum):
    """Enumeration defining styles for connecting pads to zones in PCB design."""
    NO_CONNECT = "no"
    """Pads are not connect to zone"""

    THERMAL_RELIEF = ""
    """Pads are connected to zone using thermal reliefs"""

    SOLID = "yes"
    """Pads are connected to zone using solid fill"""

    THERMAL_RELIEF_THT = "thru_hole_only"
    """Only through hold pads are connected to zone using thermal reliefs"""


class ZonePadConnection(AutoSerde):
    """Class representing a zone pad connection configuration for PCB design. Defines how pads are connected to zones, including thermal relief style and clearance settings."""
    style: ZonePadConnectionStyle = F(ZonePadConnectionStyle.THERMAL_RELIEF, positional=True)
    """Pad connection style to copper zones."""
    clearance: float | None = None
    """Clearance value for zone pad connections."""


class Zone(AutoSerde):
    """A zone represents a defined area on a PCB, typically used for copper pours, keepouts, or other design rules. Supports configuration of net connections, layers, clearance, teardrops, and fill properties."""
    net: NetSimple | None = None
    """Net connection associated with the zone."""
    net_name: str | None = None
    """Net name associated with the zone."""
    locked: bool | None = None
    """Whether the zone is locked against modifications."""
    layers: LayerSet[BaseLayer] = F()
    """Layers assigned to the zone for copper pour or design rule application"""
    uuid: Uuid | None = None
    """Unique identifier for the zone object"""
    name: str | None = None
    """Zone identifier name."""
    hatch: ZoneHatch = F()
    """Whether hatch patterns are enabled for zone outlines."""
    priority: int | None = None
    """Zone priority for copper pour ordering and connection handling"""
    teardrop: ZoneTeardrop | None = F(name="attr", nested=True)
    """Whether teardrop shaping is enabled for the zone."""
    connect_pads: ZonePadConnection = F()
    """Pad connection style for the zone."""
    clearance: float = F(0.25, skip=True)
    """Distance between zone and other copper elements."""
    min_thickness: float = 0.25
    """Minimum thickness of the zone outline"""
    filled_areas_thickness: bool | None = None
    """Whether filled areas have a specified thickness setting."""
    keepout: ZoneKeepout | None = None
    """Whether keepout rules are applied to the zone."""
    placement: ZonePlacement | None = None
    """Whether zone placement is enabled and its placement details."""
    fill: ZoneFill | None = None
    """Whether the zone has a fill configuration applied."""
    polygons: list[BasePoly] = F(name="polygon", flatten=True)
    """Polygon shapes defining the zone area"""
    filled_polygons: list[SimplePolyFilled] = F(name="filled_polygon", flatten=True)
    """Filled polygon shapes defining the zone area"""

    def _askiff_post_deser(self) -> None:
        """Handle post-deserialization clearance assignment for connect pads. If the connect pads have a clearance value set, assign it to the zone's clearance attribute. This ensures proper clearance handling after object reconstruction from serialized data."""
        if self.connect_pads.clearance:
            self.clearance = self.connect_pads.clearance

    def _askiff_pre_ser(self) -> Zone:
        """Applies clearance value to connect_pads if clearance is set. Returns self for chaining."""
        if self.connect_pads.clearance:
            self.connect_pads.clearance = self.clearance
        return self


###########################Misc############################


class Point(AutoSerde):
    """Point represents a geometric point with position, size, layer, and unique identifier. Supports automatic serialization and deserialization with field ordering preservation."""
    _askiff_key: ClassVar[str] = "point"
    position: Position = F(name="at")
    """Point position in 2D space with optional angle."""
    size: float = 1
    """Point size for rendering and display purposes."""
    layer: BaseLayer = F(Layer.DRAWINGS)
    """Layer assignment for the point in the trace hierarchy"""
    uuid: Uuid = F()
    """Unique identifier for the point object."""


class TeardropSettings(AutoSerde):
    """Settings for configuring teardrop shapes in PCB design. Controls dimensions, edge curvature, filtering, and connection preferences."""
    best_length_ratio: float | None = None
    """Ratio of teardrop length to width for optimal shape definition."""
    max_length: float | None = None
    """Maximum length allowed for teardrop shapes."""
    best_width_ratio: float | None = None
    """Ratio of best width to trace width for teardrop sizing"""
    max_width: float | None = None
    """Maximum width of the teardrop shape."""
    curved_edges: bool | None = None
    """Whether teardrop edges follow a curved shape."""
    filter_ratio: float | None = None
    """Ratio threshold for filtering teardrops based on size."""
    enabled: bool | None = None
    """Whether teardrop processing is enabled."""
    allow_two_segments: bool | None = None
    """Whether to allow teardrops with two segments instead of one."""
    prefer_zone_connections: bool | None = None
    """Whether to prefer zone connections for teardrops."""
