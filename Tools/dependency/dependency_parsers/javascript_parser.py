from __future__ import annotations

from tree_sitter import Language, Parser
import tree_sitter_javascript as tsjs

from .base import LanguageParser, FileParseResult, Symbol, Import, ClassRef

_LANGUAGE = Language(tsjs.language())


class JavaScriptParser(LanguageParser):
    language = "javascript"

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

    def _string_literal_text(self, node, source):
        """Conteudo de dentro de um no' `string` (tira as aspas)."""
        fragment = next((c for c in node.children if c.type == "string_fragment"), None)
        return self._text(fragment, source) if fragment is not None else None

    def _class_extends(self, node, source):
        heritage = next((c for c in node.children if c.type == "class_heritage"), None)
        if heritage is None:
            return []
        target = next((c for c in heritage.children if c.type in ("identifier", "member_expression")), None)
        if target is None:
            return []
        return [ClassRef(raw=self._text(target, source))]

    def _handle_import_statement(self, node, source, imports):
        string_node = next((c for c in node.children if c.type == "string"), None)
        if string_node is None:
            return
        spec = self._string_literal_text(string_node, source)
        if spec is not None:
            imports.append(Import(kind="import", raw=spec, line=node.start_point[0] + 1))

    def _handle_call_expression(self, node, source, imports):
        callee = node.children[0] if node.children else None
        if callee is None or callee.type != "identifier" or self._text(callee, source) != "require":
            return
        arguments = next((c for c in node.children if c.type == "arguments"), None)
        if arguments is None:
            return
        first_string = next((c for c in arguments.children if c.type == "string"), None)
        if first_string is None:
            return
        spec = self._string_literal_text(first_string, source)
        if spec is not None:
            imports.append(Import(kind="require", raw=spec, line=node.start_point[0] + 1))

    def _walk(self, node, source, symbols, imports, class_name):
        if node.type == "import_statement":
            self._handle_import_statement(node, source, imports)
        elif node.type == "call_expression":
            self._handle_call_expression(node, source, imports)
        elif node.type == "class_declaration":
            name_node = next((c for c in node.children if c.type == "identifier"), None)
            if name_node is not None:
                name = self._text(name_node, source)
                extends = self._class_extends(node, source)
                symbols.append(Symbol(kind="class", name=name, qualified_name=name, line=node.start_point[0] + 1, extends=extends))
                for child in node.children:
                    self._walk(child, source, symbols, imports, class_name=name)
                return  # ja desceu com o class_name atualizado - nao desce de novo la embaixo
        elif node.type == "function_declaration":
            name_node = next((c for c in node.children if c.type == "identifier"), None)
            if name_node is not None:
                name = self._text(name_node, source)
                qualified_name = f"{class_name}.{name}" if class_name else name
                symbols.append(Symbol(kind="function", name=name, qualified_name=qualified_name, line=node.start_point[0] + 1))
        elif node.type == "method_definition":
            name_node = next((c for c in node.children if c.type == "property_identifier"), None)
            if name_node is not None:
                name = self._text(name_node, source)
                qualified_name = f"{class_name}.{name}" if class_name else name
                symbols.append(Symbol(kind="method", name=name, qualified_name=qualified_name, line=node.start_point[0] + 1))

        for child in node.children:
            self._walk(child, source, symbols, imports, class_name)
