from __future__ import annotations

from tree_sitter import Language, Parser
import tree_sitter_python as tspython

from .base import LanguageParser, FileParseResult, Symbol, Import

_LANGUAGE = Language(tspython.language())


class PythonParser(LanguageParser):
    language = "python"

    def __init__(self):
        self._parser = Parser(_LANGUAGE)

    def parse(self, path: str, source: bytes) -> FileParseResult:
        tree = self._parser.parse(source)
        symbols: list[Symbol] = []
        imports: list[Import] = []
        self._walk(tree.root_node, source, symbols, imports, class_name=None)
        return FileParseResult(path=path, language=self.language, status="ok", symbols=symbols, imports=imports)

    def _text(self, node, source: bytes) -> str:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _alias_of(self, aliased_import_node, source):
        alias_node = next((c for c in aliased_import_node.children if c.type == "identifier"), None)
        return self._text(alias_node, source) if alias_node is not None else None

    def _walk(self, node, source, symbols, imports, class_name):
        for child in node.children:
            if child.type == "class_definition":
                name = self._text(child.child_by_field_name("name"), source)
                symbols.append(Symbol(kind="class", name=name, qualified_name=name, line=child.start_point[0] + 1))
                body = child.child_by_field_name("body")
                if body is not None:
                    self._walk(body, source, symbols, imports, class_name=name)
            elif child.type == "function_definition":
                name = self._text(child.child_by_field_name("name"), source)
                qualified_name = f"{class_name}.{name}" if class_name else name
                kind = "method" if class_name else "function"
                symbols.append(Symbol(kind=kind, name=name, qualified_name=qualified_name, line=child.start_point[0] + 1))
                # nao desce no corpo da funcao (ver docstring do modulo)
            elif child.type == "import_statement":
                self._handle_import(child, source, imports)
            elif child.type == "import_from_statement":
                self._handle_import_from(child, source, imports)
            else:
                # continua descendo em nos estruturais genericos (if/try/decorated_definition/...)
                # pra achar classes/imports que nao estao direto na raiz do modulo
                self._walk(child, source, symbols, imports, class_name)

    def _handle_import(self, node, source, imports):
        line = node.start_point[0] + 1
        for child in node.children:
            if child.type == "dotted_name":
                imports.append(Import(kind="import", raw=self._text(child, source), line=line))
            elif child.type == "aliased_import":
                target = next((c for c in child.children if c.type == "dotted_name"), None)
                if target is not None:
                    imports.append(Import(kind="import", raw=self._text(target, source), line=line, alias=self._alias_of(child, source)))

    def _handle_import_from(self, node, source, imports):
        line = node.start_point[0] + 1
        children = node.children
        import_idx = next((i for i, c in enumerate(children) if c.type == "import"), None)
        if import_idx is None:
            return

        module = ""
        for c in children[:import_idx]:
            if c.type in ("dotted_name", "relative_import"):
                module = self._text(c, source)

        def raw_with_module(name):
            return f"{module}.{name}" if module else name

        for c in children[import_idx + 1:]:
            if c.type == "dotted_name":
                imports.append(Import(kind="import_from", raw=raw_with_module(self._text(c, source)), line=line))
            elif c.type == "aliased_import":
                target = next((cc for cc in c.children if cc.type == "dotted_name"), None)
                if target is not None:
                    imports.append(Import(kind="import_from", raw=raw_with_module(self._text(target, source)), line=line, alias=self._alias_of(c, source)))
            elif c.type == "wildcard_import":
                imports.append(Import(kind="import_from", raw=raw_with_module("*"), line=line))
