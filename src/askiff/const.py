import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from xdg_base_dirs import xdg_config_home

TRACE_DIS = 4
"""Log level for very verbose debugging, printing a.o. disassembly of some functions"""

TRACE = 5
"""Log level for very verbose debugging, printing a.o. AutoSerde generated source code for serialize/deserialize"""

KICAD_MAX_LAYER_CU = 32
KICAD_MAX_LAYER_USER = 45

log = logging.getLogger()


class Version:
    """Matches version field of KiCad file, defines format revisions for schematic, PCB, symbol, footprint and others"""

    @dataclass
    class BaseVer:
        """
        File format revisions defined by KiCad
        See defines in KiCad source code for reference:
        - fp/pcb : https://gitlab.com/kicad/code/kicad/-/blob/10.0/pcbnew/pcb_io/kicad_sexpr/pcb_io_kicad_sexpr.h#L202
        - sym/sch: https://gitlab.com/kicad/code/kicad/-/blob/10.0/eeschema/sch_file_versions.h#L138
        """

        name: ClassVar[str]
        major: ClassVar[int]

        sch: ClassVar[int]
        pcb: ClassVar[int]
        sym: ClassVar[int]
        fp: ClassVar[int]
        dru: ClassVar[int]
        lib_table: ClassVar[int]
        _env_variables: ClassVar[dict[str, str] | None] = None

        @classmethod
        def kicad_config_path(cls) -> Path:
            return xdg_config_home() / "kicad" / cls.name

        @classmethod
        def env_variables(cls) -> dict[str, str]:
            if not cls._env_variables:
                cls._env_variables = cls._get_env_variables()

            return cls._env_variables

        @classmethod
        def _get_env_variables(cls) -> dict[str, str]:
            kicad_common_path = cls.kicad_config_path() / "kicad_common.json"

            if not kicad_common_path.is_file():
                return {}

            with open(kicad_common_path) as f:
                kicad_common_json = json.loads(f.read())

            try:
                return kicad_common_json["environment"]["vars"] or {}
            except KeyError:
                return {}

    class K8(BaseVer):
        """Version constants for KiCad 8 files"""

        name = "8.0"
        major = 8

        sch = 20231120
        pcb = 20240108
        sym = sch
        fp = pcb
        dru = 1
        lib_table = 0

    class K9(BaseVer):
        """Version constants for KiCad 9 files"""

        name = "9.0"
        major = 9

        sym = 20241209
        sch = 20250114
        pcb = 20241229
        fp = pcb
        dru = 1
        lib_table = 0

    class K10(BaseVer):
        """Version constants for KiCad 10 files"""

        name = "10.0"
        major = 10

        sym = 20251024
        sch = 20260306
        pcb = 20260206
        fp = pcb
        dru = 1
        lib_table = 7

    MIN = K8
    """Oldest supported file version (for read operation)"""

    DEFAULT = K10
    """Default file version (used when creating new objects)"""

    MAX = K10
    """Newest file format revision that is supported"""

    generator = "askiff"
    generator_ver = "9.0"

    versions: Sequence[type[BaseVer]] = [K8, K9, K10]

    @classmethod
    def from_file_version(cls, version: int, file_type: Literal["sch", "pcb"]) -> type[BaseVer] | None:
        file_kicad_version = next((v for v in cls.versions if getattr(v, file_type) == version), None)

        if file_kicad_version is None:
            log.warning(
                f"Couldn't match .kicad_{file_type} file version.\n"
                f"\nExpected one of {[getattr(v, file_type) for v in cls.versions]}, got {version}."
            )

        return file_kicad_version
