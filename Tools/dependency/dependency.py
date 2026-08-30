#!/usr/bin/env python3
"""Roteador do mapeador de dependencias.

Uso:
  python Tools/dependency/dependency.py [root_dir]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__)) # Tools/dependency
_TOOLS_DIR = os.path.dirname(_HERE)                # Tools
sys.path.insert(0, _TOOLS_DIR)

from metadata import Metadata
from language_support import LANGUAGE_SUPPORT

EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".php": "php",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".vue": "vue",
}

PROJECT_ROOT = os.path.dirname(_TOOLS_DIR) # raiz do repo Documentar
DEFAULT_IGNORED_FOLDERS_FILE = os.path.join(PROJECT_ROOT, "ignored_folders.txt")
ARTIFACTS_DIR = os.path.join(PROJECT_ROOT, "artifacts")


def load_ignored_folders(path):
    if not os.path.isfile(path):
        sys.exit(f"Arquivo de pastas ignoradas nao encontrado: {path}")
    ignored = set()
    with open(path, "r", encoding="utf-8") as f:
        for linha in f:
            nome = linha.split("#", 1)[0].strip()
            if nome:
                ignored.add(nome)
    return ignored


def list_files(root, excluded):
    for current, subdirs, files in os.walk(root):
        subdirs[:] = [d for d in subdirs if d not in excluded and not d.startswith(".")]
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext not in EXTENSION_TO_LANGUAGE:
                continue
            yield os.path.join(current, name), EXTENSION_TO_LANGUAGE[ext]


def process_file(absolute_path, relative_path, language):
    parser = LANGUAGE_SUPPORT.parsers().get(language)
    if parser is None:
        return {
            "path": relative_path, "language": language, "status": "unsupported",
            "symbols": [], "imports": [], "error": None,
        }
    try:
        with open(absolute_path, "rb") as f:
            source = f.read()
    except OSError as e:
        return {
            "path": relative_path, "language": language, "status": "error",
            "symbols": [], "imports": [], "error": str(e),
        }
    try:
        result = parser.parse(relative_path, source)
    except Exception as e:  # parser de linguagem especifica pode falhar em sintaxe inesperada
        return {
            "path": relative_path, "language": language, "status": "error",
            "symbols": [], "imports": [], "error": str(e),
        }
    return result.to_dict()


def main():
    ap = argparse.ArgumentParser(description="Roteador do mapeador de dependencias (extracao + resolucao).")
    ap.add_argument("root", nargs="?", default=".", help="Pasta raiz a escanear (default: .)")
    ap.add_argument("--project-name", default=None, help="Nome do projeto pra organizar os artefatos (default: nome da pasta raiz escaneada)")
    ap.add_argument("--out-dir", default=None, help="Pasta de saida (default: {raiz do repo}/artifacts/{projeto}/auto-generated/out-dependencies)")
    ap.add_argument("--exclude", default="", help="Pastas extras a ignorar, separadas por virgula")
    ap.add_argument("--ignored-folders-file", default=DEFAULT_IGNORED_FOLDERS_FILE, help="Arquivo com a lista de pastas puladas (default: ignored_folders.txt na raiz do projeto)")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    project_name = args.project_name or os.path.basename(root.rstrip(os.sep).rstrip("/"))
    out_dir = args.out_dir or os.path.join(ARTIFACTS_DIR, project_name, "auto-generated", "out-dependencies")
    extra_dirs = {d.strip() for d in args.exclude.split(",") if d.strip()}
    excluded = load_ignored_folders(args.ignored_folders_file) | extra_dirs

    print(f"Escaneando {root} ...", file=sys.stderr)
    files = list(list_files(root, excluded))
    print(f"{len(files)} arquivo(s) reconhecido(s). Processando...", file=sys.stderr)

    results = []
    status_counts = {}
    for absolute_path, language in files:
        relative_path = os.path.relpath(absolute_path, root).replace(os.sep, "/")
        info = process_file(absolute_path, relative_path, language)
        results.append(info)
        status_counts[info["status"]] = status_counts.get(info["status"], 0) + 1

    print("Resolvendo imports (fase 2 - conecta arquivo com arquivo)...", file=sys.stderr)
    by_language = defaultdict(list)
    for result in results:
        by_language[result["language"]].append(result)
    for language, resolver in LANGUAGE_SUPPORT.supported_languages().items():
        resolver.resolve(by_language.get(language, []), root)

    resolution_counts = {}
    for language, language_files in by_language.items():
        total_imports = sum(len(f["imports"]) for f in language_files)
        resolved_imports = sum(1 for f in language_files for imp in f["imports"] if imp["resolved_path"])
        builtin_imports = sum(1 for f in language_files for imp in f["imports"] if imp["builtin"])
        external_imports = sum(1 for f in language_files for imp in f["imports"] if imp["external"])
        if total_imports:
            resolution_counts[language] = {
                "total": total_imports, "resolved": resolved_imports,
                "builtin": builtin_imports, "external": external_imports,
            }

    metadata = (
        Metadata(root, [r["language"] for r in results])
        .add_custom_field("by_status", status_counts)
        .add_custom_field("resolution", resolution_counts)
        .to_dict()
    )

    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "dependencies.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"_metadata": metadata, "files": results}, f, ensure_ascii=False, indent=2)

    print(f"\nGerado: {json_path}", file=sys.stderr)
    print(f"Por status: {status_counts}", file=sys.stderr)
    print(f"Resolucao de imports: {resolution_counts}", file=sys.stderr)


if __name__ == "__main__":
    main()
