"""Scan a text file and print the AI tell report."""
from pathlib import Path

from ai_untell import scan_file

FIXTURE = (
    Path(__file__).parent.parent
    / "tests" / "fixtures" / "sample_texts" / "known_ai_paragraph.md"
)


def main() -> None:
    report = scan_file(FIXTURE)
    print(f"File: {FIXTURE.name}")
    print(f"Content kind: {report.content_kind.value}")
    print(f"Tokens: {report.token_count}")
    print(f"AI score: {report.ai_score:.3f}")
    print(f"Total hits: {len(report.hits)}")
    print("\nHits by category:")
    for category, count in sorted(report.per_category.items(), key=lambda kv: -kv[1]):
        print(f"  {category.value}: {count}")
    print("\nFirst 10 hits:")
    for hit in report.hits[:10]:
        print(f"  [{hit.rule_id}] {hit.category.value}: {hit.matched!r}")


if __name__ == "__main__":
    main()
