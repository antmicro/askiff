from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path
from threading import RLock
from typing import Any, Generic, Self, TypeVar

from ._auto_serde import AutoSerdeFile
from .board import Board
from .const import TRACE, TRACE_DIS
from .footprint import FootprintFile, LibTableFp
from .schematic import Schematic
from .symbol import LibSymbol, LibTableSym, SymbolFile

logging.addLevelName(TRACE_DIS, "TRACE_DIS")
logging.addLevelName(TRACE, "TRACE")


T = TypeVar("T", bound=AutoSerdeFile)


class _LazyFile(Generic[T]):
    """Thread-safe transparent file lazy loader"""

    __path: Path
    _value: Path | T
    _lock: RLock
    _inner_cls: type[T]

    def __init__(self, inner_cls: type[T], path: Path, force_load: bool = False, value: T | None = None) -> None:
        object.__setattr__(self, "_inner_cls", inner_cls)
        if not path.exists() and value is None:
            raise FileNotFoundError(value)
        object.__setattr__(self, "__LazyFile__path", path)
        object.__setattr__(self, "_value", path if value is None else value)
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
        self.objects = []

    def load(self, force: bool = False) -> Self:
        if self.path.suffix == ".kicad_sym" and self.path.exists():
            self.objects = [_LazyFile(SymbolFile, self.path, force)]
            return self

        for path in self.path.glob("*.kicad_sym"):
            self.objects.append(_LazyFile(SymbolFile, path, force))
        return self

    def symbols(self) -> Generator[LibSymbol]:
        for o in self.objects:
            yield from o.symbols

    def save(self, path: Path | None = None) -> None:
        for o in self.objects:
            o.save(path, self.__initial_path)

    def __getitem__(self, index: str) -> LibSymbol:
        return next(sym for sym in self.symbols() if sym.lib_id.name == index)

    def __setitem__(self, index: str, value: LibSymbol) -> None:
        value.lib_id.name = index
        for sym in self.symbols():
            if sym.lib_id.name == index:
                sym = value
                return

        # Add footprint to library
        if self.path.suffix == ".kicad_sym":
            # Multiple symbols per file library style
            if self.objects:
                self.objects[0].symbols.append(value)
            else:
                sym_file = SymbolFile(_fs_path=self.path)
                sym_file.symbols.append(value)
                self.objects.append(_LazyFile(SymbolFile, path=self.path, value=sym_file))
        else:
            # Symbol per file library style
            path = self.path / f"{index}.kicad_sym"
            sym_file = SymbolFile(_fs_path=path)
            sym_file.symbols.append(value)
            self.objects.append(_LazyFile(SymbolFile, path=path, value=sym_file))


class AskiffLibFp:
    path: Path
    __initial_path: Path
    objects: list[_LazyFile[FootprintFile]]
    name: str

    def __init__(self, path: Path) -> None:
        self.path = path
        self.name = path.stem
        self.__initial_path = path
        self.objects = []

    def load(self, force: bool = False) -> Self:
        for path in self.path.glob("*.kicad_mod"):
            self.objects.append(_LazyFile(FootprintFile, path, force))
        return self

    def save(self, path: Path | None = None) -> None:
        for o in self.objects:
            o.save(path, self.__initial_path)

    def __getitem__(self, index: str) -> FootprintFile:
        return next(fp for fp in self.objects if fp.lib_id.name == index)._load()

    def __setitem__(self, index: str, value: FootprintFile) -> None:
        value.lib_id.name = index
        for fp in self.objects:
            if fp.lib_id.name == index:
                fp._value = value
                return

        # Add footprint to library
        self.objects.append(_LazyFile(FootprintFile, path=self.path / f"{index}.kicad_mod", value=value))


class AskiffPro:
    """Manage KiCad project files in a directory

    Automatically discovers and lazy loads found schematics, PCBs, footprints, and symbols.
    """

    path: Path
    """Path to project's folder"""

    __initial_path: Path
    """Path from which the project was loaded"""

    project_name: str | None = None
    """Project name - retrieved from kicad_pro file name"""

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

    def __discover_child_sch(self, sch: Path, force: bool = False) -> None:
        if sch.exists():
            self.sch_root = _LazyFile(Schematic, sch, force)
            self.sch.append(self.sch_root)
            for sheet in self.sch_root.sheets:
                child_sch_path = sch.parent / sheet.properties.get("Sheetfile").value
                if [True for sch in self.sch if child_sch_path == sch._fs_path]:
                    # if file already loaded, skip it
                    continue
                self.__discover_child_sch(child_sch_path, force)

    def load(self, force: bool = False) -> Self:
        pro_path = next((p for p in self.path.glob("*.kicad_pro")), None)
        if pro_path:
            self.project_name = pro_path.stem

        self.sch = []
        if pro_path:
            sch_root_path = pro_path.with_suffix(".kicad_sch")
            self.__discover_child_sch(sch_root_path, force)
        else:
            # If there is not project file, load all sch in directory
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
