from __future__ import annotations

import logging
from collections.abc import Generator
from os import PathLike
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
    """Thread-safe lazy loader for KiCad files.
    Defers loading until first access, supporting transparent attribute access and saving relative to a root path.
    """

    __path: Path
    """Path to the KiCad file on disk."""
    _value: Path | T
    """Path to the KiCad file OR parsed file."""
    _lock: RLock
    _inner_cls: type[T]

    def __init__(self, inner_cls: type[T], path: PathLike, force_load: bool = False, value: T | None = None) -> None:
        """Initializes the lazy loader. Loads the file immediately if `force_load` is True"""
        path = Path(path)
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
        """Loads and returns the underlying file object, caching the result after the first access.
        Uses thread-safe loading with a lock to prevent concurrent access during loading."""
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

    def save(self, path: PathLike | None, initial_root_path: Path) -> None:
        """Saves the file to disk. Does nothing if file has not been loaded

        Arguments:
            path: if provided, files are saved relative to that directory.
                Otherwise, files are saved in their original locations.
            initial_root_path: folder from which original file was loaded,
                used to get relative directory, when saving to different than original path
        """
        path = Path(path) if path else None
        if not self.is_loaded():
            return

        if path and self.__path.is_relative_to(initial_root_path):
            file = self.__path.relative_to(initial_root_path)
            self.to_file(path=path / file)
        else:
            self.to_file()

    def is_loaded(self) -> bool:
        """Returns True if the file has been loaded into memory, False if it is still represented as a path."""
        return not isinstance(self._value, Path)


