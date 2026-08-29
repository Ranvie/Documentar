#!/usr/bin/env python3
"""Roteador do mapeador de dependencias (v0 - so' fase de EXTRACAO).

Le cada arquivo reconhecido, identifica a linguagem pela extensao e despacha
pro parser especifico em dependency_parsers/. Quando a linguagem e' conhecida
mas ainda nao tem parser dedicado, o arquivo entra no JSON com
status="unsupported" em vez de ser descartado (mantem o no' "opaco" em vez de
sumir do grafo - ver pergunta em aberto do PROJETO.md).

Fase de RESOLUCAO (imports_raw -> caminho de arquivo real) ainda nao existe:
todo import sai com resolved_path=null. Isso e' proposital (PROJETO.md,
decisao #1, separa extracao de resolucao em etapas distintas).

Uso:
  python Tools/dependency.py [root_dir] [--out-dir Tools/saida-dependencias]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dependency_parsers.python_parser import PythonParser
from dependency_parsers.php_parser    import PhpParser
from git_state                        import get_git_info

EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".php": "php",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

PARSERS = {
    "python": PythonParser(),
    "php": PhpParser(),
}

# Importante, essas pastas são puladas sempre, pode ser que haja falsos positivos, é necessário atualizar conforme o projeto
DEFAULT_EXCLUDED_DIRS = {
    ".git", "node_modules", "vendor", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".pytest_cache",
    # convencao Laravel: cache de view compilada, sessao, log e upload
    "storage",
}


def list_files(root, extra_excluded_dirs):
    excluded = DEFAULT_EXCLUDED_DIRS | extra_excluded_dirs
    for current, subdirs, files in os.walk(root):
        subdirs[:] = [d for d in subdirs if d not in excluded and not d.startswith(".")]
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext not in EXTENSION_TO_LANGUAGE:
                continue
            yield os.path.join(current, name), EXTENSION_TO_LANGUAGE[ext]


def process_file(absolute_path, relative_path, language):
    parser = PARSERS.get(language)
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
    ap = argparse.ArgumentParser(description="Roteador do mapeador de dependencias (fase de extracao).")
    ap.add_argument("root", nargs="?", default=".", help="Pasta raiz a escanear (default: .)")
    ap.add_argument("--out-dir", default="Tools/saida-dependencias", help="Pasta de saida")
    ap.add_argument("--exclude", default="", help="Pastas extras a ignorar, separadas por virgula")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    extra_dirs = {d.strip() for d in args.exclude.split(",") if d.strip()}

    print(f"Escaneando {root} ...", file=sys.stderr)
    files = list(list_files(root, extra_dirs))
    print(f"{len(files)} arquivo(s) reconhecido(s). Processando...", file=sys.stderr)

    results = []
    status_counts = {}
    for absolute_path, language in files:
        relative_path = os.path.relpath(absolute_path, root).replace(os.sep, "/")
        info = process_file(absolute_path, relative_path, language)
        results.append(info)
        status_counts[info["status"]] = status_counts.get(info["status"], 0) + 1

    metadata = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "root": root,
        "git": get_git_info(root),
        "command": "dependency.py " + " ".join(sys.argv[1:]),
        "files": len(results),
        "by_status": status_counts,
    }

    os.makedirs(args.out_dir, exist_ok=True)
    json_path = os.path.join(args.out_dir, "dependencias.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"_metadata": metadata, "files": results}, f, ensure_ascii=False, indent=2)

    print(f"\nGerado: {json_path}", file=sys.stderr)
    print(f"Por status: {status_counts}", file=sys.stderr)


if __name__ == "__main__":
    main()
