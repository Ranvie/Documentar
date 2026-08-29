from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Optional

from .base import LanguageResolver

_RE_CLASSMAP_ENTRY = re.compile(
    r"'((?:[^'\\]|\\.)*)'\s*=>\s*\$(vendorDir|baseDir)\s*\.\s*'((?:[^'\\]|\\.)*)'"
)
_RE_PSR4_KEY = re.compile(r"'((?:[^'\\]|\\.)*)'\s*=>\s*array\s*\(([^)]*)\)")
_RE_PSR4_DIR = re.compile(r"\$(vendorDir|baseDir)\s*\.\s*'((?:[^'\\]|\\.)*)'")

_SYMBOL_KINDS_INDEXAVEIS = ("class", "interface", "trait", "enum", "function")

_BUILTIN_CLASSES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "php_builtin_classes.txt")


def _unescape_php_string(s: str) -> str:
    return s.replace("\\\\", "\\").replace("\\'", "'")


def _load_builtin_classes(path) -> set:
    """Nomes (lowercase) das classes/interfaces/traits internas do PHP - nunca
    tem arquivo pra apontar. Ver Tools/dependency_parsers/php_builtin_classes.txt."""
    names = set()
    if not os.path.isfile(path):
        return names
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            name = line.split("#", 1)[0].strip()
            if name:
                names.add(name.lower())
    return names


_BUILTIN_CLASSES_LOWER = _load_builtin_classes(_BUILTIN_CLASSES_PATH)


def _load_composer_maps(root: str):
    """None, None se o projeto nao tiver rodado `composer install` (sem
    vendor/composer/*). Senao, (classmap: {nome_completo: caminho_abs},
    psr4: [(prefixo, [dirs_abs]), ...] ordenado do prefixo mais especifico
    pro mais generico)."""
    vendor_dir = os.path.join(root, "vendor")
    composer_dir = os.path.join(vendor_dir, "composer")
    if not os.path.isdir(composer_dir):
        return None, None

    def resolve_var(var, suffix):
        base = vendor_dir if var == "vendorDir" else root
        return os.path.normpath(base + suffix)

    classmap = {}
    classmap_path = os.path.join(composer_dir, "autoload_classmap.php")
    if os.path.isfile(classmap_path):
        with open(classmap_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        for name, var, suffix in _RE_CLASSMAP_ENTRY.findall(content):
            classmap[_unescape_php_string(name)] = resolve_var(var, _unescape_php_string(suffix))

    psr4 = []
    psr4_path = os.path.join(composer_dir, "autoload_psr4.php")
    if os.path.isfile(psr4_path):
        with open(psr4_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        for prefix, dirs_blob in _RE_PSR4_KEY.findall(content):
            dirs = [resolve_var(var, _unescape_php_string(suffix)) for var, suffix in _RE_PSR4_DIR.findall(dirs_blob)]
            if dirs:
                psr4.append((_unescape_php_string(prefix), dirs))
        psr4.sort(key=lambda item: len(item[0]), reverse=True)

    return classmap, psr4


def _psr4_lookup(qualified_name: str, psr4) -> Optional[str]:
    for prefix, dirs in psr4:
        if not qualified_name.startswith(prefix):
            continue
        remainder = qualified_name[len(prefix):].replace("\\", os.sep)
        for base_dir in dirs:
            candidate = os.path.join(base_dir, remainder + ".php")
            if os.path.isfile(candidate):
                return candidate
    return None


class PhpResolver(LanguageResolver):
    language = "php"

    def resolve(self, files: list, root: str) -> None:
        classmap, psr4 = _load_composer_maps(root)

        own_index: dict[str, str] = {}
        by_short_name: dict[str, list] = defaultdict(list)
        for file in files:
            if file["status"] != "ok":
                continue
            for symbol in file["symbols"]:
                if symbol["kind"] not in _SYMBOL_KINDS_INDEXAVEIS:
                    continue
                own_index[symbol["qualified_name"]] = file["path"]
                short_name = symbol["qualified_name"].rsplit("\\", 1)[-1]
                by_short_name[short_name].append(file["path"])

        for file in files:
            if file["status"] != "ok":
                continue

            local_alias = {}
            for imp in file["imports"]:
                if imp["kind"] in ("use", "use_function", "use_const"):
                    key = imp["alias"] or imp["raw"].rsplit("\\", 1)[-1]
                    local_alias[key] = imp["raw"]

            for imp in file["imports"]:
                raw = imp["raw"]
                if imp["kind"] == "trait_use":
                    raw = local_alias.get(raw.lstrip("\\"), raw)
                raw = raw.lstrip("\\")

                if raw.lower() in _BUILTIN_CLASSES_LOWER:
                    imp["builtin"] = True
                    continue

                imp["resolved_path"] = self._resolve_one(raw, classmap, psr4, own_index, by_short_name, root)

    def _resolve_one(self, qualified_name, classmap, psr4, own_index, by_short_name, root) -> Optional[str]:
        if classmap and qualified_name in classmap:
            return os.path.relpath(classmap[qualified_name], root).replace(os.sep, "/")
        if psr4:
            found = _psr4_lookup(qualified_name, psr4)
            if found:
                return os.path.relpath(found, root).replace(os.sep, "/")
        if qualified_name in own_index:
            return own_index[qualified_name]
        short_name = qualified_name.rsplit("\\", 1)[-1]
        candidates = by_short_name.get(short_name)
        if candidates and len(candidates) == 1:
            return candidates[0]
        return None
