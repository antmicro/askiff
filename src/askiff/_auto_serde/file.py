from __future__ import annotations

import logging
import threading
import time
from os import PathLike
from pathlib import Path
from typing import (
    ClassVar,
    Self,
)

from askiff._sexpr import Sexpr
from askiff.const import Version

from .base_class import AutoSerde, _askiff_opts_default, _askiff_opts_version_map
from .helpers import F

log = logging.getLogger()

_file_serde_lock = threading.Lock()


class _Timer:
    """Context manager for measuring execution duration with customizable message."""

    def __init__(self, message: str = "Execution time") -> None:
        """Initializes the timer with an optional message prefix.

        Args:
            message: Prefix for timer output message. Defaults to "Execution time".
        """
        self.message = message

    def __enter__(self) -> _Timer:
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args) -> None:  # type: ignore # noqa: ANN002
        elapsed = time.perf_counter() - self.start
        log_name = "time_log"
        if log_name in logging.Logger.manager.loggerDict:
            time_logger = logging.getLogger(log_name)
            time_logger.info(f"{self.message}: {elapsed:.3f} seconds")


def _setup_versioned_serde_environment(version: int, latest_version: int) -> None:
    """Configures globally serialization/deserialization behavior for a KiCad file version.
    Sets version-specific field options on classes in `_askiff_opts_version_map`
    to ensure correct handling of versioned data during (de)serialization.

    Args:
        version: The KiCad file version being processed.
        latest_version: The latest supported version for determining default options.
    """
    AutoSerdeFile._version = version

    for cls, versioned in _askiff_opts_version_map.items():
        params = None
        for ver, _params in versioned.items():
            matching = ver >= version
            if matching:
                params = _params
        opts = _askiff_opts_default[cls] if params is None or latest_version <= version else params

        for dict_name, val in opts.items():
            setattr(cls, dict_name, val)


class AutoSerdeFile(AutoSerde):
    """Base class for loading and saving KiCad project files with version validation and automatic file path handling.
    Subclasses define specific KiCad file types such as schematics, PCBs, and footprints.
    """

    _askiff_key: ClassVar[str]
    version: int
    """KiCad file format revision number. See also :class:`askiff.const.Version`"""
    _version: int = 0
    _post_final_deser_objects: list = F(list, skip=True)
    """
    # Dev notes:
    This version field is set on (global) class level.
    Objects can register themselves for additional processing after whole deserialization is completed
    Allowing field deserialization to access data from other file parts
    """
    _fs_path: Path | None = None
    __version_map: ClassVar[dict[str, str]] = {
        "kicad_pcb": "pcb",
        "kicad_sch": "sch",
        "kicad_symbol_lib": "sym",
        "footprint": "fp",
        "sym_lib_table": "lib_table",
        "fp_lib_table": "lib_table",
    }
    """Map between file identifier (first token in file) and corresponding field in :class:`askiff.const.Version`"""

    @classmethod
    def from_file(cls, path: PathLike) -> Self:
        """Load a KiCad file from the given path and deserialize it into a structured Python object.

        Examples:
            >>> from askiff import Board
            >>> from pathlib import Path
            >>> Board.from_file(Path.cwd() / "test.kicad_pcb")  # doctest: +SKIP

        # Dev notes:
        Validates the file type using the class's `_askiff_key` and ensures the file version is supported.
        Handles version-specific deserialization logic and performs post-deserialization setup."""
        path = Path(path)
        with _Timer(f"Load `{path}`"):
            sexp = Sexpr.from_file(path)
            askiff_key = cls._askiff_key
            if askiff_key != sexp[0]:
                raise Exception(f"{cls.__name__}: File {path} is not valid ")
            ver_key = cls.__version_map[askiff_key]
            raw_ver = [
                int(x[1]) for x in sexp[:5] if isinstance(x, list) and x[0] == "version" and isinstance(x[1], str)
            ]
            ver = raw_ver[0] if raw_ver else 0

            vmin, vmax = getattr(Version.MIN, ver_key), getattr(Version.MAX, ver_key)
            if vmin <= ver <= vmax:
                with _file_serde_lock:
                    AutoSerdeFile._post_final_deser_objects = []
                    _setup_versioned_serde_environment(ver, vmax)
                    ret = cls.deserialize(Sexpr(sexp[1:]))
                    for obj in AutoSerdeFile._post_final_deser_objects:
                        obj._post_final_deser(ret)

                ret._fs_path = path
                return ret
            raise Exception(
                f"{cls.__name__}: File {path} has unsupported version (Expects: {vmin}-{vmax}, File: {ver})"
            )

    def to_file(self, path: PathLike | None = None) -> None:
        """Save the current object to a KiCad file at the specified path.
        If no path is given, uses path from which file was loaded.
        Ensures correct serialization for the object's version and writes data in KiCad's sexpr format.

        Examples:
            >>> from askiff import Board
            >>> from pathlib import Path
            >>> board = Board.from_file(Path.cwd() / "test.kicad_pcb")  # doctest: +SKIP
            >>> board.to_file()  # doctest: +SKIP
        """
        path = Path(path) if path else self._fs_path
        with _Timer(f"Save `{path}`"):
            ver_key = self.__version_map[self._askiff_key]
            latest_version = getattr(Version.MAX, ver_key)
            if path is None:
                raise Exception(f"Saving {type(self).__name__} to file requires specifying file system path!")
            with _file_serde_lock:
                # serialization is CPU bound, so threading is unlikely to bring benefit anyway
                _setup_versioned_serde_environment(self.version, latest_version)
                sexpr = Sexpr((self._askiff_key, *self.serialize()))
            Sexpr.to_file(sexpr, path)
