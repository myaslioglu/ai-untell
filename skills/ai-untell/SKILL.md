---
name: ai-untell
description: Detects and removes AI writing tells from text or code — em dash overuse, AI buzzwords ("delve", "leverage", "utilize", "seamless", "tapestry"...), chatbot openers/closers ("Certainly!", "Let me know if you have any questions!"), copula avoidance, negative parallelism, invisible Unicode watermark characters, and homoglyphs — then optionally rewrites the text to sound human and break statistical watermarks. Use whenever the user asks to check whether a text "sounds AI" / "sounds like ChatGPT" or wants an AI score, before publishing a blog post, email, PR description, README, or essay drafted with an LLM, when they ask to strip em dashes or AI vocabulary, or ask to "humanize" text. Also trigger on Turkish requests like "bu metin AI gibi duruyor mu", "em dash'leri temizle", "bunu insansılaştır". Prefer this over manually eyeballing text for AI tells.
---

# ai-untell

Detect and remove AI writing tells from text and code. The engine is bundled
under `scripts/` and needs nothing but `python3` (3.10+, standard library
only): no pip install, no network, no API key.

## Locating the script

The script lives next to this file at `scripts/untell.py`:

```bash
UNTELL="${CLAUDE_SKILL_DIR}/scripts/untell.py"
```

If `${CLAUDE_SKILL_DIR}` was not substituted with a real path (for example on
claude.ai, or when the variable is empty), use the directory this SKILL.md was
loaded from instead. If that is unknown, find it:

```bash
UNTELL="$(ls /mnt/skills/*/ai-untell/scripts/untell.py 2>/dev/null | head -1)"
[ -n "$UNTELL" ] || UNTELL="$(find / -path '*/ai-untell/scripts/untell.py' -not -path '*/node_modules/*' 2>/dev/null | head -1)"
```

Then run every command below as `python3 "$UNTELL" <command> ...`.

## Commands

### `scan`: detect tells and compute an AI score

```bash
python3 "$UNTELL" scan <file>
python3 "$UNTELL" scan --text "<inline text>"
python3 "$UNTELL" scan <file> --json -v   # full JSON report + every hit listed
```

Always report the **AI score** and the verdict: `>= 0.5` is "LIKELY AI",
`< 0.5` is "LOW AI SIGNAL". With `-v`/`--verbose` (or `--json`), also
summarize the top categories that fired (e.g. `ai_vocab`, `dash_overuse`,
`chatbot_opener`) so the user knows *why* it scored the way it did.

### `clean`: deterministic, offline rewrite

```bash
python3 "$UNTELL" clean <file>                              # prints to stdout
python3 "$UNTELL" clean <file> --in-place                    # rewrites, keeps a .bak backup
python3 "$UNTELL" clean <file> --strength moderate            # light|moderate|aggressive (default: light)
python3 "$UNTELL" clean <file> --em-dash period --double-dash remove
python3 "$UNTELL" clean --text "<inline text>"
cat <file> | python3 "$UNTELL" clean -                        # stdin -> stdout
```

Key options:
- `--strength off|light|moderate|aggressive`: how aggressively to swap AI vocabulary for plainer synonyms.
- `--em-dash auto|keep|comma|period|parens|strip`: how to rewrite em dashes. `auto`/`comma` turn them into commas, `period` splits the sentence, `parens` turns a pair of dashes around an aside into parentheses.
- `--double-dash en_dash|em_dash|keep|remove`: how to rewrite a `--` used as a dash (command-line flags like `--help` and table separators are never touched).
- `--strip-emoji`, `--straighten-quotes`, `--remove-bold`: optional formatting cleanups.
- `--clean-strings`: also clean string literals in source code. Off by default because strings are program data.

Use `--in-place` when the user gives a real file and wants it edited directly;
otherwise print the cleaned text and leave the original file alone.

### `demo`: shows the whole pipeline on a built-in sample

```bash
python3 "$UNTELL" demo
```

## Humanizing (full rewrite)

Rule-based `clean` fixes surface tells but cannot remove token-level
statistical watermarks (Kirchenbauer green-list, Aaronson Gumbel-max); only a
real paraphrase does. When the user wants a full rewrite or mentions
watermarks/detectors, **do the rewrite yourself**. You are already a
different model from the one that produced the text, which is exactly what
breaks the watermark:

1. `scan` the original and note the categories that fired.
2. Rewrite the text following these rules:
   - Keep every fact, number, name, date, quote, citation and technical detail.
   - Remove em dashes, stock vocabulary (delve, leverage, foster, harness,
     multifaceted, tapestry, realm, holistic, comprehensive, seamless, robust,
     pivotal, crucial, testament, moreover, furthermore, in conclusion),
     "serves as"/"stands as", "not just X, it's Y", rule-of-three cadence,
     chatbot openers/closers and significance inflation.
   - Use plain, concrete words and mix short and long sentences.
   - Do not add headings, bullets, bold or emoji the source did not have.
   - Keep code blocks, inline code and identifiers exactly as they are.
3. `scan` your rewrite (`--text` or a temp file) and fix whatever still
   fires. Report the before/after scores.

Only use the bundled `humanize --llm` command when the user explicitly asks
for a specific external model (Anthropic API, OpenAI, or a local Ollama):

```bash
python3 "$UNTELL" humanize <file> --llm --provider anthropic   # needs ANTHROPIC_API_KEY + `anthropic` package
python3 "$UNTELL" humanize <file> --llm --provider openai --model gpt-4o-mini
python3 "$UNTELL" humanize <file> --llm --provider ollama --model llama3.1
```

If the provider is not available it exits with a clear error (exit code 2)
and writes nothing; tell the user, and offer to do the rewrite yourself.
`--fallback` switches to rule-based cleaning instead of erroring. Without
`--llm`, `humanize` is the same as `clean`.

## What it guarantees

- **Code is not broken.** In source files only comments and docstrings are
  edited; identifiers, keywords, syntax and string literals are left alone
  (unless `--clean-strings`). Language is detected from the extension
  (Python, JS/TS, Go, Rust, Java, C#, C/C++) or from real syntax.
- **Markdown code stays intact.** Fenced code blocks (including unclosed
  ones) and inline `code spans` are skipped when cleaning prose.
- Homoglyph normalization (Cyrillic/Greek look-alikes to Latin) only runs on
  documents that are already mostly Latin script, so real Cyrillic/Greek text
  is left alone.

## Working without a file

If the user gives raw text instead of a file, use `--text "<text>"` (or pipe
it through stdin with `-` for long or quote-heavy text). If they haven't given
either a file path or text, ask which one they mean before running anything.

## When output is long

`--json` dumps the full structured report (every hit, offsets, suggestions).
Prefer the plain-text summary for a quick answer and only reach for `--json`
when the user wants the raw data or you need to reason over every hit.
