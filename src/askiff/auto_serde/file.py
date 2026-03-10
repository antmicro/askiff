from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import (
    ClassVar,
    Self,
)

from askiff.const import Version
from askiff.sexpr import Sexpr

from .base_class import AutoSerde, _askiff_opts_default, _askiff_opts_version_map

log = logging.getLogger()

_file_serde_lock = threading.Lock()


class _Timer:
    def __init__(self, message: str = "Execution time") -> None:
        self.message = message

    def __enter__(self) -> _Timer:
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args) -> None:  # type: ignore # noqa: ANN002
        elapsed = time.perf_counter() - self.start
        time_logger = logging.getLogger("time_log")
        time_logger.info(f"{self.message}: {elapsed:.3f} seconds")


def _setup_versioned_serde_environment(version: int, latest_version: int) -> None:
    AutoSerdeFile._version = version

    for cls, versioned in _askiff_opts_version_map.items():
        params = None
        for ver, _params in versioned.items():
            matching = ver <= version
            if matching:
                params = _params
        opts = _askiff_opts_default[cls] if params is None or latest_version <= version else params

        for dict_name, val in opts.items():
            setattr(cls, dict_name, val)


class AutoSerdeFile(AutoSerde):
    """`AutoSerde` wrapper that targets top (file) level structures"""

    _askiff_key: ClassVar[str]
    version: int
    _version: int = 0
    """This version field is set on (global) class level, and used for simple access to version in any place"""
    _fs_path: Path | None = None
    __version_map: ClassVar[dict[str, str]] = {
        "kicad_pcb": "pcb",
        "kicad_sch": "sch",
        "symbol": "sym",
        "footprint": "fp",
        "sym_lib_table": "lib_table",
        "fp_lib_table": "lib_table",
    }

    @classmethod
    def from_file(cls, path: Path) -> Self:
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
                    _setup_versioned_serde_environment(ver, vmax)
                    ret = cls.deserialize(Sexpr(sexp[1:]))
                ret._fs_path = path
                return ret
            raise Exception(
                f"{cls.__name__}: File {path} has unsupported version (Expects: {vmin}-{vmax}, File: {ver})"
            )

    def to_file(self, path: Path | None = None) -> None:
        path = path if path else self._fs_path
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
