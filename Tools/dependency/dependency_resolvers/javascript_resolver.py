from __future__ import annotations

import os

from .base import LanguageResolver

_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")


class JavaScriptResolver(LanguageResolver):
    language = "javascript"

    def resolve(self, files: list, root: str) -> None:
        for file in files:
            if file["status"] != "ok":
                continue
            file_dir = os.path.dirname(file["path"])
            for imp in file["imports"]:
                spec = imp["raw"]
                if spec.startswith("./") or spec.startswith("../"):
                    imp["resolved_path"] = self._resolve_relative(root, file_dir, spec)

    def _resolve_relative(self, root, file_dir, spec):
        base = os.path.normpath(os.path.join(root, file_dir, spec))

        candidatos  = [base]
        candidatos += [base + ext for ext in _EXTENSIONS]
        candidatos += [os.path.join(base, "index" + ext) for ext in _EXTENSIONS]

        for candidato in candidatos:
            if os.path.isfile(candidato):
                return os.path.relpath(candidato, root).replace(os.sep, "/")
        return None
