from dataclasses import dataclass

TRACE_DIS = 4
"""Log level for very verbose debugging, printing a.o. disassembly of some functions"""

TRACE = 5
"""Log level for very verbose debugging, printing a.o. AutoSerde generated source code for serialize/deserialize"""

KICAD_MAX_LAYER_CU = 32
KICAD_MAX_LAYER_USER = 45


class Version:
    """Describes version field of file"""

    @dataclass
    class BaseVer:
        sch: int
        pcb: int
        sym: int
        fp: int
        lib_table: int

    class K8(BaseVer):
        sch = 20231120
        pcb = 20240108
        sym = sch
        fp = pcb
        lib_table = 7

    class K9(BaseVer):
        sym = 20241209
        sch = 20250114
        pcb = 20241229
        fp = pcb
        lib_table = 7

    class K10(BaseVer):
        sym = 20251024
        sch = 20260101
        pcb = 20260206
        fp = pcb
        lib_table = 7

    MIN = K8
    """Oldest supported file version (for read operation)"""

    DEFAULT = K9
    """Default file version (used when creating new objects)"""

    MAX = K10

    generator = "askiff"
    generator_ver = "9.0"
