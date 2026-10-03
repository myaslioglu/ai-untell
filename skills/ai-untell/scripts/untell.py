#!/usr/bin/env python3
"""Dependency-free CLI for the ai-untell engine vendored under scripts/ai_untell/.

Runs with nothing but the Python 3 standard library — no pip install of
ai-untell, click, rich or pyyaml needed. This is a thin argparse+print
re-implementation of the project's original click/rich CLI so the skill
works standalone on any machine.

The only optional dependency is for `humanize --llm`: --provider anthropic
needs the `anthropic` package, --provider openai needs `openai`. Both are
lazy-imported by the vendored code; a missing package, missing API key or
failed call exits with a clear error (exit code 2) instead of silently
falling back, unless --fallback is given. --provider ollama needs no package
(talks to localhost via urllib).

The vendored engine under ai_untell/ is generated from the project's
src/ai_untell by tools/build_skill.py; edit the source there, not here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_untell.cleaner import Cleaner  # noqa: E402
from ai_untell.humanizer import Humanizer  # noqa: E402
from ai_untell.llm.base import LLMError  # noqa: E402
from ai_untell.scanner import Scanner  # noqa: E402
from ai_untell.types import Config  # noqa: E402

DEMO_TEXT = """Certainly! Here's a comprehensive overview of this fascinating topic.

Coffee is not just a beverage — it's a cultural phenomenon that has shaped
societies across the globe. Moreover, it serves as a testament to humanity's
enduring relationship with this vibrant elixir. In today's fast-paced world,
coffee stands as a pivotal part of daily routines, offering a seamless blend of
flavor and energy. Furthermore, its impact on the global economy cannot be
understated — it underscores the crucial role that trade plays in our
interconnected landscape.

In conclusion, coffee represents a multifaceted tapestry of tradition,
innovation, and community. Whether you're a casual drinker or a dedicated
enthusiast, there's always something new to delve into.

