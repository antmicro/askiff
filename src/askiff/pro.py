from __future__ import annotations

import logging
from pathlib import Path
from threading import RLock
from typing import Any, Generic, Self, TypeVar

from .auto_serde import AutoSerdeFile
from .const import TRACE, TRACE_DIS

# from .kistruct.board import Board
from .kistruct.footprint import Footprint, LibTableFp
from .sexpr import Sexpr

logging.addLevelName(TRACE_DIS, "TRACE_DIS")
logging.addLevelName(TRACE, "TRACE")


T = TypeVar("T", bound=AutoSerdeFile)


class _LazyFile(Generic[T]):
    """Thread-safe transparent file lazy loader"""

    def __init__(self, inner_cls: type[T], value: Path, force_load: bool = False) -> None:
        self._inner_cls = inner_cls
        if not value.exists():
            raise FileNotFoundError(value)
        self.__path = value
        self._value = value
        self._lock = RLock()
        if force_load:
            self._load()

    def _load(self) -> T:
        # Fast path (already loaded)
        if isinstance(self._value, self._inner_cls):
            return self._value

        # Slow path (needs loading)
        with self._lock:
            # Double-check as before locking, file might get loaded
            if isinstance(self._value, Path):
                loaded = self._inner_cls.from_file(self._value)
                self._value = loaded
            return self._value  # type: ignore

    # Transparent attribute access
    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        return getattr(self._load(), name)

    def __repr__(self) -> str:
        if isinstance(self._value, Path):
            return f"<LazyFile unloaded path={self._value}>"
        return repr(self._value)

    def save(self, path: Path | None, initial_root_path: Path) -> None:
        if not self.is_loaded():
            return

        if path and self.__path.is_relative_to(initial_root_path):
            file = self.__path.relative_to(initial_root_path)
            self.to_file(path=path / file)
        else:
            self.to_file()

    def is_loaded(self) -> bool:
        return not isinstance(self._value, Path)


class AskiffLibFp:
    path: Path
    __initial_path: Path
    objects: list[_LazyFile[Footprint]]

    def __init__(self, path: Path) -> None:
        self.path = path
        self.__initial_path = path

    def load(self, force: bool = False) -> Self:
        self.objects = []
        for path in self.path.glob("*.kicad_mod"):
            self.objects.append(_LazyFile(Footprint, path, force))
        return self

    def save(self, path: Path | None = None) -> None:
        for o in self.objects:
            o.save(path, self.__initial_path)


class AskiffPro:
    path: Path
    __initial_path: Path
    # pro: dict[Path, Sexpr] # Note: kicad_pro seems to be json
    # pcb: list[_LazyFile[Board]]
    sch: dict[Path, Sexpr]  # TODO: replace with target kicad structure
    fp: dict[str, AskiffLibFp]
    fp_lib_table: LibTableFp
    variables: dict[str, str]

    def __init__(self, path: Path) -> None:
        self.path = path
        self.__initial_path = path
        self.variables = {"KIPRJMOD": str(path)}

    def resolve_var(self, string: str) -> str:
        for var, subst in self.variables.items():
            string = string.replace("${" + var + "}", subst)
        return string

    def load(self, force: bool = False) -> Self:
        # self.pro={p: Sexpr.from_file(p) for p in self.path.glob("*.kicad_pro")}

        # self.pcb = []
        # for path in self.path.glob("*.kicad_pcb"):
        #     self.pcb.append(_LazyFile(Board, path, force))

        fp_lib_table_path = self.path / "fp-lib-table"
        self.fp_lib_table = LibTableFp.from_file(fp_lib_table_path) if fp_lib_table_path.exists() else LibTableFp()
        self.fp = {lib.name: AskiffLibFp(Path(self.resolve_var(lib.uri))).load(force) for lib in self.fp_lib_table.lib}

        return self

    def save(self, path: Path | None = None) -> None:
        # for p, sexpr in self.pro.items():
        #     sexpr.to_file(p)

        # for pcb in self.pcb:
        #     pcb.save(path, self.__initial_path)
        # for p, sexpr in self.sch.items():
        #     sexpr.to_file(p)
        for lib in self.fp.values():
            if path and lib._AskiffLibFp__initial_path.is_relative_to(self.__initial_path):  # type: ignore # ty:ignore[unresolved-attribute]
                file = lib._AskiffLibFp__initial_path.relative_to(self.__initial_path)  # type: ignore  # ty:ignore[unresolved-attribute]
                lib.save(path / file)
            else:
                lib.save()
        pass
