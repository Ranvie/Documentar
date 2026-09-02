from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class Package:
    name: str
    version: Optional[str] = None
    ecosystem: str = ""
    manifest_path: str = ""
    dev: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class PackageDetector:
    ecosystem: str

    def wanted_filenames(self) -> list:
        raise NotImplementedError

    def parse(self, path: str, content: bytes) -> list:
        raise NotImplementedError
