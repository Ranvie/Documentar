from __future__ import annotations

import json

from .base import Package, PackageDetector


class PackageNpm(PackageDetector):
    ecosystem = "npm"

    def wanted_filenames(self) -> list:
        return ["package.json"]

    def parse(self, path: str, content: bytes) -> list:
        try:
            data = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return []

        packages = []
        for section, dev in (("dependencies", False), ("devDependencies", True)):
            for name, version in data.get(section, {}).items():
                packages.append(Package(name=name, version=version, ecosystem=self.ecosystem, manifest_path=path, dev=dev))
        return packages
