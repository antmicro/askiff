from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import (
    ClassVar,
    Self,
)

from askiff.const import Version
from askiff.sexpr import Sexpr

from .base_class import AutoSerde

log = logging.getLogger()


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


class AutoSerdeFile(AutoSerde):
    """`AutoSerde` wrapper that targets top (file) level structures"""

    _askiff_key: ClassVar[str]
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
                ret = cls.deserialize(Sexpr(sexp[1:]))
                ret._fs_path = path
                return ret
            raise Exception(
                f"{cls.__name__}: File {path} has unsupported version (Expects: {vmin}-{vmax}, File: {ver})"
            )

    def to_file(self, path: Path | None = None) -> None:
        path = path if path else self._fs_path
        with _Timer(f"Save `{path}`"):
            if path is None:
                raise Exception(f"Saving {type(self).__name__} to file requires specifying file system path!")

            Sexpr.to_file(Sexpr((self._askiff_key, *self.serialize())), path)
