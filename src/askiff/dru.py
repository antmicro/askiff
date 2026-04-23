from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Final, cast

from askiff._auto_serde import AutoSerde, AutoSerdeFile, F
from askiff.const import Version

if TYPE_CHECKING:  # workaround around ty not allowing Any subclasses assignment to final classes
    F = cast(Any, F)  # type: ignore

class Rule(AutoSerde):
    name: str=F(positional=True)


class DesignRulesFile(AutoSerdeFile):
    """Represents a KiCad Custom design rules file (.kicad_dru)"""

    _askiff_key: Final[str] = ""  # type: ignore

    _askiff_sexpr_format: ClassVar[dict[str, bool]] = {"flatten":True, "reduced_ident":True}
    """File type specific S-Expression formatting"""
    
    fs_ext: Final[str] = F(".kicad_dru", skip=True)  # type: ignore # ty:ignore[override-of-final-variable]
    """File name extension"""

    version: int = F(Version.DEFAULT.dru)
    """Defines the file format revision"""

