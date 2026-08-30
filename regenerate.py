#!/usr/bin/env python3
"""
Uso:
  python regenerate.py                             # roda todos os projetos do registry.toml
  python regenerate.py <nome>                      # roda so um projeto ja cadastrado
  python regenerate.py --path <path> --name <nome> # cadastra/atualiza o projeto e roda
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import tomlkit

PROJECT_ROOT = Path(__file__).resolve().parent
TOOLS_DIR = PROJECT_ROOT / "Tools"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
TEMP_DIR = PROJECT_ROOT / "artifacts-temp"
ERRORS_DIR = PROJECT_ROOT / "errors"
REGISTRY_PATH = PROJECT_ROOT / "registry.toml"


def load_registry():
    if not REGISTRY_PATH.exists():
        doc = tomlkit.document()
        doc["projects"] = tomlkit.aot()
        return doc
    return tomlkit.parse(REGISTRY_PATH.read_text(encoding="utf-8"))


def save_registry(doc) -> None:
    REGISTRY_PATH.write_text(tomlkit.dumps(doc), encoding="utf-8")


def find_project(doc, name):
    for project in doc.get("projects", []):
        if project["name"] == name:
            return project
    return None


def register_project(doc, name: str, path: str):
    existing = find_project(doc, name)

    if existing is None:
        if not os.path.isdir(path):
            sys.exit(f"Erro: path '{path}' nao existe ou nao e uma pasta.")
        table = tomlkit.table()
        table["name"] = name
        table["path"] = path
        table["steps"] = tomlkit.aot()
        doc["projects"].append(table)
        save_registry(doc)
        return table

    if existing["path"] == path:
        return existing

    resposta = input(
        f"Aviso: o projeto '{name}' ja existe com path diferente "
        f"({existing['path']}). Deseja sobrescrever para: ({path})? [s/N]: "
    ).strip().lower()
    if resposta not in ("s", "sim"):
        sys.exit("Cancelado.")
    existing["path"] = path
    save_registry(doc)
    return existing


def log_error(project_name: str, step_index: int, tool: str, args: list, stderr: str) -> Path:
    ERRORS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now()
    error_path = ERRORS_DIR / (timestamp.strftime("%Y-%m-%d_%H-%M-%S") + ".json")
    payload = {
        "project": project_name,
        "failed_step_index": step_index,
        "tool": tool,
        "args": args,
        "stderr": stderr,
        "timestamp": timestamp.isoformat(),
    }
    error_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return error_path


def run_project(project) -> bool:
    name = project["name"]
    project_path = project["path"]
    steps = project.get("steps", [])

    project_temp_dir = TEMP_DIR / name
    if project_temp_dir.exists():
        shutil.rmtree(project_temp_dir)

    auto_generated_dir = project_temp_dir / "auto-generated"

    for index, step in enumerate(steps):
        tool = step["tool"]
        args = list(step.get("args", []))

        if "--project-name" not in args:
            args += ["--project-name", name]

        tool_path = TOOLS_DIR / tool

        if not tool_path.is_file():
            error_path = log_error(name, index, tool, args, f"Ferramenta nao encontrada: {tool_path}")
            print(f"Falhou no step {index} ({tool}) do projeto {name}. Veja {error_path}", file=sys.stderr)
            return False

        cmd = [sys.executable, str(tool_path), *args, "--auto-generated-dir", str(auto_generated_dir)]
        result = subprocess.run(cmd, cwd=project_path, capture_output=True, text=True)

        if result.returncode != 0:
            error_path = log_error(name, index, tool, args, result.stderr)
            print(f"Falhou no step {index} ({tool}) do projeto {name}. Veja {error_path}", file=sys.stderr)
            return False

    return True


def swap_into_place(name: str) -> None:
    temp_auto_generated = TEMP_DIR / name / "auto-generated"
    if not temp_auto_generated.exists():
        return

    real_auto_generated = ARTIFACTS_DIR / name / "auto-generated"
    real_auto_generated.parent.mkdir(parents=True, exist_ok=True)
    if real_auto_generated.exists():
        shutil.rmtree(real_auto_generated)
    shutil.move(str(temp_auto_generated), str(real_auto_generated))

    project_temp_dir = TEMP_DIR / name
    if project_temp_dir.exists() and not any(project_temp_dir.iterdir()):
        project_temp_dir.rmdir()


def run_all(doc) -> None:
    projects = list(doc.get("projects", []))
    for project in projects:
        if not run_project(project):
            sys.exit(f"Rebuild interrompido no projeto '{project['name']}'.")
    for project in projects:
        swap_into_place(project["name"])
    print(f"Rebuild completo: {len(projects)} projeto(s) atualizados.")


def run_single(project) -> None:
    if not run_project(project):
        sys.exit(f"Rebuild do projeto '{project['name']}' falhou.")
    swap_into_place(project["name"])
    print(f"Rebuild completo: projeto '{project['name']}' atualizado.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Orquestrador mecanico: roda as ferramentas de Tools/ para cada projeto do registry.toml.")
    ap.add_argument("name", nargs="?", default=None, help="Nome de um projeto ja cadastrado (roda so ele)")
    ap.add_argument("--path", default=None, help="Caminho da raiz do projeto (usado junto com --name)")
    ap.add_argument("--name", dest="reg_name", default=None, help="Nome do projeto a cadastrar/atualizar (usado junto com --path)")
    args = ap.parse_args()

    if args.path or args.reg_name:
        if not (args.path and args.reg_name):
            sys.exit("Erro: --path e --name devem ser usados juntos.")
        if args.name:
            sys.exit("Erro: nao use um nome posicional junto com --path/--name.")
        doc = load_registry()
        project = register_project(doc, args.reg_name, args.path)
        run_single(project)
        return

    doc = load_registry()

    if args.name:
        project = find_project(doc, args.name)
        if project is None or not (ARTIFACTS_DIR / args.name).is_dir():
            sys.exit(
                f"Projeto '{args.name}' nao encontrado. "
                f"Use --path e --name na primeira execucao para configura-lo."
            )
        run_single(project)
        return

    run_all(doc)


if __name__ == "__main__":
    main()
