"""Portable launcher for the LOL short-window evaluator Skill.

When copied outside the repository, set LOL_SHORT_WINDOW_REPO to the project
root. When kept under ``skills/`` in this repository, the root is discovered
automatically. All command-line arguments are passed to the existing workbench
entry point; this file does not duplicate sampling or scoring logic.
"""

from pathlib import Path
import os
import subprocess
import sys


def repository_root():
    configured = os.environ.get("LOL_SHORT_WINDOW_REPO")
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser().resolve())
    # A local installation may carry a one-line repo_path.txt next to the
    # Skill. This keeps a copied Skill usable in later Codex conversations
    # without requiring the parent process to inherit a new environment var.
    configured_file = Path(__file__).with_name("repo_path.txt")
    if configured_file.is_file():
        value = configured_file.read_text(encoding="utf-8-sig").strip()
        if value:
            candidates.append(Path(value).expanduser().resolve())
    candidates.append(Path(__file__).resolve().parents[2])
    for candidate in candidates:
        if (candidate / "main.py").is_file() and (candidate / "workbench").is_dir():
            return candidate
    raise RuntimeError(
        "Cannot locate the evaluator repository; set LOL_SHORT_WINDOW_REPO "
        "to its root directory."
    )


def main(argv=None):
    root = repository_root()
    command = [sys.executable, str(root / "main.py"), *(sys.argv[1:] if argv is None else argv)]
    return subprocess.call(command, cwd=str(root))


if __name__ == "__main__":
    raise SystemExit(main())