class AskiffLibSym:
    """Manage a KiCad symbol library, loading and saving LibSymbol objects from .kicad_sym files.
        Transparently handles both library-per-file and library-per-directory styles

    Examples:
        Create new library & Add new symbol to library
        >>> from askiff.symbol import LibSymbol
        >>> from askiff.pro import AskiffLibSym
        >>> new_lib_path = Path("test.kicad_sym")  # library-per-file structure
        >>> # new_lib_path = Path("test") # library-per-folder structure
        >>> lib = AskiffLibSym(new_lib_path)  # Create new library
        >>> new_symbol = LibSymbol()  # Create new symbol
        >>> lib["symbol_name"] = new_symbol  # Add new symbol (or modify existing) to library
        >>> lib.save()  # save library changes to disk
        >>> print(new_lib_path.exists())
        True

        Iterate over symbols in library
        >>> # doctest: +SKIP
        >>> from askiff.pro import AskiffLibSym
        >>> lib = AskiffLibSym("path/to/library")  # Load library
        >>> for sym in lib.symbols:
        >>>     print(sym.lib_id)

        Get symbol by name & modify it in library
        >>> # doctest: +SKIP
        >>> from askiff.pro import AskiffLibSym
        >>> lib = AskiffLibSym("path/to/library")  # Load library
        >>> sym = lib["symbol_name"]
        >>> sym.in_bom = False
        >>> lib.save()
    """

    path: Path
    """Path to library directory or file file."""
    __initial_path: Path
    """Original file path this library was loaded from."""
    objects: list[_LazyFile[SymbolFile]]
    """List of lazy-loaded files in the library"""
    name: str
    """Library name"""

    def __init__(self, path: PathLike) -> None:
        """Initialize an AskiffLibSym instance.

        Args:
            path: Path to the library directory or library file (`kicad_sym`).
        """
        path = Path(path)
        self.path = path
        self.name = path.stem
        self.__initial_path = path
        self.objects = []

    def load(self, force: bool = False) -> Self:
        """Lazy-load symbol library

        Transparently handles both library-per-file and library-per-directory styles,
        depending if library path points to directory or a `.kicad_sym` file

        Args:
            force: if `True`, immediately load lazy-loaded files

        Returns:
            Self, for method chaining.
        """
        if self.path.suffix == ".kicad_sym" and self.path.exists():
            self.objects = [_LazyFile(SymbolFile, self.path, force)]
            return self

        self.objects = []
        for path in self.path.glob("*.kicad_sym"):
            self.objects.append(_LazyFile(SymbolFile, path, force))
        return self

    def symbols(self) -> Generator[LibSymbol]:
        """Returns a generator yielding all symbols contained within the library."""
        for o in self.objects:
            yield from o.symbols

    def save(self, path: PathLike | None = None) -> None:
        """Saves all library symbol objects managed by this instance to disk.

        Arguments:
            path: if provided, files are saved relative to that directory.
                Otherwise, files are saved in their original locations."""
        path = Path(path) if path else None
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
    """Manage a KiCad footprint library, loading and saving FootprintFile objects from .kicad_mod files.

    Examples:
        Create new library & Add new footprint to library
        >>> from askiff.footprint import FootprintFile
        >>> from askiff.pro import AskiffLibFp
        >>> new_lib_path = Path("path/to/library/folder")
        >>> lib = AskiffLibFp(new_lib_path)  # Create new library
        >>> new_fp = FootprintFile()  # Create new footprint
        >>> lib["footprint_name"] = new_fp  # Add new footprint (or modify existing) to library
        >>> lib.save()  # save library changes to disk
        >>> print(new_lib_path.exists())
        True

        Iterate over footprints in library
        >>> # doctest: +SKIP
        >>> from askiff.pro import AskiffLibFp
        >>> lib = AskiffLibFp("path/to/library")  # Load library
        >>> for fp in lib.objects:
        >>>     print(fp.lib_id)

        Get footprint by name & modify it in library
        >>> # doctest: +SKIP
        >>> from askiff.pro import AskiffLibFp
        >>> lib = AskiffLibFp("path/to/library")  # Load library
        >>> fp = lib["footprint_name"]
        >>> fp.attributes.board_only = False
        >>> lib.save()
    """

    path: Path
    """Path to the footprint library directory."""
    __initial_path: Path
    """Original path to the footprint library directory."""
    objects: list[_LazyFile[FootprintFile]]
    """List of lazy-loaded footprint files in the library."""
    name: str
    """Library name"""

    def __init__(self, path: PathLike) -> None:
        """Initialize an AskiffLibFp instance

        Args:
            path: Path to library folder
        """
        path = Path(path)
        self.path = path
        self.name = path.stem
        self.__initial_path = path
        self.objects = []

    def load(self, force: bool = False) -> Self:
        """Lazy-load footprint files from the library directory.

        Discovers all `.kicad_mod` files found in the library path and creates lazy-loaded `_LazyFile` objects for each

        Args:
            force: if `True`, immediately load lazy-loaded files

        Returns:
            Self, for method chaining.
        """
        self.objects = []
        for path in self.path.glob("*.kicad_mod"):
            self.objects.append(_LazyFile(FootprintFile, path, force))
        return self

    def save(self, path: PathLike | None = None) -> None:
        """Saves all library footprint objects managed by this instance to disk.

        Arguments:
            path: if provided, files are saved relative to that directory.
                Otherwise, files are saved in their original locations."""
        path = Path(path) if path else None
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

    Examples:

        >>> # doctest: +SKIP
        >>> from askiff import AskiffPro
        >>>
        >>> # Load a KiCad project
        >>> project = AskiffPro("path/to/project").load()
        >>>
        >>> # Load footprint (from project library)
        >>> footprint = project.fp["ResistorLib"]["Resistor0402"]
        >>>
        >>> # Add footprint to board
        >>> project.pcb[0].add_footprint(footprint, reference="R1", position=Position(15, 20))
        >>>
        >>> # Save the project
        >>> project.save()
    """

    path: Path
    """Path to project's folder"""

    __initial_path: Path
    """Path from which the project was loaded"""

    project_name: str | None = None
    """Project name - retrieved from kicad_pro file name"""

    # pro: dict[Path, Sexpr] # Note: kicad_pro seems to be json
    pcb: list[_LazyFile[Board]]
    """PCB files in the KiCad project directory"""
    sch: list[_LazyFile[Schematic]]
    """Schematic files in the KiCad project"""

    fp: dict[str, AskiffLibFp]
    """Lazy loaded footprint libraries"""
    fp_lib_table: LibTableFp
    """Footprint library table file contents"""

    sym: dict[str, AskiffLibSym]
    """Lazy loaded symbol libraries"""
    sym_lib_table: LibTableSym
    """Symbol library table file contents"""

    variables: dict[str, str]
    """KiCad variables AskiffPro is able to resolve"""

    def __init__(self, path: PathLike) -> None:
        """Initialize an AskiffPro instance for managing KiCad project files in the given directory path.
        Sets up internal state including the project directory, initial path, and default project variables.

        Args:
            path: Path to the KiCad project directory.
        """
        path = Path(path)
        self.path = path
        self.__initial_path = path
        self.variables = {"KIPRJMOD": str(path)}

    def resolve_var(self, string: str) -> str:
        """Resolves variables in a string by replacing placeholders of the form `${var}`
        with their corresponding values from the project's variables dictionary."""
        for var, subst in self.variables.items():
            string = string.replace("${" + var + "}", subst)
        return string

    def __discover_child_sch(self, sch: Path, force: bool = False) -> None:
        """Discover and load schematic files referenced by a KiCad project.
        Recursively loads child schematics based on hierarchical sub-sheets, avoiding duplicate loads."""
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
        """Discover project relevant files in `AskiffPro.path` directory.

        Loads schematics (to discover hierarchy) and library tables.
        Initializes lazy-loaders for PCB & library files

        Args:
            force: if `True`, immediately load lazy-loaded files
        """
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

    def save(self, path: PathLike | None = None) -> None:
        """Saves all loaded KiCad files managed by this instance to disk.

        Args:
            path: if provided, files are saved relative to that directory.
                Otherwise, files are saved in their original locations."""
        path = Path(path) if path else None

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
