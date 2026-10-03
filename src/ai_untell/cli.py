"""Command-line interface for ai-untell."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ai_untell.cleaner import Cleaner
from ai_untell.humanizer import Humanizer
from ai_untell.scanner import Scanner
from ai_untell.types import Config

console = Console()
err_console = Console(stderr=True)

DEMO_TEXT = """Certainly! Here's a comprehensive overview of this fascinating topic.

Coffee is not just a beverage \u2014 it's a cultural phenomenon that has shaped
societies across the globe. Moreover, it serves as a testament to humanity's
enduring relationship with this vibrant elixir. In today's fast-paced world,
coffee stands as a pivotal part of daily routines, offering a seamless blend of
flavor and energy. Furthermore, its impact on the global economy cannot be
understated \u2014 it underscores the crucial role that trade plays in our
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
        raise click.ClickException(f"file not found: {path}")
    return p.read_text(encoding="utf-8"), p


def _build_config(
    strength: str | None = None,
    em_dash: str | None = None,
    double_dash: str | None = None,
    strip_emoji: bool = False,
    straighten_quotes: bool = False,
    remove_bold: bool = False,
    use_llm: bool = False,
    provider: str = "anthropic",
    model: str | None = None,
) -> Config:
    config = Config()
    if strength:
        config.synonym_strength = strength  # type: ignore[assignment]
    if em_dash:
        config.em_dash_policy = em_dash  # type: ignore[assignment]
    if double_dash:
        config.double_dash_policy = double_dash  # type: ignore[assignment]
    if strip_emoji:
        config.strip_emoji = True
    if straighten_quotes:
        config.curly_quotes = "straighten"
    if remove_bold:
        config.bold_policy = "remove"
    config.use_llm = use_llm
    config.llm_provider = provider  # type: ignore[assignment]
    if model:
        config.llm_model = model
    return config


@click.group()
@click.version_option(package_name="ai-untell")
def cli() -> None:
    """ai-untell: detect and remove AI writing tells from text and code.

    Scans for em dashes, AI vocabulary, chatbot openers/closers, invisible
    Unicode, homoglyphs and more; cleans them deterministically; optionally
    humanizes via an LLM to jam statistical watermarks.
    """


