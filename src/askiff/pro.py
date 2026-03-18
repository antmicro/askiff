from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path
from threading import RLock
from typing import Any, Generic, Self, TypeVar

from .auto_serde import AutoSerdeFile
from .const import TRACE, TRACE_DIS
from .kistruct.board import Board
from .kistruct.footprint import FootprintFile, LibTableFp
from .kistruct.schematic import Schematic
from .kistruct.symbol import LibSymbol, LibTableSym, SymbolFile

logging.addLevelName(TRACE_DIS, "TRACE_DIS")
logging.addLevelName(TRACE, "TRACE")


T = TypeVar("T", bound=AutoSerdeFile)


class _LazyFile(Generic[T]):
    """Thread-safe transparent file lazy loader"""

    __path: Path
    _value: Path | T
    _lock: RLock
    _inner_cls: type[T]

    def __init__(self, inner_cls: type[T], value: Path, force_load: bool = False) -> None:
        object.__setattr__(self, "_inner_cls", inner_cls)
        if not value.exists():
            raise FileNotFoundError(value)
        object.__setattr__(self, "__LazyFile__path", value)
        object.__setattr__(self, "_value", value)
        object.__setattr__(self, "_lock", RLock())
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
                object.__setattr__(self, "_value", loaded)
            return self._value  # type: ignore  # ty:ignore[invalid-return-type]

    # Transparent attribute access
    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        return getattr(self._load(), name)

    def __setattr__(self, name: str, val: Any) -> None:  # noqa: ANN401
        setattr(self._load(), name, val)

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


class AskiffLibSym:
    path: Path
    __initial_path: Path
    objects: list[_LazyFile[SymbolFile]]
    name: str

    def __init__(self, path: Path) -> None:
        self.path = path
        self.name = path.stem
        self.__initial_path = path

    def load(self, force: bool = False) -> Self:
        if self.path.suffix == ".kicad_sym" and self.path.exists():
            self.objects = [_LazyFile(SymbolFile, self.path, force)]
            return self

        self.objects = []
        for path in self.path.glob("*.kicad_sym"):
            self.objects.append(_LazyFile(SymbolFile, path, force))
        return self

    def symbols(self) -> Generator[LibSymbol]:
        for o in self.objects:
            yield from o.symbols

    def save(self, path: Path | None = None) -> None:
        for o in self.objects:
            o.save(path, self.__initial_path)


class AskiffLibFp:
    path: Path
    __initial_path: Path
    objects: list[_LazyFile[FootprintFile]]
    name: str

    def __init__(self, path: Path) -> None:
        self.path = path
        self.name = path.stem
        self.__initial_path = path

    def load(self, force: bool = False) -> Self:
        self.objects = []
        for path in self.path.glob("*.kicad_mod"):
            self.objects.append(_LazyFile(FootprintFile, path, force))
        return self

    def save(self, path: Path | None = None) -> None:
        for o in self.objects:
            o.save(path, self.__initial_path)


class AskiffPro:
    path: Path
    __initial_path: Path
    # pro: dict[Path, Sexpr] # Note: kicad_pro seems to be json
    pcb: list[_LazyFile[Board]]
    sch: list[_LazyFile[Schematic]]

    fp: dict[str, AskiffLibFp]
    fp_lib_table: LibTableFp

    sym: dict[str, AskiffLibSym]
    sym_lib_table: LibTableSym

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

        self.sch = []
        for path in self.path.glob("*.kicad_sch"):
            self.sch.append(_LazyFile(Schematic, path, force))

        self.pcb = []
        for path in self.path.glob("*.kicad_pcb"):
            self.pcb.append(_LazyFile(Board, path, force))

        fp_lib_table_path = self.path / "fp-lib-table"
        self.fp_lib_table = LibTableFp.from_file(fp_lib_table_path) if fp_lib_table_path.exists() else LibTableFp()
        self.fp = {lib.name: AskiffLibFp(Path(self.resolve_var(lib.uri))).load(force) for lib in self.fp_lib_table.lib}

        sym_lib_table_path = self.path / "sym-lib-table"
        self.sym_lib_table = LibTableSym.from_file(sym_lib_table_path) if sym_lib_table_path.exists() else LibTableSym()
        self.sym = {
            lib.name: AskiffLibSym(Path(self.resolve_var(lib.uri))).load(force) for lib in self.sym_lib_table.lib
        }

        return self

    def save(self, path: Path | None = None) -> None:
        # for p, sexpr in self.pro.items():
        #     sexpr.to_file(p)

        for pcb in self.pcb:
            pcb.save(path, self.__initial_path)

        for sch in self.sch:
            sch.save(path, self.__initial_path)

        for fp_lib in self.fp.values():
            if path and fp_lib._AskiffLibFp__initial_path.is_relative_to(self.__initial_path):  # type: ignore # ty:ignore[unresolved-attribute]
                file = fp_lib._AskiffLibFp__initial_path.relative_to(self.__initial_path)  # type: ignore  # ty:ignore[unresolved-attribute]
                fp_lib.save(path / file)
            else:
                fp_lib.save()
        for sch_lib in self.sym.values():
            if path and sch_lib._AskiffLibSym__initial_path.is_relative_to(self.__initial_path):  # type: ignore # ty:ignore[unresolved-attribute]
                file = sch_lib._AskiffLibSym__initial_path.relative_to(self.__initial_path)  # type: ignore  # ty:ignore[unresolved-attribute]
                sch_lib.save(path / file)
            else:
                sch_lib.save()
        pass
