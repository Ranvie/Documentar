from __future__ import annotations

import subprocess


def run_git(root, *args):
    try:
        r = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def get_git_info(root):
    branch = run_git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch is None:
        return None
    commit = run_git(root, "rev-parse", "--short", "HEAD")
    status = run_git(root, "status", "--porcelain")
    return {"branch": branch, "commit": commit, "dirty": bool(status)}
