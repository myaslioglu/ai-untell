"""Tests for the scanner and AI scoring."""
from pathlib import Path

from ai_untell.scanner import Scanner
from ai_untell.types import ContentKind, TellCategory


def test_ai_paragraph_scores_high(ai_paragraph):
    report = Scanner().scan(ai_paragraph)
    assert report.ai_score >= 0.4
    assert TellCategory.AI_VOCAB in report.per_category
    assert TellCategory.CHATBOT_OPENER in report.per_category


def test_human_paragraph_scores_low(human_paragraph):
    report = Scanner().scan(human_paragraph)
    assert report.ai_score <= 0.3


def test_em_dash_detected():
    text = "This is a point \u2014 and here is another clause."
    report = Scanner().scan(text)
    assert TellCategory.DASH_OVERUSE in report.per_category


def test_double_hyphen_detected():
    text = "This is a point -- and here is another clause."
    report = Scanner().scan(text)
    assert TellCategory.DASH_OVERUSE in report.per_category


def test_invisible_chars_detected():
    text = "Some text\u200b with a zero-width space."
    report = Scanner().scan(text)
    assert TellCategory.INVISIBLE_UNICODE in report.per_category
    assert report.invisible_chars or any(
        h.category == TellCategory.INVISIBLE_UNICODE for h in report.hits
    )


def test_knowledge_cutoff_detected():
    text = ("Great question. As an AI language model, I don't have real-time "
            "information. The answer is 42.")
    report = Scanner().scan(text)
    assert TellCategory.KNOWLEDGE_CUTOFF in report.per_category


def test_chatbot_opener_detected():
    text = "Certainly! Here is the answer you asked for.\n\nIt is 42."
    report = Scanner().scan(text)
    assert TellCategory.CHATBOT_OPENER in report.per_category


def test_code_file_detection(ai_code):
    report = Scanner().scan(ai_code, path=Path("claude_generated.py"))
    assert report.content_kind == ContentKind.CODE


def test_mixed_document_detection(mixed_doc):
    report = Scanner().scan(mixed_doc, path=Path("notes.md"))
    assert report.content_kind == ContentKind.MIXED
    assert report.ai_score >= 0.3


def test_token_count():
    report = Scanner().scan("one two three four five")
    assert report.token_count == 5


def test_score_between_zero_and_one(ai_paragraph):
    report = Scanner().scan(ai_paragraph)
    assert 0.0 <= report.ai_score <= 1.0
