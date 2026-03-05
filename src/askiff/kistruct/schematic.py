from typing import ClassVar

from askiff.auto_serde import AutoSerdeFile


class Schematic(AutoSerdeFile):
    _askiff_key: ClassVar[str] = "kicad_sch"
    