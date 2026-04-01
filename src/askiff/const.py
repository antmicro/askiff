from dataclasses import dataclass

TRACE_DIS = 4
"""Log level for very verbose debugging, printing a.o. disassembly of some functions"""

TRACE = 5
"""Log level for very verbose debugging, printing a.o. AutoSerde generated source code for serialize/deserialize"""

KICAD_MAX_LAYER_CU = 32
KICAD_MAX_LAYER_USER = 45


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

        sch: int
        pcb: int
        sym: int
        fp: int
        lib_table: int

    class K8(BaseVer):
        """Version constants for KiCad 8 files"""

        sch = 20231120
        pcb = 20240108
        sym = sch
        fp = pcb
        lib_table = 7

    class K9(BaseVer):
        """Version constants for KiCad 9 files"""

        sym = 20241209
        sch = 20250114
        pcb = 20241229
        fp = pcb
        lib_table = 7

    class K10(BaseVer):
        """Version constants for KiCad 10 files"""

        sym = 20251024
        sch = 20260306
        pcb = 20260206
        fp = pcb
        lib_table = 7

    MIN = K8
    """Oldest supported file version (for read operation)"""

    DEFAULT = K10
    """Default file version (used when creating new objects)"""

    MAX = K10
    """Newest file format revision that is supported"""

    generator = "askiff"
    generator_ver = "9.0"
