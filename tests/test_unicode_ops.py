"""Tests for Unicode hygiene operations."""
from ai_untell.unicode_ops import (
    find_homoglyphs,
    find_invisible,
    latin_ratio,
    normalize_homoglyphs,
    strip_invisible,
)


def test_strip_zero_width_space():
    text = "hel\u200blo wor\u200bld"
    cleaned, counts = strip_invisible(text)
    assert cleaned == "hello world"
    assert counts["ZERO WIDTH SPACE"] == 2


def test_strip_soft_hyphen_and_bom():
    text = "\ufeffso\u00adft hyphen"
    cleaned, counts = strip_invisible(text)
    assert cleaned == "soft hyphen"
    assert counts["ZERO WIDTH NO-BREAK SPACE (BOM)"] == 1
    assert counts["SOFT HYPHEN"] == 1


def test_strip_tag_block_characters():
    text = "watermark\U000e0041\U000e0042\U000e007f here"
    cleaned, counts = strip_invisible(text)
    assert cleaned == "watermark here"
    assert sum(counts.values()) == 3


def test_zwj_preserved_inside_emoji():
    family = "\U0001f468\u200d\U0001f469\u200d\U0001f467"  # family emoji
    cleaned, counts = strip_invisible(family)
    assert cleaned == family
    assert counts == {}


def test_zwj_removed_in_prose():
    text = "word\u200dword"
    cleaned, counts = strip_invisible(text)
    assert cleaned == "wordword"
    assert counts.get("ZERO WIDTH JOINER") == 1


def test_variation_selector_preserved_after_emoji():
    text = "\u2764\ufe0f love"
    cleaned, _ = strip_invisible(text)
    assert cleaned == text


def test_find_invisible_reports_offsets():
    text = "a\u200bb\u200bc"
    found = find_invisible(text)
    assert found["\u200b"] == [1, 3]


def test_homoglyph_normalization():
    # Cyrillic а (U+0430) inside a Latin word
    text = "p\u0430ssword"
    cleaned, count = normalize_homoglyphs(text)
    assert cleaned == "password"
    assert count == 1


def test_find_homoglyphs():
    text = "c\u0430t"
    found = find_homoglyphs(text)
    assert len(found) == 1
    assert found[0][1] == "\u0430"


def test_fullwidth_normalization():
    text = "\uff28ello"  # fullwidth H
    cleaned, count = normalize_homoglyphs(text)
    assert cleaned == "Hello"
    assert count == 1


def test_latin_ratio_gate():
    assert latin_ratio("this is pure latin text") == 1.0
    assert latin_ratio("\u044d\u0442\u043e \u0440\u0443\u0441\u0441\u043a\u0438\u0439") == 0.0
    assert latin_ratio("") == 1.0
