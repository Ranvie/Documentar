#!/usr/bin/env python3
"""
Regenera javascript_builtin_classes.txt rodando reflection no Node CLI local.
Uso:
  python Tools/dependency/dependency_resolvers/generate_javascript_builtins.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_PATH = os.path.join(_HERE, "javascript_builtin_classes.txt")

_JS_SNIPPET = r"""
const names = Object.getOwnPropertyNames(globalThis)
  .filter(name => /^[A-Z]/.test(name) && typeof globalThis[name] === 'function')
  .sort();
console.log(names.join('\n'));
"""


def main():
    try:
        version = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as e:
        sys.exit(f"Não foi possível rodar o `node` (precisa estar no PATH): {e}")

    result = subprocess.run(["node", "-e", _JS_SNIPPET], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"node -e falhou:\n{result.stderr}")

    names = sorted({n.strip() for n in result.stdout.splitlines() if n.strip()})

    header = (
        "# Globals do JavaScript (construtores - Error, Array, Map, Promise, ...)\n"
        "# que comecam com maiuscula e sao \"function\" no globalThis - nunca tem\n"
        "# arquivo .js de verdade pra apontar, entao o javascript_resolver.py usa\n"
        "# essa lista pra marcar import[\"builtin\"]/ClassRef.builtin = true em vez de\n"
        "# deixar resolved_path=null sem explicacao.\n"
        "#\n"
        f"# Gerado automaticamente por generate_javascript_builtins.py em {datetime.now().strftime('%Y-%m-%d')}\n"
        f"# (Node {version}). Inclui tanto ECMAScript puro (Error/Array/Map/...) quanto\n"
        "# Web APIs globais no Node (fetch, streams, crypto) - uteis porque esse\n"
        "# parser tambem le codigo de front-end que roda no navegador. Pra atualizar:\n"
        "#   python Tools/dependency/dependency_resolvers/generate_javascript_builtins.py\n"
    )

    with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        f.write("\n".join(names) + "\n")

    print(f"{len(names)} nomes escritos em {_OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
