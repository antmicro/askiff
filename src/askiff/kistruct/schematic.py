from typing import ClassVar

from askiff.auto_serde import AutoSerdeFile
from askiff.const import Version


class Schematic(AutoSerdeFile):
    _askiff_key: ClassVar[str] = "kicad_sch"
    version: int | None = Version.DEFAULT.sch
    """Defines the file format version"""
