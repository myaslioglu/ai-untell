# Research: Claude / LLM Watermarking and AI Writing Tells

This document summarizes the research that shaped `ai-untell`. Sources:
Anthropic official channels, arXiv papers, Wikipedia's WikiProject AI Cleanup,
and open-source watermarking/humanizer repositories (retrieved 2026-09).

## 1. Does Claude actually watermark its output?

**Short answer: there is no publicly confirmed production watermark.**

- Anthropic's Sonnet 4.5 announcement, Claude Code docs, Consumer Terms of
  Service and "Core views on AI safety" contain **no statement** about an
  active output watermark. Nothing in the Responsible Scaling Policy commits
  to one either.
- The Claude Code documentation describes checkpoints, context editing, memory
  tools and the Agent SDK — no code watermarking feature.
- However, watermarking research is strongly associated with Anthropic: Scott
  Aaronson (then at Anthropic) publicly described a cryptographic watermarking
  scheme for LLMs, and it is widely believed to be the design Anthropic would
  deploy if/when it chooses to.

**Implication for this tool:** we cannot detect or strip a Claude-specific
watermark because none is publicly documented. The practical attack surface is
(a) visible stylistic tells, (b) invisible Unicode carriers, (c) generic
token-level statistical watermarks via paraphrase "jamming".

## 2. Token-level statistical watermarks (the real watermark tech)

### 2.1 Kirchenbauer et al. — "A Watermark for Large Language Models"
(arXiv:2301.10226, ICML 2023; official repo `jwkirchenbauer/lm-watermarking`)

- Before sampling each token, a PRF keyed on the previous tokens selects a
  random "green list" (~25-50% of the vocabulary).
- Sampling softly promotes green tokens by adding delta to their logits.
- Detection is an open z-test on the green-token fraction; it needs the
  vocabulary and seeding scheme but **not** model access.
- Reference implementation: `WatermarkLogitsProcessor` / `WatermarkDetector`
  as a HuggingFace `LogitsProcessor`; supports `selfhash`/`minhash` seeding.

### 2.2 Aaronson scheme (Gumbel-max / exponential-min sampling)

- For logit vector `l` and PRF-derived uniforms `r_i`, sample
  `token = argmax_i (l_i - (-log r_i))` (equivalently argmin of exponentials).
- Detection: the provider recomputes `r_i` from the token history and tests
  whether the sum of `-log(-log r_i)` is skewed — a zero-bit, key-based test.
  Undetectable without the PRF key.

### 2.3 Reliability and attacks
(arXiv:2306.04634, "On the Reliability of Watermarks", ICLR 2024)

- Watermarks survive human editing and machine paraphrasing, but paraphrases
  leak n-grams; detection confidence scales with observed token count
  (~800 tokens at 1e-5 FPR after strong human paraphrase).
- Known attacks: paraphrase/spinning, translation round-trips, Dipper-style
  sentence paraphrasers, token substitution, truncation. **Paraphrasing is the
  canonical "jammer"** — which is exactly what our `humanize --llm` mode does.

## 3. Visible AI tells (what we can actually clean)

Wikipedia's **"Signs of AI writing"** (WikiProject AI Cleanup) catalogues ~35
recurring patterns observed in thousands of LLM outputs. The community
`blader/humanizer` skill (39.8k stars) encodes these 35 patterns. Categories:

- **Em-dash overuse** — the single most discussed Claude tell; spaced em dashes
  between clauses at rates far above human baselines. Includes double hyphens
  `--` left over from markdown habits.
- **AI vocabulary** — delve, leverage, utilize, foster, facilitate, streamline,
  harness, tapestry, realm, holistic, multifaceted, seamless, robust, pivotal,
  crucial, testament, moreover, furthermore, in conclusion, game-changer,
  cutting-edge, transformative, paradigm, synergy, etc.
- **Copula avoidance** — "serves as", "stands as", "functions as" instead of
  "is"; studies measured >10% drop of "is/are" in 2023 academic writing.
- **Negative parallelisms** — "not just X, it's Y", "not only X but also Y".
- **Rule of three** — triplet cadence ("streamlining, optimizing, and
  enhancing").
- **Chatbot artifacts** — openers ("Certainly!", "Here's a comprehensive
  overview..."), closers ("Let me know if you have any questions!"), knowledge
  cutoff disclaimers ("As an AI language model...").
- **Significance inflation** — "marks a pivotal moment", "stands as a
  testament", "shaping the future of".
- **Style tics** — bold overuse, emoji bullets, curly quotes, title case
  headings, inline-header lists.

## 4. Invisible carriers (steganography surface)

- Zero-width space U+200B, ZWNJ U+200C, ZWJ U+200D, LRM/RLM U+200E/F, word
  joiner U+2060, invisible operators U+2061-2064, soft hyphen U+00AD, BOM
  U+FEFF, bidi controls, and the **Tags block U+E0000-E007F** (a known
  steganography carrier used to smuggle bits through text).
- **Homoglyphs** — Cyrillic/Greek lookalikes of Latin letters (a/o/e/p/c/x)
  used to dodge similarity detection; they also break identifiers in code. The
  Kirchenbauer repo ships a homoglyph attack module.
- These are detectable deterministically and stripped safely — implemented in
  `unicode_ops.py`.

## 5. Existing tools surveyed

- `jwkirchenbauer/lm-watermarking` — reference green-list watermark + detector.
- `blader/humanizer` — Markdown skill, 35 Wikipedia patterns, 39.8k stars.
- `harshaneel/humanize` — research-grounded skill with 9 "levers", 50+ sources.
- GPTZero et al. — classifier detectors (perplexity, burstiness, stylometry);
  Pangram Labs' analyses show perplexity/burstiness alone are weak, while
  trained classifiers remain effective — so surface rewriting alone is not a
  guaranteed bypass, which motivates the optional LLM paraphrase layer.

## 6. Conclusions -> design decisions

1. Since no Claude production watermark is documented, the tool's default
   value is **visible tell removal + invisible carrier stripping**, both
   deterministic, offline and safe for code (identifiers never touched).
2. **Statistical watermark jamming** is implemented as LLM paraphrase
   (`humanize --llm`), the canonical attack in the literature.
3. Rule-based synonym substitution uses lemma tables + an inflection engine to
   avoid grammar breakage; adjectives that merely look inflected are
   blocklisted.
4. Code handling is segment-based (state-machine extraction of comments,
   docstrings, string literals per language) so replacements never touch code
   syntax.

- Detection of these watermarks without the key/model is not possible;
  third-party "AI detectors" (GPTZero etc.) are classifier-based stylometry,
  not watermark decoders.
