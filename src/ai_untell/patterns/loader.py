"""Rule loading and matching engine.

Rules live in YAML files under ``patterns/rules/``. The Claude skill bundle
ships the same rules as JSON (built by ``tools/build_skill.py``) so it runs on
the standard library alone; JSON files are preferred when present. Each rule is
a regex with
metadata: category, severity, replacement options, scope (prose / code
natural-language / any) and the minimum synonym strength at which its
replacement is applied. Detection is always active; replacement is gated by
``Config.synonym_strength``.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ai_untell.types import TellCategory, TellHit

RULES_DIR = Path(__file__).parent / "rules"

STRENGTH_ORDER = {"off": 0, "light": 1, "moderate": 2, "aggressive": 3}

_FLAG_MAP = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}


@dataclass
class Rule:
    id: str
    category: TellCategory
    severity: int
    pattern: str
    regex: re.Pattern
    replacements: list[str] = field(default_factory=list)
    note: str = ""
    scope: str = "any"            # any | prose | code_nl
    min_strength: str = "light"   # light | moderate | aggressive
    action: str = "replace"       # replace | flag

    @property
    def has_replacement(self) -> bool:
        return bool(self.replacements) and self.action == "replace"


class PatternEngine:
    def __init__(self, rules_dir: Path | None = None):
        self.rules_dir = rules_dir or RULES_DIR
        self.rules: list[Rule] = []
        self._loaded = False

    def load(self) -> "PatternEngine":
        if self._loaded:
            return self
        for entry in self._read_entries():
            flags = 0
            for ch in entry.get("flags", ""):
                flags |= _FLAG_MAP.get(ch, 0)
            category = TellCategory(entry["category"])
            self.rules.append(
                Rule(
                    id=str(entry["id"]),
                    category=category,
                    severity=int(entry.get("severity", 2)),
                    pattern=entry["pattern"],
                    regex=re.compile(entry["pattern"], flags),
                    replacements=list(entry.get("replacements") or []),
                    note=entry.get("note", ""),
                    scope=entry.get("scope", "any"),
                    min_strength=entry.get("min_strength", "light"),
                    action=entry.get("action", "replace"),
                )
            )
        self._loaded = True
        return self

    def _read_entries(self) -> list[dict]:
        json_paths = sorted(self.rules_dir.glob("*.json"))
        if json_paths:
            files = [json.loads(p.read_text(encoding="utf-8")) for p in json_paths]
        else:
            import yaml

            files = [
                yaml.safe_load(p.read_text(encoding="utf-8"))
                for p in sorted(self.rules_dir.glob("*.yml"))
            ]
        return [entry for data in files for entry in (data or [])]

    def by_category(self, category: TellCategory) -> list[Rule]:
        self.load()
        return [r for r in self.rules if r.category == category]

    def detectable(self, scope: str, categories: set[TellCategory] | None = None) -> list[Rule]:
        """Rules whose patterns may be searched in the given scope."""
        self.load()
        out = []
        for rule in self.rules:
            if rule.scope not in ("any", scope):
                continue
            if categories is not None and rule.category not in categories:
                continue
            out.append(rule)
        return out

    def match(
        self,
        text: str,
        scope: str = "prose",
        categories: set[TellCategory] | None = None,
        offset: int = 0,
    ) -> list[TellHit]:
        """Find all rule hits in ``text`` (offsets shifted by ``offset``)."""
        hits: list[TellHit] = []
        for rule in self.detectable(scope, categories):
            for m in rule.regex.finditer(text):
                if not m.group(0):
                    continue
                suggestion = rule.replacements[0] if rule.replacements else None
                hits.append(
                    TellHit(
                        category=rule.category,
                        span=(offset + m.start(), offset + m.end()),
                        matched=m.group(0),
                        severity=rule.severity,
                        rule_id=rule.id,
                        suggestion=suggestion,
                    )
                )
        return hits
