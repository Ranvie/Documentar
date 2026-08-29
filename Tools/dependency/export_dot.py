#!/usr/bin/env python3
"""
Uso:
  python Tools/dependency/export_dot.py <dependencias.json> [--out grafo.dot]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

_ESTILO_POR_CATEGORIA = {
    "extends": "style=solid, arrowhead=empty, penwidth=1.5",
    "implements": "style=dashed, arrowhead=empty, penwidth=1.5",
    "uses": 'style=solid, arrowhead=normal, color="#888888"',
}


def _escapar(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


class DotExporter:
    def __init__(self, data: dict):
        self._files = data.get("files", [])

    def build_edges(self) -> Counter:
        edges = Counter()
        heranca_pairs = set()

        for file in self._files:
            if file.get("status") != "ok":
                continue
            origem = file["path"]
            for symbol in file.get("symbols", []):
                for categoria in ("extends", "implements"):
                    for ref in symbol.get(categoria, []):
                        destino = ref.get("resolved_path")
                        if destino and destino != origem:
                            edges[(origem, destino, categoria)] += 1
                            heranca_pairs.add((origem, destino))

        for file in self._files:
            if file.get("status") != "ok":
                continue
            origem = file["path"]
            for imp in file.get("imports", []):
                destino = imp.get("resolved_path")
                if destino and destino != origem and (origem, destino) not in heranca_pairs:
                    edges[(origem, destino, "uses")] += 1

        return edges

    def to_dot(self) -> str:
        edges = self.build_edges()

        nodes = {file["path"] for file in self._files if file.get("status") == "ok"}

        linhas = ["digraph dependencias {", "  rankdir=LR;", "  node [shape=box, fontsize=10];"]
        for no in sorted(nodes):
            linhas.append(f'  "{_escapar(no)}";')

        for (origem, destino, categoria), contagem in sorted(edges.items()):
            estilo = _ESTILO_POR_CATEGORIA[categoria]
            label = f', label="{contagem}"' if contagem > 1 and categoria == "uses" else ""
            linhas.append(f'  "{_escapar(origem)}" -> "{_escapar(destino)}" [{estilo}{label}];')

        linhas.append("}")
        return "\n".join(linhas)


def main():
    ap = argparse.ArgumentParser(description="Exporta dependencies.json pra grafo .dot (Graphviz).")
    ap.add_argument("json_path", help="Caminho do dependencies.json")
    ap.add_argument("--out", default=None, help="Caminho do .dot de saida (default: mesmo nome/pasta do json, trocando a extensao)")
    args = ap.parse_args()

    with open(args.json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    dot = DotExporter(data).to_dot()

    out_path = args.out or args.json_path.rsplit(".", 1)[0] + ".dot"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(dot + "\n")

    print(f"Gerado: {out_path}", file=sys.stderr)
    print(f"Renderizar: dot -Tsvg {out_path} -o {out_path.rsplit('.', 1)[0]}.svg", file=sys.stderr)


if __name__ == "__main__":
    main()
