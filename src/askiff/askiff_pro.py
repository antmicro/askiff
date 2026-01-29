from pathlib import Path
from typing import Self

from .sexpr import Sexpr


class AskiffPro:
    path: Path
    # pro: dict[Path, Sexpr] # Note: kicad_pro seems to be json
    pcb: dict[Path, Sexpr]  # TODO: replace with target kicad structure
    sch: dict[Path, Sexpr]

    def __init__(self, path: Path) -> None:
        self.path = path

    def load_all(self) -> Self:
        # self.pro={p: Sexpr.from_file(p) for p in self.path.glob("*.kicad_pro")}
        self.pcb = {p: Sexpr.from_file(p) for p in self.path.glob("*.kicad_pcb")}
        self.sch = {p: Sexpr.from_file(p) for p in self.path.glob("*.kicad_sch")}
        return self

    def save_all(self, path: Path | None = None) -> None:
        # for p, sexpr in self.pro.items():
        #     sexpr.to_file(p)
        for p, sexpr in self.pcb.items():
            sexpr.to_file(p)
        for p, sexpr in self.sch.items():
            sexpr.to_file(p)
        pass
