"""The Claude skill bundle must match the source and run on the stdlib alone."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
UNTELL = ROOT / "skills" / "ai-untell" / "scripts" / "untell.py"

sys.path.insert(0, str(ROOT / "tools"))
import build_skill  # noqa: E402


def _run(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    # -S: no site-packages, so click/rich/pyyaml are unavailable, exactly like
    # a bare python3 in a cloud sandbox.
    return subprocess.run(
        [sys.executable, "-S", str(UNTELL), *args],
        input=stdin, capture_output=True, text=True, timeout=60,
    )


def test_bundle_in_sync_with_source():
    stale = build_skill.out_of_date()
    assert not stale, f"run `make skill`; stale files: {stale}"


def test_skill_md_frontmatter():
    text = (ROOT / "skills" / "ai-untell" / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    front = text.split("---\n")[1]
    fields = dict(line.split(": ", 1) for line in front.strip().splitlines())
    assert fields["name"] == "ai-untell"
    assert len(fields["description"]) <= 1024


def test_scan_json_stdlib_only():
    proc = _run("scan", "--json", "--text", "Certainly! Let's delve into this — now.")
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["ai_score"] > 0
    assert "chatbot_opener" in report["per_category"]


def test_clean_stdin_stdlib_only():
    proc = _run("clean", "-", stdin="We will delve into the topic — today.\n")
    assert proc.returncode == 0, proc.stderr
    assert "delve" not in proc.stdout and "—" not in proc.stdout


def test_clean_keeps_code_strings(tmp_path):
    src = tmp_path / "x.py"
    code = 'p.add_argument("--in-place")  # we leverage this flag\n'
    src.write_text(code, encoding="utf-8")
    proc = _run("clean", str(src))
    assert proc.returncode == 0, proc.stderr
    assert '"--in-place"' in proc.stdout
    assert "leverage" not in proc.stdout


def test_humanize_llm_error_exits_cleanly():
    proc = _run("humanize", "--text", "Some text.", "--llm", "--provider", "anthropic")
    assert proc.returncode == 2
    assert "nothing was written" in proc.stderr
    assert "Traceback" not in proc.stderr


@pytest.mark.parametrize("name", ["plugin.json", "marketplace.json"])
def test_plugin_manifests_are_valid_json(name):
    data = json.loads((ROOT / ".claude-plugin" / name).read_text(encoding="utf-8"))
    assert data["name"] == "ai-untell"
