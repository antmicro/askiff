from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Final, cast

from askiff._auto_serde import AutoSerde, AutoSerdeFile, F
from askiff._sexpr import Qstr, Sexpr
from askiff.const import Version

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore


class Rule(AutoSerde):
    """Description of a design rule, describing its conditions and constraints"""

    name: str = F(positional=True)
    """User name of the rule"""

    comment: str | None = F(positional=True, serialize=lambda c: ("# " + c,), deserialize=lambda c: c.lstrip("# "))
    """Comment about rule, eg. describing rule destination"""

    _layer: str | None = F(name="layer", serialize=lambda v: (v if v in ["inner", "outer"] else Qstr(v),))
    _condition: str | None = F(name="condition")
    _constraints: list[Sexpr] = F(name="constraint", flatten=True)


class DesignRulesFile(AutoSerdeFile):
    """Represents a KiCad Custom design rules file (.kicad_dru)

    .. warning:: Serialization accuracy

        Due to nature of `*.kicad_dru` (that is no enforced formatting on KiCad side),
        current implementation of :class:`askiff.dru.DesignRulesFile` may introduce following non-semantic changes:

        * Removal of top level comments (not enclosed in `()`)
        * Enforced single leading space in comments
        * Changed formatting of S-expressions (ie. different splitting between lines)

    """

    _askiff_key: Final[str] = ""  # type: ignore

    _askiff_sexpr_format: ClassVar[dict[str, bool]] = {"flatten": True, "reduced_ident": True, "keep_comments": True}
    """File type specific S-Expression formatting"""

    fs_ext: Final[str] = F(".kicad_dru", skip=True)  # type: ignore # ty:ignore[override-of-final-variable]
    """File name extension"""

    version: int = F(Version.DEFAULT.dru)
    """Defines the file format revision"""

    rules: list[Rule] = F(name="rule", flatten=True)
    """List of rules defined in this file"""
