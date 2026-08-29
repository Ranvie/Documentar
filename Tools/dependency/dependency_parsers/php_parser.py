from __future__ import annotations

from tree_sitter import Language, Parser
import tree_sitter_php as tsphp

from .base import LanguageParser, FileParseResult, Symbol, Import

_LANGUAGE = Language(tsphp.language_php())

_DECLARATION_KIND = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "trait_declaration": "trait",
    "enum_declaration": "enum",
}

_BODY_TYPES = ("declaration_list", "enum_declaration_list")

_NAME_TYPES = ("qualified_name", "namespace_name", "name")


class PhpParser(LanguageParser):
    language = "php"

    def __init__(self):
        self._parser = Parser(_LANGUAGE)

    def parse(self, path: str, source: bytes) -> FileParseResult:
        tree = self._parser.parse(source)
        symbols: list[Symbol] = []
        imports: list[Import] = []
        namespace = self._find_namespace(tree.root_node, source)
        self._walk(tree.root_node, source, symbols, imports, namespace=namespace, class_name=None)
        return FileParseResult(path=path, language=self.language, status="ok", symbols=symbols, imports=imports)

    def _text(self, node, source: bytes) -> str:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _direct_name(self, node, source):
        name_node = next((c for c in node.children if c.type == "name"), None)
        return self._text(name_node, source) if name_node is not None else None

    def _find_namespace(self, root, source):
        ns_node = next((c for c in root.children if c.type == "namespace_definition"), None)
        if ns_node is None:
            return None
        name_node = next((c for c in ns_node.children if c.type == "namespace_name"), None)
        return self._text(name_node, source) if name_node is not None else None

    def _walk(self, node, source, symbols, imports, namespace, class_name):
        for child in node.children:
            if child.type in _DECLARATION_KIND:
                name = self._direct_name(child, source)
                if name is None:
                    continue
                qualified_name = f"{namespace}\\{name}" if namespace else name
                symbols.append(Symbol(kind=_DECLARATION_KIND[child.type], name=name, qualified_name=qualified_name, line=child.start_point[0] + 1))
                body = next((c for c in child.children if c.type in _BODY_TYPES), None)
                if body is not None:
                    self._walk(body, source, symbols, imports, namespace, class_name=qualified_name)
            elif child.type == "function_definition":
                name = self._direct_name(child, source)
                if name is None:
                    continue
                qualified_name = f"{namespace}\\{name}" if namespace else name
                symbols.append(Symbol(kind="function", name=name, qualified_name=qualified_name, line=child.start_point[0] + 1))
                # nao desce no corpo da funcao (ver docstring do modulo)
            elif child.type == "method_declaration":
                name = self._direct_name(child, source)
                if name is None:
                    continue
                qualified_name = f"{class_name}::{name}" if class_name else name
                symbols.append(Symbol(kind="method", name=name, qualified_name=qualified_name, line=child.start_point[0] + 1))
                # nao desce no corpo do metodo
            elif child.type == "use_declaration":
                self._handle_trait_use(child, source, imports)
            elif child.type == "namespace_use_declaration":
                self._handle_namespace_use(child, source, imports)
            else:
                # continua descendo em nos estruturais genericos (namespace com
                # bloco, if/match/attribute_list/...) pra achar declaracoes que
                # nao estao direto na raiz do arquivo
                self._walk(child, source, symbols, imports, namespace, class_name)

    def _handle_trait_use(self, node, source, imports):
        line = node.start_point[0] + 1
        for child in node.children:
            if child.type in ("name", "qualified_name"):
                imports.append(Import(kind="trait_use", raw=self._text(child, source), line=line))

    def _handle_namespace_use(self, node, source, imports):
        line = node.start_point[0] + 1
        group = next((c for c in node.children if c.type == "namespace_use_group"), None)
        if group is not None:
            prefix_node = next((c for c in node.children if c.type == "namespace_name"), None)
            prefix = self._text(prefix_node, source) + "\\" if prefix_node is not None else ""
            clauses = [c for c in group.children if c.type == "namespace_use_clause"]
        else:
            prefix = ""
            clauses = [c for c in node.children if c.type == "namespace_use_clause"]

        for clause in clauses:
            name_node = next((c for c in clause.children if c.type in _NAME_TYPES), None)
            if name_node is None:
                continue
            raw = prefix + self._text(name_node, source)

            if any(c.type == "function" for c in clause.children):
                kind = "use_function"
            elif any(c.type == "const" for c in clause.children):
                kind = "use_const"
            else:
                kind = "use"

            alias = None
            if any(c.type == "as" for c in clause.children):
                as_idx = next(i for i, c in enumerate(clause.children) if c.type == "as")
                alias_node = next((c for c in clause.children[as_idx + 1:] if c.type == "name"), None)
                if alias_node is not None:
                    alias = self._text(alias_node, source)

            imports.append(Import(kind=kind, raw=raw, line=line, alias=alias))
