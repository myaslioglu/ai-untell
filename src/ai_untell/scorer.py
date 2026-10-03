"""AI-score computation from a ScanReport.

Each tell category has a weight and a saturation threshold expressed as hits
per 100 tokens. The score is the weight-normalized sum of clamped densities,
so a document saturated with every tell approaches 1.0 and a clean document
approaches 0.0.
"""
from __future__ import annotations

from ai_untell.types import ScanReport, TellCategory

# category -> relative weight (sums to 1.0)
WEIGHTS: dict[TellCategory, float] = {
    TellCategory.DASH_OVERUSE: 0.08,
    TellCategory.AI_VOCAB: 0.14,
    TellCategory.COPULA_AVOIDANCE: 0.06,
    TellCategory.RULE_OF_THREE: 0.03,
    TellCategory.NEGATIVE_PARALLELISM: 0.06,
    TellCategory.CHATBOT_OPENER: 0.12,
    TellCategory.KNOWLEDGE_CUTOFF: 0.10,
    TellCategory.PROMOTIONAL: 0.05,
    TellCategory.SIGNIFICANCE_INFLATION: 0.08,
    TellCategory.INVISIBLE_UNICODE: 0.12,
    TellCategory.HOMOGLYPH: 0.10,
    TellCategory.EMOJI_FORMATTING: 0.02,
    TellCategory.BOLD_OVERUSE: 0.02,
    TellCategory.CURLY_QUOTES: 0.01,
    TellCategory.STRUCTURAL: 0.01,
}

# category -> hits per 100 tokens that count as "fully saturated"
THRESHOLDS: dict[TellCategory, float] = {
    TellCategory.DASH_OVERUSE: 1.2,
    TellCategory.AI_VOCAB: 3.0,
    TellCategory.COPULA_AVOIDANCE: 0.8,
    TellCategory.RULE_OF_THREE: 0.4,
    TellCategory.NEGATIVE_PARALLELISM: 0.6,
    TellCategory.CHATBOT_OPENER: 0.4,
    TellCategory.KNOWLEDGE_CUTOFF: 0.3,
    TellCategory.PROMOTIONAL: 1.5,
    TellCategory.SIGNIFICANCE_INFLATION: 1.0,
    TellCategory.INVISIBLE_UNICODE: 0.3,
    TellCategory.HOMOGLYPH: 0.3,
    TellCategory.EMOJI_FORMATTING: 0.5,
    TellCategory.BOLD_OVERUSE: 3.0,
    TellCategory.CURLY_QUOTES: 8.0,
    TellCategory.STRUCTURAL: 1.0,
}


def compute_ai_score(report: ScanReport) -> float:
    """Compute a 0..1 AI-likelihood score for a report."""
    tokens = max(report.token_count, 1)
    score = 0.0
    for category, weight in WEIGHTS.items():
        count = report.per_category.get(category, 0)
        if count <= 0:
            continue
        density = count / tokens * 100.0
        threshold = THRESHOLDS[category]
        score += weight * min(1.0, density / threshold)
    return round(min(1.0, score), 4)
