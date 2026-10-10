"""Experiment plumbing: configs, result directories, and output writers.

Every run writes to its own ``eval/results/<timestamp>-<name>/`` directory
with a copy of the config and environment metadata, so any table in the paper
can be traced back to the exact settings and code version that produced it.
"""

from __future__ import annotations

import csv
import glob
import json
import platform
import subprocess
import sys
from datetime import datetime
from importlib import metadata
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]

_TRACKED_PACKAGES = (
    "chromadb",
    "langchain-core",
    "langchain-chroma",
    "langchain-huggingface",
    "langchain-ollama",
    "langchain-text-splitters",
    "lingua-language-detector",
    "pypdf",
    "sentence-transformers",
    "torch",
    "transformers",
)


def load_config(path: str | Path) -> dict:
    """Read a YAML experiment config."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve(path: str | Path) -> Path:
    """Resolve ``path`` against the repo root unless it is absolute."""
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def expand_globs(patterns: list[str]) -> list[Path]:
    """Expand repo-relative glob patterns into a sorted, de-duplicated list."""
    paths = {Path(m) for pattern in patterns for m in glob.glob(str(resolve(pattern)))}
    if not paths:
        raise FileNotFoundError(f"No files match {patterns}")
    return sorted(paths)


def make_run_dir(name: str, base: str | Path = "eval/results") -> Path:
    """Create ``<base>/<YYYYmmdd-HHMMSS>-<name>/`` and return it."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = resolve(base) / f"{stamp}-{name}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def run_metadata(extra: dict | None = None) -> dict:
    """Collect code version and environment details for reproducibility."""
    versions = {}
    for package in _TRACKED_PACKAGES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": versions,
        "command": " ".join(sys.argv),
        **(extra or {}),
    }


def write_run_header(run_dir: Path, config: dict, extra_meta: dict | None = None) -> None:
    """Write ``config.yaml`` and ``meta.json`` into ``run_dir``."""
    (run_dir / "config.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (run_dir / "meta.json").write_text(
        json.dumps(run_metadata(extra_meta), indent=2, ensure_ascii=False), encoding="utf-8"
    )


def write_csv(path: Path, rows: list[dict]) -> None:
    """Write ``rows`` (dicts sharing the first row's keys) as UTF-8 CSV."""
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict], columns: list[str] | None = None) -> str:
    """Render ``rows`` as a GitHub-flavoured markdown table."""
    if not rows:
        return "_(no rows)_\n"
    cols = columns or list(rows[0].keys())
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def fmt_ci(value: float, low: float, high: float) -> str:
    """Format a point estimate with its interval, e.g. ``0.81 [0.69, 0.92]``."""
    return f"{value:.2f} [{low:.2f}, {high:.2f}]"
