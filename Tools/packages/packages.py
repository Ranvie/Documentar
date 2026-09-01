#!/usr/bin/env python3
"""
Uso:
  python Tools/packages/packages.py [root_dir] [--project-name <nome>]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))  # Tools/packages
_TOOLS_DIR = os.path.dirname(_HERE)                 # Tools
sys.path.insert(0, _HERE)
sys.path.insert(0, _TOOLS_DIR)

from metadata import Metadata
from file_scanner import scan_files, load_ignored_folders, load_ignored_folders_optional

from package_detectors.package_composer import PackageComposer
from package_detectors.package_npm import PackageNpm
from package_detectors.package_pip import PackagePip

PROJECT_ROOT = os.path.dirname(_TOOLS_DIR)
DEFAULT_IGNORED_FOLDERS_FILE = os.path.join(PROJECT_ROOT, "ignored_folders.txt")
ARTIFACTS_DIR = os.path.join(PROJECT_ROOT, "artifacts")

DETECTORS = [
    PackageComposer(),
    PackageNpm(),
    PackagePip(),
]


def build_dispatch_table(detectors):
    table = defaultdict(list)
    for detector in detectors:
        for filename in detector.wanted_filenames():
            table[filename].append(detector)
    return table


def main():
    ap = argparse.ArgumentParser(description="Detector de dependencias externas do projeto (le manifesto de empacotador).")
    ap.add_argument("root", nargs="?", default=".", help="Pasta raiz a escanear (default: .)")
    ap.add_argument("--project-name", default=None, help="Nome do projeto pra organizar os artefatos (default: nome da pasta raiz escaneada)")
    ap.add_argument("--auto-generated-dir", default=None, help="Raiz de auto-generated do projeto (default: {raiz do repo}/artifacts/{projeto}/auto-generated)")
    ap.add_argument("--out-dir", default=None, help="Pasta de saida (default: {auto-generated-dir}/out-packages)")
    ap.add_argument("--exclude", default="", help="Pastas extras a ignorar, separadas por virgula")
    ap.add_argument("--ignored-folders-file", default=DEFAULT_IGNORED_FOLDERS_FILE, help="Arquivo com pastas puladas comuns a qualquer projeto")
    ap.add_argument("--project-ignored-folders-file", default=None, help="Arquivo com pastas puladas especificas deste projeto")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    project_name = args.project_name or os.path.basename(root.rstrip(os.sep).rstrip("/"))
    project_dir = os.path.join(ARTIFACTS_DIR, project_name)
    auto_generated_dir = args.auto_generated_dir or os.path.join(project_dir, "auto-generated")
    out_dir = args.out_dir or os.path.join(auto_generated_dir, "out-packages")
    project_ignored_folders_file = args.project_ignored_folders_file or os.path.join(project_dir, "ignored_folders.txt")
    extra_dirs = {d.strip() for d in args.exclude.split(",") if d.strip()}
    excluded = (
        load_ignored_folders(args.ignored_folders_file)
        | load_ignored_folders_optional(project_ignored_folders_file)
        | extra_dirs
    )

    dispatch_table = build_dispatch_table(DETECTORS)

    print(f"Escaneando {root} ...", file=sys.stderr)
    packages = []
    manifests_found = []
    file_ecosystems = []
    for absolute_path, relative_path in scan_files(root, excluded):
        matching_detectors = dispatch_table.get(os.path.basename(relative_path))
        if not matching_detectors:
            continue
        try:
            with open(absolute_path, "rb") as f:
                content = f.read()
        except OSError:
            continue

        manifests_found.append(relative_path)
        for detector in matching_detectors:
            file_ecosystems.append(detector.ecosystem)
            packages.extend(p.to_dict() for p in detector.parse(relative_path, content))

    by_ecosystem = defaultdict(int)
    for pkg in packages:
        by_ecosystem[pkg["ecosystem"]] += 1

    print(f"{len(manifests_found)} manifesto(s) encontrado(s), {len(packages)} pacote(s).", file=sys.stderr)

    metadata = (
        Metadata(root, file_ecosystems)
        .add_custom_field("manifests_found", manifests_found)
        .add_custom_field("by_ecosystem", dict(by_ecosystem))
        .to_dict()
    )

    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "packages.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"_metadata": metadata, "packages": packages}, f, ensure_ascii=False, indent=2)

    print(f"\nGerado: {json_path}", file=sys.stderr)
    print(f"Por ecossistema: {dict(by_ecosystem)}", file=sys.stderr)


if __name__ == "__main__":
    main()
