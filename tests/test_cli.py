"""Tests for the CLI (via click's CliRunner)."""
import json

from click.testing import CliRunner

from ai_untell.cli import cli


def test_scan_inline_json():
    runner = CliRunner()
    result = runner.invoke(cli, ["scan", "--text", "Let's delve into it.", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["token_count"] > 0
    assert "ai_score" in data


def test_scan_file(fixtures_dir):
    runner = CliRunner()
    path = fixtures_dir / "sample_texts" / "known_ai_paragraph.md"
    result = runner.invoke(cli, ["scan", str(path), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ai_score"] >= 0.4


def test_clean_inline():
    runner = CliRunner()
    result = runner.invoke(cli, ["clean", "--text", "In conclusion, we delve in."])
    assert result.exit_code == 0
    assert "In conclusion" not in result.output


def test_clean_in_place(tmp_path):
    runner = CliRunner()
    target = tmp_path / "doc.md"
    target.write_text("Let's delve into it \u2014 now.", encoding="utf-8")
    result = runner.invoke(cli, ["clean", str(target), "--in-place"])
    assert result.exit_code == 0
    cleaned = target.read_text(encoding="utf-8")
    assert "\u2014" not in cleaned
    # Backup exists by default.
    assert (tmp_path / "doc.md.bak").exists()


def test_clean_in_place_no_backup(tmp_path):
    runner = CliRunner()
    target = tmp_path / "doc.md"
    target.write_text("Let's delve into it.", encoding="utf-8")
    result = runner.invoke(cli, ["clean", str(target), "--in-place", "--no-backup"])
    assert result.exit_code == 0
    assert not (tmp_path / "doc.md.bak").exists()


def test_humanize_rule_fallback():
    runner = CliRunner()
    result = runner.invoke(cli, ["humanize", "--text", "We delve into it."])
    assert result.exit_code == 0
    assert "delve" not in result.output.lower()


def test_demo_command():
    runner = CliRunner()
    result = runner.invoke(cli, ["demo"])
    assert result.exit_code == 0
    assert "Cleaned text" in result.output


def test_missing_file_errors():
    runner = CliRunner()
    result = runner.invoke(cli, ["scan", "/nonexistent/path/file.md"])
    assert result.exit_code != 0
