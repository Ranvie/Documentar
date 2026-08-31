from __future__ import annotations

import re

from tree_sitter import Language, Parser
import tree_sitter_php as tsphp

from .base import LanguageParser, FileParseResult, Symbol, Import, ClassRef

_LANGUAGE = Language(tsphp.language_php())

_RE_USE_LEADING_BACKSLASH = re.compile(rb"(?m)^(\s*use\s+)\\")

_DECLARATION_KIND = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "trait_declaration": "trait",
    "enum_declaration": "enum",
}

_BODY_TYPES = ("declaration_list", "enum_declaration_list")

_NAME_TYPES = ("qualified_name", "namespace_name", "name")

_TYPE_ANNOTATION_TYPES = ("named_type", "optional_type", "union_type", "intersection_type")

_PSEUDO_TYPE_NAMES = {"self", "static", "parent"}


class PhpParser(LanguageParser):
    language = "php"

    def __init__(self):
        self._parser = Parser(_LANGUAGE)

    def parse(self, path: str, source: bytes) -> FileParseResult:
        source = _RE_USE_LEADING_BACKSLASH.sub(rb"\1 ", source)
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

    def _names_in_clause(self, node, clause_type, source):
        clause = next((c for c in node.children if c.type == clause_type), None)
        if clause is None:
            return []
        return [ClassRef(raw=self._text(c, source)) for c in clause.children if c.type in _NAME_TYPES]

    def _type_names(self, type_node, source):
        if type_node is None:
            return []
        names = []

        def collect(n):
            if n.type in _NAME_TYPES:
                text = self._text(n, source)
                if text.lower() not in _PSEUDO_TYPE_NAMES:
                    names.append(text)
                return
            for c in n.children:
                collect(c)

        collect(type_node)
        return names

    def _declared_type_names(self, node, source):
        type_node = next((c for c in node.children if c.type in _TYPE_ANNOTATION_TYPES), None)
        return self._type_names(type_node, source)

    def _find_namespace(self, root, source):
        ns_node = next((c for c in root.children if c.type == "namespace_definition"), None)
        if ns_node is None:
            return None
        name_node = next((c for c in ns_node.children if c.type == "namespace_name"), None)
        return self._text(name_node, source) if name_node is not None else None

    def _walk(self, node, source, symbols, imports, namespace, class_name):
        for child in node.children:
            self._check_expr(child, source, imports)
            if child.type in _DECLARATION_KIND:
                name = self._direct_name(child, source)
                if name is None:
                    continue
                qualified_name = f"{namespace}\\{name}" if namespace else name
                extends = self._names_in_clause(child, "base_clause", source)
                implements = self._names_in_clause(child, "class_interface_clause", source)
                symbols.append(Symbol(
                    kind=_DECLARATION_KIND[child.type], name=name, qualified_name=qualified_name,
                    line=child.start_point[0] + 1, extends=extends, implements=implements,
                ))
                body = next((c for c in child.children if c.type in _BODY_TYPES), None)
                if body is not None:
                    self._walk(body, source, symbols, imports, namespace, class_name=qualified_name)
            elif child.type == "function_definition":
                name = self._direct_name(child, source)
                if name is None:
                    continue
                qualified_name = f"{namespace}\\{name}" if namespace else name
                symbols.append(Symbol(kind="function", name=name, qualified_name=qualified_name, line=child.start_point[0] + 1))
                self._handle_signature_and_body(child, source, imports)
            elif child.type == "method_declaration":
                name = self._direct_name(child, source)
                if name is None:
                    continue
                qualified_name = f"{class_name}::{name}" if class_name else name
                symbols.append(Symbol(kind="method", name=name, qualified_name=qualified_name, line=child.start_point[0] + 1))
                self._handle_signature_and_body(child, source, imports)
            elif child.type == "property_declaration":
                for type_name in self._declared_type_names(child, source):
                    imports.append(Import(kind="type_hint", raw=type_name, line=child.start_point[0] + 1))
            elif child.type == "use_declaration":
                self._handle_trait_use(child, source, imports)
            elif child.type == "namespace_use_declaration":
                self._handle_namespace_use(child, source, imports)
            else:
                self._walk(child, source, symbols, imports, namespace, class_name)

    def _handle_signature_and_body(self, node, source, imports):
        formal_params = next((c for c in node.children if c.type == "formal_parameters"), None)
        if formal_params is not None:
            for param in formal_params.children:
                if param.type in ("simple_parameter", "property_promotion_parameter", "variadic_parameter"):
                    for type_name in self._declared_type_names(param, source):
                        imports.append(Import(kind="type_hint", raw=type_name, line=param.start_point[0] + 1))

        for type_name in self._declared_type_names(node, source):
            imports.append(Import(kind="type_hint", raw=type_name, line=node.start_point[0] + 1))

        body = next((c for c in node.children if c.type == "compound_statement"), None)
        if body is not None:
            self._walk_body(body, source, imports)

    def _class_before_scope_operator(self, node, source):
        idx = next((i for i, c in enumerate(node.children) if c.type == "::"), None)
        if idx is None:
            return None
        target = next((c for c in node.children[:idx] if c.type in _NAME_TYPES), None)
        return self._text(target, source) if target is not None else None

    def _check_expr(self, node, source, imports):
        line = node.start_point[0] + 1

        if node.type == "object_creation_expression":
            target = next((c for c in node.children if c.type in _NAME_TYPES), None)
            if target is not None:
                name = self._text(target, source)
                if name.lower() not in _PSEUDO_TYPE_NAMES:
                    imports.append(Import(kind="new", raw=name, line=line))
        elif node.type == "scoped_call_expression":
            target = self._class_before_scope_operator(node, source)
            if target is not None:
                imports.append(Import(kind="static_call", raw=target, line=line))
        elif node.type == "class_constant_access_expression":
            target = self._class_before_scope_operator(node, source)
            if target is not None:
                imports.append(Import(kind="class_const_access", raw=target, line=line))
        elif node.type == "binary_expression" and any(c.type == "instanceof" for c in node.children):
            instanceof_idx = next(i for i, c in enumerate(node.children) if c.type == "instanceof")
            target = next((c for c in node.children[instanceof_idx + 1:] if c.type in _NAME_TYPES), None)
            if target is not None:
                imports.append(Import(kind="instanceof", raw=self._text(target, source), line=line))
        elif node.type == "type_list":  # tipo(s) de excecao de um `catch (A | B $e)`
            for type_name in self._type_names(node, source):
                imports.append(Import(kind="catch_type", raw=type_name, line=line))

    def _walk_body(self, node, source, imports):
        self._check_expr(node, source, imports)
        for child in node.children:
            self._walk_body(child, source, imports)

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