Let me know if you have any questions!
"""


def _read_input(path: str | None, inline_text: str | None) -> tuple[str, Path | None]:
    if inline_text is not None:
        return inline_text, None
    if path is None or path == "-":
        return sys.stdin.read(), None
    p = Path(path)
    if not p.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    return p.read_text(encoding="utf-8"), p


def _build_config(args: argparse.Namespace) -> Config:
    config = Config()
    if getattr(args, "strength", None):
        config.synonym_strength = args.strength
    if getattr(args, "em_dash", None):
        config.em_dash_policy = args.em_dash
    if getattr(args, "double_dash", None):
        config.double_dash_policy = args.double_dash
    if getattr(args, "strip_emoji", False):
        config.strip_emoji = True
    if getattr(args, "straighten_quotes", False):
        config.curly_quotes = "straighten"
    if getattr(args, "remove_bold", False):
        config.bold_policy = "remove"
    if getattr(args, "clean_strings", False):
        config.preserve_code_strings = False
    config.llm_fallback = getattr(args, "fallback", False)
    config.use_llm = getattr(args, "llm", False)
    config.llm_provider = getattr(args, "provider", "anthropic")
    if getattr(args, "model", None):
        config.llm_model = args.model
    return config


def cmd_scan(args: argparse.Namespace) -> None:
    text, file_path = _read_input(args.path, args.text)
    report = Scanner().scan(text, path=file_path)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return

    print("=== AI Tell Report ===")
    print(f"Content kind : {report.content_kind.value}")
    print(f"Language     : {report.language.value}")
    print(f"Tokens       : {report.token_count}")
    print(f"AI score     : {report.ai_score:.3f}")
    print(f"Total hits   : {len(report.hits)}")

    if report.per_category:
        print("\nHits by category:")
        for category, count in sorted(report.per_category.items(), key=lambda kv: -kv[1]):
            print(f"  {category.value:<28} {count}")

    if args.verbose and report.hits:
        print("\nDetected tells:")
        for hit in report.hits[:200]:
            print(f"  [{hit.rule_id}] {hit.category.value}: {hit.matched!r}")

    verdict = "LIKELY AI" if report.ai_score >= 0.5 else "LOW AI SIGNAL"
    print(f"\nVerdict: {verdict} (score {report.ai_score:.3f})")


def cmd_clean(args: argparse.Namespace) -> None:
    if args.in_place and (args.path is None or args.path == "-" or args.text is not None):
        print("error: --in-place requires a real file path", file=sys.stderr)
        sys.exit(1)

    text, file_path = _read_input(args.path, args.text)
    config = _build_config(args)
    result = Cleaner(config).clean(text, path=file_path)

    if args.in_place and file_path is not None:
        changed = result.cleaned != text
        if changed:
            if not args.no_backup:
                file_path.with_suffix(file_path.suffix + ".bak").write_text(
                    text, encoding="utf-8"
                )
            file_path.write_text(result.cleaned, encoding="utf-8")
        print(f"Cleaned {file_path}: {'changed' if changed else 'no change'}.", file=sys.stderr)
        return

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    if args.path is None and args.text is None:
        sys.stdout.write(result.cleaned)
        return

    print(result.cleaned)
    if result.diff_stats:
        print(f"\nStats: {json.dumps(result.diff_stats, ensure_ascii=False)}", file=sys.stderr)
        print(f"Remaining tells: {len(result.remaining_hits)}", file=sys.stderr)


def cmd_humanize(args: argparse.Namespace) -> None:
    if args.in_place and (args.path is None or args.path == "-" or args.text is not None):
        print("error: --in-place requires a real file path", file=sys.stderr)
        sys.exit(1)

    text, file_path = _read_input(args.path, args.text)
    config = _build_config(args)
    try:
        result = Humanizer(config).humanize(text, path=file_path)
    except LLMError as exc:
        print(f"error: {exc} (nothing was written)", file=sys.stderr)
        sys.exit(2)

    if args.in_place and file_path is not None:
        changed = result.cleaned != text
        if changed:
            if not args.no_backup:
                file_path.with_suffix(file_path.suffix + ".bak").write_text(
                    text, encoding="utf-8"
                )
            file_path.write_text(result.cleaned, encoding="utf-8")
        print(
            f"Humanized {file_path} ({result.mode}): "
            f"{'changed' if changed else 'no change'}.",
            file=sys.stderr,
        )
        return

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    if args.path is None and args.text is None:
        sys.stdout.write(result.cleaned)
        return

    print(result.cleaned)
    print(f"\nMode: {result.mode}; remaining tells: {len(result.remaining_hits)}", file=sys.stderr)


def cmd_demo(_args: argparse.Namespace) -> None:
    print("Original text:\n")
    print(DEMO_TEXT)

    report = Scanner().scan(DEMO_TEXT)
    print(f"\nDetected {len(report.hits)} tells, AI score {report.ai_score:.3f}\n")

    result = Cleaner().clean(DEMO_TEXT)
    print("Cleaned text:\n")
    print(result.cleaned)

    after = Scanner().scan(result.cleaned)
    print(
        f"\nAfter cleaning: AI score {after.ai_score:.3f}, {len(after.hits)} tells remain."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="untell", description="Detect and remove AI writing tells.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Scan a file (or stdin with '-') for AI writing tells.")
    p_scan.add_argument("path", nargs="?")
    p_scan.add_argument("--text", dest="text", default=None, help="Scan inline text instead of a file.")
    p_scan.add_argument("--json", action="store_true", help="Emit a JSON report.")
    p_scan.add_argument("--verbose", "-v", action="store_true", help="List every detected tell.")
    p_scan.set_defaults(func=cmd_scan)

    p_clean = sub.add_parser("clean", help="Clean AI tells using deterministic rules.")
    p_clean.add_argument("path", nargs="?")
    p_clean.add_argument("--text", dest="text", default=None)
    p_clean.add_argument("--in-place", action="store_true", help="Rewrite the file (creates a .bak backup).")
    p_clean.add_argument("--no-backup", action="store_true")
    p_clean.add_argument("--strength", choices=["off", "light", "moderate", "aggressive"])
    p_clean.add_argument("--em-dash", choices=["auto", "keep", "comma", "period", "parens", "strip"])
    p_clean.add_argument("--double-dash", choices=["en_dash", "em_dash", "keep", "remove"])
    p_clean.add_argument("--strip-emoji", action="store_true")
    p_clean.add_argument("--straighten-quotes", action="store_true")
    p_clean.add_argument("--remove-bold", action="store_true")
    p_clean.add_argument("--clean-strings", action="store_true",
                         help="Also clean string literals in code (off by default: they are data).")
    p_clean.add_argument("--json", action="store_true")
    p_clean.set_defaults(func=cmd_clean)

    p_hum = sub.add_parser("humanize", help="Humanize text (LLM with --llm, else rule fallback).")
    p_hum.add_argument("path", nargs="?")
    p_hum.add_argument("--text", dest="text", default=None)
    p_hum.add_argument("--llm", action="store_true", help="Use an LLM provider for rewriting.")
    p_hum.add_argument("--provider", choices=["anthropic", "openai", "ollama"], default="anthropic")
    p_hum.add_argument("--model", default=None)
    p_hum.add_argument("--fallback", action="store_true",
                       help="Use rule-based cleaning if the LLM call fails instead of erroring.")
    p_hum.add_argument("--in-place", action="store_true")
    p_hum.add_argument("--no-backup", action="store_true")
    p_hum.add_argument("--strength", choices=["off", "light", "moderate", "aggressive"])
    p_hum.add_argument("--json", action="store_true")
    p_hum.set_defaults(func=cmd_humanize)

    p_demo = sub.add_parser("demo", help="Run scan + clean on a built-in AI-sounding sample.")
    p_demo.set_defaults(func=cmd_demo)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
