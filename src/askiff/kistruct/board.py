from typing import ClassVar

from askiff.auto_serde import AutoSerdeFile
from askiff.const import Version


class Board(AutoSerdeFile):
    _askiff_key: ClassVar[str] = "kicad_pcb"

    version: int | None = Version.DEFAULT.pcb
    """Defines the file format version"""
