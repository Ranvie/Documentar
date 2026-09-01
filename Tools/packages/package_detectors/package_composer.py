from __future__ import annotations

import json

from .base import Package, PackageDetector

# "php" e "ext-*" sao requisito de plataforma (versao do runtime, extensao
# nativa) - nao sao biblioteca de terceiro de verdade, entao ficam fora.
_PLATFORM_NAMES = {"php", "php-64bit", "hhvm"}
_PLATFORM_PREFIXES = ("ext-", "lib-")


def _is_platform_requirement(name: str) -> bool:
    return name in _PLATFORM_NAMES or name.startswith(_PLATFORM_PREFIXES)


class PackageComposer(PackageDetector):
    ecosystem = "composer"

    def wanted_filenames(self) -> list:
        return ["composer.json"]

    def parse(self, path: str, content: bytes) -> list:
        try:
            data = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return []

        packages = []
        for section, dev in (("require", False), ("require-dev", True)):
            for name, version in data.get(section, {}).items():
                if _is_platform_requirement(name):
                    continue
                packages.append(Package(name=name, version=version, ecosystem=self.ecosystem, manifest_path=path, dev=dev))
        return packages
