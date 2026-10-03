"""Shared fixtures for ai-untell tests."""
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def ai_paragraph() -> str:
    return (FIXTURES / "sample_texts" / "known_ai_paragraph.md").read_text(encoding="utf-8")


@pytest.fixture
def human_paragraph() -> str:
    return (FIXTURES / "sample_texts" / "human_paragraph.md").read_text(encoding="utf-8")


@pytest.fixture
def ai_code() -> str:
    return (FIXTURES / "sample_code" / "claude_generated.py").read_text(encoding="utf-8")


@pytest.fixture
def mixed_doc() -> str:
    return (FIXTURES / "sample_texts" / "mixed_doc.md").read_text(encoding="utf-8")


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
