#!/usr/bin/env python3
"""Regenera php_builtin_classes.txt rodando reflection no PHP CLI local.

So' precisa rodar de novo quando trocar de versao do PHP (ou instalar uma
extensao nova estaticamente compilada) - o arquivo gerado e' um recurso
estatico, o dependency.py normal nao chama isso nem depende de `php` estar
instalado pra rodar.

Uso:
  python Tools/dependency/dependency_resolvers/generate_php_builtins.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_PATH = os.path.join(_HERE, "php_builtin_classes.txt")

_PHP_SNIPPET = r"""
$names = array_merge(get_declared_classes(), get_declared_interfaces(), get_declared_traits());
$internal = [];
foreach ($names as $n) {
    if ((new ReflectionClass($n))->isInternal()) {
        $internal[] = $n;
    }
}
sort($internal, SORT_STRING);
echo implode("\n", $internal);
"""


def main():
    try:
        version = subprocess.run(
            ["php", "-n", "-r", "echo PHP_VERSION;"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as e:
        sys.exit(f"Nao consegui rodar `php` (precisa estar no PATH): {e}")

    result = subprocess.run(["php", "-n", "-r", _PHP_SNIPPET], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"php -r falhou:\n{result.stderr}")

    names = sorted({n.strip() for n in result.stdout.splitlines() if n.strip()})

    header = (
        "# Classes/interfaces/traits internas do PHP (nucleo + extensoes estaticamente\n"
        "# compiladas) - nunca tem arquivo .php de verdade pra apontar, entao o\n"
        "# php_resolver.py usa essa lista pra marcar import[\"builtin\"] = true em vez de\n"
        "# deixar resolved_path=null sem explicacao.\n"
        "#\n"
        f"# Gerado automaticamente por generate_php_builtins.py em {datetime.now().strftime('%Y-%m-%d')}\n"
        f"# (PHP {version}, sem php.ini pra evitar lixo de extensao especifica de uma\n"
        "# maquina so'). Pra atualizar (ex: depois de trocar de versao do PHP):\n"
        "#   python Tools/dependency/dependency_resolvers/generate_php_builtins.py\n"
    )

    with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        f.write("\n".join(names) + "\n")

    print(f"{len(names)} nomes escritos em {_OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
