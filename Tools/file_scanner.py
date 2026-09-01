from __future__ import annotations

import os
import sys


def _read_folder_list(path):
    names = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            name = line.split("#", 1)[0].strip()
            if name:
                names.add(name)
    return names


def load_ignored_folders(path):
    if not os.path.isfile(path):
        sys.exit(f"Arquivo de pastas ignoradas nao encontrado: {path}")
    return _read_folder_list(path)


def load_ignored_folders_optional(path):
    if not path or not os.path.isfile(path):
        return set()
    return _read_folder_list(path)


def scan_files(root, excluded_folders):
    for current, subdirs, files in os.walk(root):
        subdirs[:] = [d for d in subdirs if d not in excluded_folders and not d.startswith(".")]
        for name in files:
            absolute_path = os.path.join(current, name)
            relative_path = os.path.relpath(absolute_path, root).replace(os.sep, "/")
            yield absolute_path, relative_path
