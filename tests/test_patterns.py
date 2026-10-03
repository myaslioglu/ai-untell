"""Tests for the YAML pattern engine."""
from ai_untell.patterns.loader import PatternEngine
from ai_untell.types import TellCategory


def test_engine_loads_rules():
    engine = PatternEngine().load()
    assert len(engine.rules) > 80


def test_every_rule_has_valid_category():
    engine = PatternEngine().load()
    for rule in engine.rules:
        assert isinstance(rule.category, TellCategory)
        assert rule.severity in (1, 2, 3)


def test_match_detects_delve():
    engine = PatternEngine().load()
    hits = engine.match("Let's delve into the details.", scope="prose")
    assert any(h.rule_id.startswith("VOCAB-00") for h in hits)


def test_match_detects_serves_as():
    engine = PatternEngine().load()
    hits = engine.match("It serves as a reminder.", scope="prose")
    assert any(h.category == TellCategory.COPULA_AVOIDANCE for h in hits)


def test_scope_filtering():
    engine = PatternEngine().load()
    prose_rules = {r.id for r in engine.detectable("prose")}
    code_rules = {r.id for r in engine.detectable("code_nl")}
    assert "CODE-002" in code_rules
    assert "CODE-002" not in prose_rules


def test_offset_shift():
    engine = PatternEngine().load()
    hits = engine.match("xx leverage yy", scope="prose", offset=100)
    assert all(h.span[0] >= 100 for h in hits)
