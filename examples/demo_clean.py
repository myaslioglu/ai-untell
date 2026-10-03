"""Clean an AI-sounding file and show before/after scores."""
from pathlib import Path

from ai_untell import Config, clean_file, scan_file

FIXTURE = (
    Path(__file__).parent.parent
    / "tests" / "fixtures" / "sample_texts" / "known_ai_paragraph.md"
)


def main() -> None:
    before = scan_file(FIXTURE)
    print(f"Before: AI score {before.ai_score:.3f}, {len(before.hits)} tells\n")

    config = Config(synonym_strength="moderate")
    result = clean_file(FIXTURE, config=config)
    print("Cleaned text:\n" + "-" * 40)
    print(result.cleaned)
    print("-" * 40)

    from ai_untell import scan

    after = scan(result.cleaned)
    print(f"\nAfter:  AI score {after.ai_score:.3f}, {len(after.hits)} tells remain")
    print(f"Diff stats: {result.diff_stats}")


if __name__ == "__main__":
    main()
