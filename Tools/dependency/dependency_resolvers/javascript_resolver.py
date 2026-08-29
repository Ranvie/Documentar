from __future__ import annotations

import json
import os

from .base import LanguageResolver

_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue")

_TSCONFIG_CANDIDATES = ("tsconfig.app.json", "tsconfig.json")


def _load_path_aliases(root):
    for nome in _TSCONFIG_CANDIDATES:
        caminho = os.path.join(root, nome)
        if not os.path.isfile(caminho):
            continue
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        paths = config.get("compilerOptions", {}).get("paths", {})
        aliases = [(padrao.rstrip("*"), alvos[0].rstrip("*")) for padrao, alvos in paths.items() if alvos]
        if aliases:
            return aliases
    return []


class JavaScriptResolver(LanguageResolver):
    language = "javascript"

    def resolve(self, files: list, root: str) -> None:
        aliases = _load_path_aliases(root)

        for file in files:
            if file["status"] != "ok":
                continue
            file_dir = os.path.dirname(file["path"])

            for imp in file["imports"]:
                spec = imp["raw"]

                if spec.startswith("./") or spec.startswith("../"):
                    imp["resolved_path"] = self._resolve_from(root, file_dir, spec)
                    continue

                for prefixo, alvo in aliases:
                    if spec.startswith(prefixo):
                        spec_relativo_a_raiz = alvo + spec[len(prefixo):]
                        imp["resolved_path"] = self._resolve_from(root, "", spec_relativo_a_raiz)
                        break

    def _resolve_from(self, root, base_dir, spec):
        base = os.path.normpath(os.path.join(root, base_dir, spec))

        candidatos = [base]
        candidatos += [base + ext for ext in _EXTENSIONS]
        candidatos += [os.path.join(base, "index" + ext) for ext in _EXTENSIONS]

        for candidato in candidatos:
            if os.path.isfile(candidato):
                return os.path.relpath(candidato, root).replace(os.sep, "/")
        return None
