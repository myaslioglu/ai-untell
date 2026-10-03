"""Tests for the top-level public API."""
import ai_untell
from ai_untell import CleanResult, ScanReport, clean, humanize, scan


def test_public_scan():
    report = scan("This is a test \u2014 with an em dash.")
    assert isinstance(report, ScanReport)
    assert report.char_count > 0


def test_public_clean():
    result = clean("Let's delve into the topic.")
    assert isinstance(result, CleanResult)
    assert "delve" not in result.cleaned.lower()


def test_public_humanize():
    result = humanize("Let's delve into the topic.")
    assert isinstance(result, CleanResult)


def test_version_present():
    assert ai_untell.__version__


def test_scan_file(fixtures_dir):
    report = ai_untell.scan_file(
        fixtures_dir / "sample_texts" / "known_ai_paragraph.md"
    )
    assert report.ai_score > 0.0


def test_clean_file_in_place(tmp_path):
    target = tmp_path / "x.md"
    target.write_text("We leverage this \u2014 a lot.", encoding="utf-8")
    result = ai_untell.clean_file(target, in_place=True)
    assert isinstance(result, CleanResult)
    assert "\u2014" not in target.read_text(encoding="utf-8")
