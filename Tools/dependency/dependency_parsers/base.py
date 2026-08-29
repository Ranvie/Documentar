from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class ClassRef:
    raw: str
    resolved_path: Optional[str] = None
    builtin: bool = False


@dataclass
class Symbol:
    kind: str            # "class" | "function" | "method"
    name: str
    qualified_name: str
    line: int
    extends: list = field(default_factory=list)
    implements: list = field(default_factory=list)


@dataclass
class Import:
    kind: str             # "import" | "import_from"
    raw: str
    line: int
    alias: Optional[str] = None
    resolved_path: Optional[str] = None
    builtin: bool = False    # parte da linguagem/stdlib (Exception do PHP, os do Python)
    external: bool = False   # dependencia de pacote de terceiro (npm/node_modules) - nao e' a mesma coisa que builtin


@dataclass
class FileParseResult:
    path: str
    language: str
    status: str            # "ok" | "unsupported" | "error"
    symbols: list = field(default_factory=list)
    imports: list = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class LanguageParser:
    """Interface que cada dependency_parsers/<lang>_parser.py implementa."""

    language: str

    def parse(self, path: str, source: bytes) -> FileParseResult:
        raise NotImplementedError
