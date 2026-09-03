from __future__ import annotations

import copy
import os
import sys
from collections import Counter
from datetime import datetime

from git_state import get_git_info


class Metadata:
    def __init__(self, root: str, file_languages: list, total_files: int | None = None):
        language_counts = Counter(file_languages)
        self._data = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "root": root,
            "git": get_git_info(root),
            "command": os.path.basename(sys.argv[0]) + " " + " ".join(sys.argv[1:]),
            "files": {
                "total": total_files if total_files is not None else len(file_languages),
                "recognized": len(file_languages),
                "type": dict(sorted(language_counts.items())),
            },
        }

    def add_custom_field(self, name: str, value) -> "Metadata":
        self._data[name] = value
        return self

    def copy(self) -> "Metadata":
        return copy.deepcopy(self)

    def to_dict(self) -> dict:
        return self._data