@cli.command()
@click.argument("path", required=False)
@click.option("--text", "inline_text", default=None, help="Scan inline text instead of a file.")
@click.option("--json", "as_json", is_flag=True, help="Emit a JSON report.")
@click.option("--verbose", "-v", is_flag=True, help="List every detected tell.")
def scan(path: str | None, inline_text: str | None, as_json: bool, verbose: bool) -> None:
    """Scan a file (or stdin with '-') for AI writing tells."""
    text, file_path = _read_input(path, inline_text)
    report = Scanner().scan(text, path=file_path)

    if as_json:
        click.echo(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return

    table = Table(title="AI Tell Report")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Content kind", report.content_kind.value)
    table.add_row("Language", report.language.value)
    table.add_row("Tokens", str(report.token_count))
    table.add_row("AI score", f"{report.ai_score:.3f}")
    table.add_row("Total hits", str(len(report.hits)))
    console.print(table)

    if report.per_category:
        cat_table = Table(title="Hits by category")
        cat_table.add_column("Category", style="magenta")
        cat_table.add_column("Count", justify="right")
        for category, count in sorted(
            report.per_category.items(), key=lambda kv: -kv[1]
        ):
            cat_table.add_row(category.value, str(count))
        console.print(cat_table)

    if verbose and report.hits:
        hit_table = Table(title="Detected tells")
        hit_table.add_column("Rule", style="green")
        hit_table.add_column("Category")
        hit_table.add_column("Matched", style="yellow")
        for hit in report.hits[:200]:
            hit_table.add_row(hit.rule_id, hit.category.value, repr(hit.matched)[:60])
        console.print(hit_table)

    verdict = "LIKELY AI" if report.ai_score >= 0.5 else "LOW AI SIGNAL"
    console.print(f"\nVerdict: [bold]{verdict}[/bold] (score {report.ai_score:.3f})")


@cli.command()
@click.argument("path", required=False)
@click.option("--text", "inline_text", default=None)
@click.option("--in-place", is_flag=True, help="Rewrite the file (creates a .bak backup).")
@click.option("--no-backup", is_flag=True, help="Skip the .bak backup with --in-place.")
@click.option("--strength", type=click.Choice(["off", "light", "moderate", "aggressive"]))
@click.option(
    "--em-dash",
    type=click.Choice(["auto", "keep", "comma", "period", "parens", "strip"]),
)
@click.option("--double-dash", type=click.Choice(["en_dash", "em_dash", "keep", "remove"]))
@click.option("--strip-emoji", is_flag=True)
@click.option("--straighten-quotes", is_flag=True)
@click.option("--remove-bold", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
def clean(
    path: str | None,
    inline_text: str | None,
    in_place: bool,
    no_backup: bool,
    strength: str | None,
    em_dash: str | None,
    double_dash: str | None,
    strip_emoji: bool,
    straighten_quotes: bool,
    remove_bold: bool,
    as_json: bool,
) -> None:
    """Clean AI tells from a file (or stdin with '-') using deterministic rules."""
    if in_place and (path is None or path == "-" or inline_text is not None):
        raise click.ClickException("--in-place requires a real file path")

    text, file_path = _read_input(path, inline_text)
    config = _build_config(strength, em_dash, double_dash, strip_emoji,
                           straighten_quotes, remove_bold)
    result = Cleaner(config).clean(text, path=file_path)

    if in_place and file_path is not None:
        changed = result.cleaned != text
        if changed:
            if not no_backup:
                file_path.with_suffix(file_path.suffix + ".bak").write_text(
                    text, encoding="utf-8"
                )
            file_path.write_text(result.cleaned, encoding="utf-8")
        err_console.print(
            f"Cleaned {file_path}: {'changed' if changed else 'no change'}."
        )
        return

    if as_json:
        click.echo(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    if path is None and inline_text is None:
        sys.stdout.write(result.cleaned)
        return

    click.echo(result.cleaned)
    if result.diff_stats:
        err_console.print(f"\nStats: {json.dumps(result.diff_stats, ensure_ascii=False)}")
        err_console.print(f"Remaining tells: {len(result.remaining_hits)}")


@cli.command()
@click.argument("path", required=False)
@click.option("--text", "inline_text", default=None)
@click.option("--llm", "use_llm", is_flag=True, help="Use an LLM provider for rewriting.")
@click.option("--provider", type=click.Choice(["anthropic", "openai", "ollama"]),
              default="anthropic")
@click.option("--model", default=None, help="Model name for the provider.")
@click.option("--in-place", is_flag=True)
@click.option("--no-backup", is_flag=True)
@click.option("--strength", type=click.Choice(["off", "light", "moderate", "aggressive"]))
@click.option("--json", "as_json", is_flag=True)
def humanize(
    path: str | None,
    inline_text: str | None,
    use_llm: bool,
    provider: str,
    model: str | None,
    in_place: bool,
    no_backup: bool,
    strength: str | None,
    as_json: bool,
) -> None:
    """Humanize a file (or stdin). Uses an LLM with --llm, else rule fallback."""
    if in_place and (path is None or path == "-" or inline_text is not None):
        raise click.ClickException("--in-place requires a real file path")

    text, file_path = _read_input(path, inline_text)
    config = _build_config(strength=strength, use_llm=use_llm, provider=provider, model=model)
    result = Humanizer(config).humanize(text, path=file_path)

    if in_place and file_path is not None:
        changed = result.cleaned != text
        if changed:
            if not no_backup:
                file_path.with_suffix(file_path.suffix + ".bak").write_text(
                    text, encoding="utf-8"
                )
            file_path.write_text(result.cleaned, encoding="utf-8")
        err_console.print(
            f"Humanized {file_path} ({result.mode}): "
            f"{'changed' if changed else 'no change'}."
        )
        return

    if as_json:
        click.echo(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    if path is None and inline_text is None:
        sys.stdout.write(result.cleaned)
        return

    click.echo(result.cleaned)
    err_console.print(f"\nMode: {result.mode}; remaining tells: {len(result.remaining_hits)}")


@cli.command()
def demo() -> None:
    """Run scan + clean on a built-in AI-sounding sample."""
    console.print("[bold]Original text:[/bold]\n")
    console.print(DEMO_TEXT)

    report = Scanner().scan(DEMO_TEXT)
    console.print(f"\nDetected [bold]{len(report.hits)}[/bold] tells, "
                  f"AI score [bold]{report.ai_score:.3f}[/bold]\n")

    result = Cleaner().clean(DEMO_TEXT)
    console.print("[bold]Cleaned text:[/bold]\n")
    console.print(result.cleaned)

    after = Scanner().scan(result.cleaned)
    console.print(f"\nAfter cleaning: AI score [bold]{after.ai_score:.3f}[/bold], "
                  f"{len(after.hits)} tells remain.")
