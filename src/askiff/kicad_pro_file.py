from __future__ import annotations

import json
from os import PathLike
from pathlib import Path
from threading import RLock
from typing import Any


class KicadProFile:
    """A class that represents a .kicad_pro file"""

    fs_path: Path
    project_name: str

    _kicad_pro_json: dict[str, Any] | None
    _lock: RLock

    @property
    def kicad_pro_json(self) -> dict[str, Any]:
        return self._load_kicad_pro()

    def __init__(
        self,
        fs_path: Path,
        project_name: str | None = None,
        *,
        kicad_pro_json: dict[str, Any] | None = None,
        force: bool = False,
    ) -> None:
        self.fs_path = fs_path
        self.project_name = project_name if project_name is not None else fs_path.stem
        self._lock = RLock()

        if kicad_pro_json is not None:
            self._kicad_pro_json = kicad_pro_json
        else:
            self._kicad_pro_json = None

            if force:
                self._load_kicad_pro()

    def _load_kicad_pro(self) -> dict[str, Any]:
        # Double-checked lock
        if self._kicad_pro_json is None:
            with self._lock:
                if self._kicad_pro_json is None:
                    with open(self.fs_path) as f:
                        kicad_pro_json = json.load(f)

                    self._kicad_pro_json = kicad_pro_json or {}

        assert self._kicad_pro_json is not None
        return self._kicad_pro_json

    @classmethod
    def load(cls, fs_path: Path, *, force: bool = False, strict: bool = True) -> KicadProFile:
        """Load a .kicad_pro file

        Args:
            fs_path: the path of the .kicad_pro file
            force: if `True`, immediately load the .kicad_pro file
            strict: if `True`, raise exceptions if file doesn't exist

        Returns:
            KicadProFile
        """
        if strict:
            if not fs_path.exists():
                raise FileNotFoundError("Project file not found!")

            if not fs_path.is_file():
                raise FileNotFoundError("Project file is not a file!")

            if not fs_path.suffix == ".kicad_pro":
                raise ValueError("Project file's extension is not `.kicad_pro`!")

        if not fs_path.exists():
            return KicadProFile(fs_path, kicad_pro_json={})

        return KicadProFile(fs_path, force=force)

    def save(self, path: PathLike | None = None) -> None:
        """Save the .kicad_pro file

        Args:
            path: if provided, the .kicad_pro file is saved in the path given.
                Otherwise, the file is saved in its original location.
        """

        path = Path(path) if path else self.fs_path

        if self._kicad_pro_json is not None:
            with self._lock, open(path, "w") as f:
                json.dump(self._kicad_pro_json, f, indent=2)
                f.write("\n")
