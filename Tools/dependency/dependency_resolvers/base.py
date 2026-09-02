from __future__ import annotations

import os


def load_builtin_names(path) -> frozenset:
    if not path or not os.path.isfile(path):
        return frozenset()
    names = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            name = line.split("#", 1)[0].strip()
            if name:
                names.add(name.lower())
    return frozenset(names)


class LanguageResolver:
    language: str

    def resolve(self, files: list, root: str) -> None:
        raise NotImplementedError
