#!/usr/bin/env python3
"""
Uso:
  python Tools/structure/structure.py <project_name> [--sort-by fan-in|fan-out]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))  # Tools/structure
_TOOLS_DIR = os.path.dirname(_HERE)                  # Tools
sys.path.insert(0, _TOOLS_DIR)

from metadata import Metadata
from language_support import LANGUAGE_SUPPORT

PROJECT_ROOT = os.path.dirname(_TOOLS_DIR)  # raiz do repo Documentar
ARTIFACTS_DIR = os.path.join(PROJECT_ROOT, "artifacts")


def is_internal_import(imp: dict) -> bool:
    return bool(imp.get("resolved_path")) and not imp.get("builtin") and not imp.get("external")


def internal_targets(f: dict) -> set:
    targets = {imp["resolved_path"] for imp in f["imports"] if is_internal_import(imp)}
    for symbol in f.get("symbols", []):
        for category in ("extends", "implements"):
            for ref in symbol.get(category, []):
                if is_internal_import(ref):
                    targets.add(ref["resolved_path"])
    return targets


def compute_fan_metrics(files: list) -> tuple:
    """Retorna (fan_out_por_path, fan_in_por_path): fan_out conta arquivos distintos
    referenciados (import ou extends/implements); fan_in conta arquivos distintos que
    referenciam de volta, nao ocorrencias brutas."""
    fan_out = {}
    incoming = {f["path"]: set() for f in files}
    for f in files:
        targets = internal_targets(f)
        fan_out[f["path"]] = len(targets)
        for target in targets:
            if target in incoming:
                incoming[target].add(f["path"])
    fan_in = {path: len(sources) for path, sources in incoming.items()}
    return fan_out, fan_in


def build_tree(files: list, fan_out: dict, fan_in: dict) -> dict:
    supported = LANGUAGE_SUPPORT.supported_languages()
    tree: dict = {}
    for f in files:
        parts = f["path"].split("/")
        *dirs, filename = parts
        node = tree
        for d in dirs:
            node = node.setdefault(d, {})
        node[filename] = {
            "fan_in": fan_in[f["path"]],
            "fan_out": fan_out[f["path"]],
            "analyzed": f["language"] in supported,
        }
    return tree


def _better(current, candidate, field):
    if candidate is None:
        return current
    if current is None or candidate[field] > current[field]:
        return candidate
    return current


def compute_stats(node: dict) -> dict:
    """Preenche node['_stats'] (rollup do diretorio) recursivamente e o devolve."""
    fan_in_total = 0
    fan_out_total = 0
    file_count = 0
    unanalyzed_file_count = 0
    hottest_fan_in = None
    hottest_fan_out = None

    for name, child in node.items():
        if "fan_in" in child:  # arquivo (folha)
            fan_in_total += child["fan_in"]
            fan_out_total += child["fan_out"]
            file_count += 1
            if not child["analyzed"]:
                unanalyzed_file_count += 1
            hottest_fan_in = _better(hottest_fan_in, {"path": name, "fan_in": child["fan_in"]}, "fan_in")
            hottest_fan_out = _better(hottest_fan_out, {"path": name, "fan_out": child["fan_out"]}, "fan_out")
        else:  # diretorio: recursa primeiro
            child_stats = compute_stats(child)
            fan_in_total += child_stats["fan_in_total"]
            fan_out_total += child_stats["fan_out_total"]
            file_count += child_stats["file_count"]
            unanalyzed_file_count += child_stats["unanalyzed_file_count"]
            child_hot_in = child_stats["hottest_fan_in_file"]
            if child_hot_in:
                child_hot_in = {"path": f"{name}/{child_hot_in['path']}", "fan_in": child_hot_in["fan_in"]}
            child_hot_out = child_stats["hottest_fan_out_file"]
            if child_hot_out:
                child_hot_out = {"path": f"{name}/{child_hot_out['path']}", "fan_out": child_hot_out["fan_out"]}
            hottest_fan_in = _better(hottest_fan_in, child_hot_in, "fan_in")
            hottest_fan_out = _better(hottest_fan_out, child_hot_out, "fan_out")

    stats = {
        "fan_in_total": fan_in_total,
        "fan_out_total": fan_out_total,
        "file_count": file_count,
        "unanalyzed_file_count": unanalyzed_file_count,
        "hottest_fan_in_file": hottest_fan_in,
        "hottest_fan_out_file": hottest_fan_out,
    }
    node["_stats"] = stats
    return stats


def sort_tree(node: dict, metric_field: str) -> dict:
    entries = [(name, child) for name, child in node.items() if name != "_stats"]

    def key(item):
        _, child = item
        if "fan_in" in child:  # arquivo
            return child[metric_field]
        return child["_stats"][f"{metric_field}_total"]

    entries.sort(key=key, reverse=True)

    ordered = {}
    if "_stats" in node:
        ordered["_stats"] = node["_stats"]
    for name, child in entries:
        ordered[name] = child if "fan_in" in child else sort_tree(child, metric_field)
    return ordered


def main():
    ap = argparse.ArgumentParser(description="Mapa de calor (fan-in/fan-out) por arquivo e por pasta.")
    ap.add_argument("project_name", help="Nome do projeto (mesma pasta usada em artifacts/<projeto>/...)")
    ap.add_argument("--dependencies-json", default=None, help="Caminho pro dependencies.json (default: artifacts/<projeto>/auto-generated/out-dependencies/dependencies.json)")
    ap.add_argument("--out-dir", default=None, help="Pasta de saida (default: artifacts/<projeto>/auto-generated/out-structure)")
    ap.add_argument("--sort-by", choices=["fan-in", "fan-out"], default="fan-in", help="Metrica usada pro arquivo ordenado (default: fan-in)")
    args = ap.parse_args()

    dependencies_json = args.dependencies_json or os.path.join(
        ARTIFACTS_DIR, args.project_name, "auto-generated", "out-dependencies", "dependencies.json"
    )
    out_dir = args.out_dir or os.path.join(ARTIFACTS_DIR, args.project_name, "auto-generated", "out-structure")

    if not os.path.isfile(dependencies_json):
        sys.exit(f"dependencies.json nao encontrado: {dependencies_json} (rode dependency.py antes)")

    with open(dependencies_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    files = data["files"]
    root = data["_metadata"]["root"]

    fan_out, fan_in = compute_fan_metrics(files)
    tree = build_tree(files, fan_out, fan_in)
    compute_stats(tree)

    metadata = Metadata(root, [f["language"] for f in files])

    os.makedirs(out_dir, exist_ok=True)

    structure_path = os.path.join(out_dir, "structure.json")
    with open(structure_path, "w", encoding="utf-8") as f:
        json.dump({"_metadata": metadata.to_dict(), "tree": tree}, f, ensure_ascii=False, indent=2)

    metric_field = "fan_in" if args.sort_by == "fan-in" else "fan_out"
    ordered_tree = sort_tree(tree, metric_field)
    ordered_metadata = metadata.copy().add_custom_field("sort_by", args.sort_by).to_dict()

    ordered_path = os.path.join(out_dir, f"ordered-{args.sort_by}-structure.json")
    with open(ordered_path, "w", encoding="utf-8") as f:
        json.dump({"_metadata": ordered_metadata, "tree": ordered_tree}, f, ensure_ascii=False, indent=2)

    print(f"Gerado: {structure_path}", file=sys.stderr)
    print(f"Gerado: {ordered_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
