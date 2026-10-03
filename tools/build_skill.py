#!/usr/bin/env python3
"""Build the Claude skill bundle from the package source.

The skill under ``skills/ai-untell/`` carries a vendored copy of the engine so
it runs anywhere ``python3`` exists (local Claude Code, cloud sessions,
claude.ai, the Claude API) with no pip install. This script regenerates that
copy from ``src/ai_untell`` so the two never drift:

* every engine module is copied verbatim (the CLI, which needs click/rich, is
  left out; the skill has its own stdlib CLI in ``scripts/untell.py``);
* YAML rule files are converted to JSON, which the loader reads without PyYAML.

Usage:
    python tools/build_skill.py           # regenerate skills/ai-untell/scripts/ai_untell
    python tools/build_skill.py --check   # exit 1 if the bundle is out of date
    python tools/build_skill.py --zip     # also write dist/ai-untell-skill.zip (claude.ai upload)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "ai_untell"
SKILL_DIR = ROOT / "skills" / "ai-untell"
VENDOR = SKILL_DIR / "scripts" / "ai_untell"
ZIP_PATH = ROOT / "dist" / "ai-untell-skill.zip"

EXCLUDED_FILES = {"cli.py", "__main__.py"}
EXCLUDED_PARTS = {"__pycache__", ".DS_Store"}


def _wanted(path: Path) -> bool:
    return (
        path.is_file()
        and path.name not in EXCLUDED_FILES
        and not EXCLUDED_PARTS.intersection(path.parts)
        and path.suffix in {".py", ".yml"}
    )


def _yaml_to_json(text: str) -> str:
    import yaml

    return json.dumps(yaml.safe_load(text) or [], indent=2, ensure_ascii=False) + "\n"


def render(dest: Path) -> None:
    """Write the vendored engine into ``dest`` (which must not exist)."""
    for path in sorted(SRC.rglob("*")):
        if not _wanted(path):
            continue
        rel = path.relative_to(SRC)
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".yml":
            rel = rel.with_suffix(".json")
            text = _yaml_to_json(text)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file() and not EXCLUDED_PARTS.intersection(p.parts)
    }


def out_of_date() -> list[str]:
    """Return the vendored files that differ from a fresh build."""
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "ai_untell"
        render(fresh)
        expected = _snapshot(fresh)
    actual = _snapshot(VENDOR) if VENDOR.exists() else {}
    return sorted(
        name for name in expected.keys() | actual.keys()
        if expected.get(name) != actual.get(name)
    )


def build() -> None:
    if VENDOR.exists():
        shutil.rmtree(VENDOR)
    render(VENDOR)


def build_zip() -> Path:
    """Zip the skill as ``ai-untell/...`` for upload to claude.ai."""
    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(SKILL_DIR.rglob("*")):
            if path.is_file() and not EXCLUDED_PARTS.intersection(path.parts):
                zf.write(path, Path("ai-untell") / path.relative_to(SKILL_DIR))
    return ZIP_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="Fail if the bundle is stale.")
    parser.add_argument("--zip", action="store_true", help="Also build the claude.ai zip.")
    args = parser.parse_args()

    if args.check:
        stale = out_of_date()
        if stale:
            print("Skill bundle is out of date; run `make skill`. Differs:", file=sys.stderr)
            for name in stale:
                print(f"  {name}", file=sys.stderr)
            return 1
        print("Skill bundle is up to date.")
        return 0

    build()
    print(f"Built {VENDOR.relative_to(ROOT)}")
    if args.zip:
        print(f"Wrote {build_zip().relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
