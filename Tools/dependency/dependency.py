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
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__)) # Tools/dependency
_TOOLS_DIR = os.path.dirname(_HERE)                # Tools
sys.path.insert(0, _TOOLS_DIR)

from metadata import Metadata
from language_support import LANGUAGE_SUPPORT
from file_scanner import scan_files, load_ignored_folders, load_ignored_folders_optional

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


def list_files(root, excluded):
    for absolute_path, relative_path in scan_files(root, excluded):
        ext = os.path.splitext(relative_path)[1].lower()
        yield absolute_path, relative_path, EXTENSION_TO_LANGUAGE.get(ext), ext


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
    ap.add_argument("--auto-generated-dir", default=None, help="Raiz de auto-generated do projeto (default: {raiz do repo}/artifacts/{projeto}/auto-generated)")
    ap.add_argument("--out-dir", default=None, help="Pasta de saida (default: {auto-generated-dir}/out-dependencies)")
    ap.add_argument("--exclude", default="", help="Pastas extras a ignorar, separadas por virgula")
    ap.add_argument("--ignored-folders-file", default=DEFAULT_IGNORED_FOLDERS_FILE, help="Arquivo com pastas puladas comuns a qualquer projeto (default: ignored_folders.txt na raiz do Documentar)")
    ap.add_argument("--project-ignored-folders-file", default=None, help="Arquivo com pastas puladas especificas deste projeto, somado ao --ignored-folders-file (default: artifacts/{projeto}/ignored_folders.txt, se existir)")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    project_name = args.project_name or os.path.basename(root.rstrip(os.sep).rstrip("/"))
    project_dir = os.path.join(ARTIFACTS_DIR, project_name)
    auto_generated_dir = args.auto_generated_dir or os.path.join(project_dir, "auto-generated")
    out_dir = args.out_dir or os.path.join(auto_generated_dir, "out-dependencies")
    project_ignored_folders_file = args.project_ignored_folders_file or os.path.join(project_dir, "ignored_folders.txt")
    extra_dirs = {d.strip() for d in args.exclude.split(",") if d.strip()}
    excluded = (
        load_ignored_folders(args.ignored_folders_file)
        | load_ignored_folders_optional(project_ignored_folders_file)
        | extra_dirs
    )

    print(f"Escaneando {root} ...", file=sys.stderr)
    files = list(list_files(root, excluded))
    print(f"{len(files)} arquivo(s) encontrado(s). Processando...", file=sys.stderr)

    results = []
    status_counts = {}
    unrecognized_extension_counts = Counter()
    for absolute_path, relative_path, language, ext in files:
        if language is None:
            unrecognized_extension_counts[ext or "(No extension)"] += 1
            continue
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

    unrecognized_extensions = dict(
        sorted(unrecognized_extension_counts.items(), key=lambda kv: kv[1], reverse=True)
    )

    metadata = (
        Metadata(root, [r["language"] for r in results])
        .add_custom_field("by_status", status_counts)
        .add_custom_field("resolution", resolution_counts)
        .add_custom_field("unrecognized_extensions", unrecognized_extensions)
        .to_dict()
    )

    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "dependencies.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"_metadata": metadata, "files": results}, f, ensure_ascii=False, indent=2)

    print(f"\nGerado: {json_path}", file=sys.stderr)
    print(f"Por status: {status_counts}", file=sys.stderr)
    print(f"Resolucao de imports: {resolution_counts}", file=sys.stderr)
    print(f"Extensoes nao reconhecidas: {unrecognized_extensions}", file=sys.stderr)


if __name__ == "__main__":
    main()
