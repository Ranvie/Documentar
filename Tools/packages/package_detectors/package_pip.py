from __future__ import annotations

import re

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None

from .base import Package, PackageDetector


_RE_REQUIREMENT_LINE = re.compile(
    r"^\s*([A-Za-z0-9_.\-]+)\s*(?:\[[^\]]*\])?\s*(?:==|>=|<=|~=|!=|>|<)?\s*([^\s;#]*)"
)

_PLATFORM_NAMES = {"python"}


class PackagePip(PackageDetector):
    ecosystem = "pip"

    def wanted_filenames(self) -> list:
        return ["requirements.txt", "pyproject.toml"]

    def parse(self, path: str, content: bytes) -> list:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return []

        if path.endswith("pyproject.toml"):
            return self._parse_pyproject(text, path)
        return self._parse_requirements(text, path)

    def _parse_requirements(self, text: str, path: str) -> list:
        packages = []
        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or line.startswith("-") or "://" in line:
                continue
            pkg = self._parse_pep508(line, path, dev=False)
            if pkg:
                packages.append(pkg)
        return packages

    def _parse_pyproject(self, text: str, path: str) -> list:
        if tomllib is None:
            return []
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return []

        packages = []

        project = data.get("project", {})
        for dep_string in project.get("dependencies", []):
            pkg = self._parse_pep508(dep_string, path, dev=False)
            if pkg:
                packages.append(pkg)
        for group_deps in project.get("optional-dependencies", {}).values():
            for dep_string in group_deps:
                pkg = self._parse_pep508(dep_string, path, dev=True)
                if pkg:
                    packages.append(pkg)

        poetry = data.get("tool", {}).get("poetry", {})
        for name, version in poetry.get("dependencies", {}).items():
            if name.lower() in _PLATFORM_NAMES:
                continue
            packages.append(Package(name=name, version=self._poetry_version_text(version), ecosystem=self.ecosystem, manifest_path=path))
        for group in poetry.get("group", {}).values():
            for name, version in group.get("dependencies", {}).items():
                packages.append(Package(name=name, version=self._poetry_version_text(version), ecosystem=self.ecosystem, manifest_path=path, dev=True))
        for name, version in poetry.get("dev-dependencies", {}).items():
            packages.append(Package(name=name, version=self._poetry_version_text(version), ecosystem=self.ecosystem, manifest_path=path, dev=True))

        return packages

    def _parse_pep508(self, dep_string: str, path: str, dev: bool):
        match = _RE_REQUIREMENT_LINE.match(dep_string.strip())
        if not match:
            return None
        name, version = match.groups()
        return Package(name=name, version=version or None, ecosystem=self.ecosystem, manifest_path=path, dev=dev)

    @staticmethod
    def _poetry_version_text(version) -> str:
        if isinstance(version, dict):
            return version.get("version") or ""
        return str(version)
