"""Tests for the rule-based cleaner."""
from ai_untell.cleaner import Cleaner
from ai_untell.types import Config


def _clean(text: str, **cfg) -> str:
    return Cleaner(Config(**cfg)).clean(text).cleaned


def test_em_dash_replaced():
    text = "This is a point \u2014 and here is another clause."
    out = _clean(text)
    assert "\u2014" not in out


def test_double_hyphen_normalized_to_en_dash():
    text = "This is a point -- and here is another clause."
    out = _clean(text)
    assert "--" not in out
    assert "\u2013" in out


def test_double_dash_keep_policy():
    text = "A point -- stays."
    out = _clean(text, double_dash_policy="keep")
    assert "--" in out


def test_delve_replaced():
    text = "We will delve into the topic today."
    out = _clean(text)
    assert "delve" not in out.lower()


def test_leverage_replaced():
    text = "The system leverages caching."
    out = _clean(text)
    assert "leverage" not in out.lower()


def test_in_conclusion_replaced():
    text = "In conclusion, the approach works well."
    out = _clean(text)
    assert "In conclusion" not in out


def test_copula_replaced():
    text = "The module serves as a parser."
    out = _clean(text)
    assert "serves as" not in out.lower()


def test_opener_removed():
    text = "Certainly! The answer is 42."
    out = _clean(text)
    assert not out.lstrip().lower().startswith("certainly")


def test_closer_removed():
    text = "The answer is 42.\n\nLet me know if you have any questions!"
    out = _clean(text)
    assert "Let me know" not in out


def test_cutoff_sentence_removed():
    text = ("As an AI language model, I don't have real-time information. "
            "The answer is 42.")
    out = _clean(text)
    assert "As an AI" not in out
    assert "The answer is 42." in out


def test_invisible_chars_removed():
    text = "hello\u200b world"
    out = _clean(text)
    assert "\u200b" not in out


def test_homoglyphs_normalized():
    text = "Use the p\u0430ssword to log in."
    out = _clean(text)
    assert "password" in out


def test_strength_off_keeps_vocab():
    text = "We will delve into the topic today."
    out = _clean(text, synonym_strength="off")
    assert "delve" in out.lower()


def test_not_only_but_also_simplified():
    text = "It improves not only speed, but also reliability."
    out = _clean(text)
    assert "not only" not in out.lower()


def test_curly_quotes_kept_by_default():
    text = "\u201cHello,\u201d she said."
    out = _clean(text)
    assert "\u201c" in out


def test_curly_quotes_straightened():
    text = "\u201cHello,\u201d she said."
    out = _clean(text, curly_quotes="straighten")
    assert '"' in out
    assert "\u201c" not in out


def test_emoji_stripped_when_enabled():
    text = "This rocks! \U0001f680 Fast and fun."
    out = _clean(text, strip_emoji=True)
    assert "\U0001f680" not in out


def test_clean_result_metadata():
    text = "Let's delve into it \u2014 now."
    result = Cleaner().clean(text)
    assert result.mode == "rules"
    assert result.pass_count == 1
    assert result.original == text
    assert result.cleaned != text
