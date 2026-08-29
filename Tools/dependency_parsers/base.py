"""Contrato comum que todo parser de linguagem (fase de EXTRACAO) segue.

A fase de RESOLUCAO (imports_raw -> caminho real de arquivo) e' uma etapa
separada, ainda nao implementada (PROJETO.md, decisao #1). Por isso
Import.resolved_path fica sempre None por enquanto.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing      import Optional


@dataclass
class Symbol:
    kind: str            # "class" | "function" | "method"
    name: str
    qualified_name: str
    line: int


@dataclass
class Import:
    kind: str             # "import" | "import_from"
    raw: str
    line: int
    resolved_path: Optional[str] = None


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
