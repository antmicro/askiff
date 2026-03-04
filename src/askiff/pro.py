from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Self

from .const import TRACE, TRACE_DIS
from .kistruct.board import Board
from .kistruct.footprint import Footprint, LibTableFp
from .sexpr import Sexpr

logging.addLevelName(TRACE_DIS, "TRACE_DIS")
logging.addLevelName(TRACE, "TRACE")
time_logger = logging.getLogger("time_log")


class Timer:
    def __init__(self, message: str = "Execution time") -> None:
        self.message = message

    def __enter__(self) -> Timer:
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args) -> None:  # type: ignore # noqa: ANN002
        elapsed = time.perf_counter() - self.start
        time_logger.info(f"{self.message}: {elapsed:.3f} seconds")


class AskiffLibFp:
    path: Path
    objects: list[Footprint]

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self, force: bool = False) -> Self:
        self.objects = []
        for p in self.path.glob("*.kicad_mod"):
            self.objects.append(Footprint.from_file(p))
        return self

    def save(self, path: Path | None = None, force: bool = False) -> None:
        for o in self.objects:
            o.to_file()


class AskiffPro:
    path: Path
    # pro: dict[Path, Sexpr] # Note: kicad_pro seems to be json
    # pcb: dict[Path, Sexpr]
    pcb: list[Board]
    sch: dict[Path, Sexpr]  # TODO: replace with target kicad structure
    fp: dict[str, AskiffLibFp]
    fp_lib_table: LibTableFp
    variables: dict[str, str]

    def __init__(self, path: Path) -> None:
        self.path = path
        self.variables = {"KIPRJMOD": str(path)}

    def resolve_var(self, string: str) -> str:
        for var, subst in self.variables.items():
            string = string.replace("${" + var + "}", subst)
        return string

    def load(self, force: bool = False) -> Self:
        # self.pro={p: Sexpr.from_file(p) for p in self.path.glob("*.kicad_pro")}

        self.pcb = []
        for path in self.path.glob("*.kicad_pcb"):
            with Timer(f"Load `{path}`"):
                self.pcb.append(Board.from_file(path))
        # self.pcb = {}
        # for path in self.path.glob("*.kicad_pcb"):
        #     with Timer(f"Load `{path}`"):
        #         self.pcb[path] = Sexpr.from_file(path)
        # self.sch = {p: Sexpr.from_file(p) for p in self.path.glob("*.kicad_sch")}
        fp_lib_table_path = self.path / "fp-lib-table"
        self.fp_lib_table = LibTableFp.from_file(fp_lib_table_path) if fp_lib_table_path.exists() else LibTableFp()
        self.fp = {lib.name: AskiffLibFp(Path(self.resolve_var(lib.uri))).load(force) for lib in self.fp_lib_table.lib}

        return self

    def save(self, path: Path | None = None, force: bool = False) -> None:
        # for p, sexpr in self.pro.items():
        #     sexpr.to_file(p)
        # for path, pcb in self.pcb.items():
        #     with Timer(f"Save `{path}`"):
        #         pcb.to_file(path)
        for pcb in self.pcb:
            with Timer(f"Save `{pcb._fs_path}`"):
                pcb.to_file()
        # for p, sexpr in self.sch.items():
        #     sexpr.to_file(p)
        for lib in self.fp.values():
            lib.save(force=force)
        pass
