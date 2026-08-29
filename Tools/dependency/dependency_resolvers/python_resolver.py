from __future__ import annotations

import os
import sys
from collections import defaultdict
from typing import Optional

from .base import LanguageResolver

_STDLIB_MODULES = getattr(sys, "stdlib_module_names", frozenset())


class PythonResolver(LanguageResolver):
    language = "python"

    def resolve(self, files: list, root: str) -> None:
        own_index = defaultdict(list)
        for file in files:
            if file["status"] != "ok":
                continue
            for symbol in file["symbols"]:
                own_index[symbol["name"]].append(file["path"])
            module_name = os.path.splitext(os.path.basename(file["path"]))[0]
            if module_name != "__init__":
                own_index[module_name].append(file["path"])

        for file in files:
            if file["status"] != "ok":
                continue
            file_dir = os.path.dirname(file["path"])

            for imp in file["imports"]:
                raw = imp["raw"]

                if raw.startswith("."):
                    imp["resolved_path"] = self._resolve_relative(root, file_dir, raw)
                    continue

                top_level = raw.split(".", 1)[0]
                if top_level in _STDLIB_MODULES:
                    imp["builtin"] = True
                    continue

                imp["resolved_path"] = self._resolve_dotted(root, raw, own_index)

    def _module_path_candidates(self, base_dir_abs, dotted):
        parts = [p for p in dotted.split(".") if p]
        if not parts:
            return []
        base = os.path.join(base_dir_abs, *parts)
        return [base + ".py", os.path.join(base, "__init__.py")]

    def _resolve_from_base(self, base_dir_abs, dotted, root) -> Optional[str]:
        for candidate in self._module_path_candidates(base_dir_abs, dotted):
            if os.path.isfile(candidate):
                return os.path.relpath(candidate, root).replace(os.sep, "/")

        if "." in dotted:
            parent = dotted.rsplit(".", 1)[0]
            for candidate in self._module_path_candidates(base_dir_abs, parent):
                if os.path.isfile(candidate):
                    return os.path.relpath(candidate, root).replace(os.sep, "/")

        return None

    def _resolve_dotted(self, root, dotted, own_index) -> Optional[str]:
        resolved = self._resolve_from_base(root, dotted, root)
        if resolved:
            return resolved

        short_name = dotted.rsplit(".", 1)[-1]
        candidates = own_index.get(short_name)
        if candidates and len(candidates) == 1:
            return candidates[0]
        return None

    def _resolve_relative(self, root, file_dir, raw) -> Optional[str]:
        num_dots = len(raw) - len(raw.lstrip("."))
        remainder = raw[num_dots:]

        if "." in remainder:
            pkg_path, name = remainder.rsplit(".", 1)
            levels_up = num_dots - 1
        else:
            pkg_path, name = None, remainder
            levels_up = num_dots - 2

        base_dir_abs = os.path.join(root, file_dir)
        for _ in range(max(levels_up, 0)):
            base_dir_abs = os.path.dirname(base_dir_abs)

        dotted = f"{pkg_path}.{name}" if pkg_path else name
        resolved = self._resolve_from_base(base_dir_abs, dotted, root)
        if resolved:
            return resolved

        init_candidate = os.path.join(base_dir_abs, "__init__.py")
        if os.path.isfile(init_candidate):
            return os.path.relpath(init_candidate, root).replace(os.sep, "/")

        return None
