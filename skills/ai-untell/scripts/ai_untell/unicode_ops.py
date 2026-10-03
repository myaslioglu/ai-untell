"""Unicode hygiene: invisible characters, homoglyphs, normalization.

Invisible/format characters are a known carrier for steganographic markers and
are strong "AI tell" signals when found inside prose or code. Homoglyphs
(visually identical characters from other scripts, e.g. Cyrillic "а" vs Latin
"a") are used to dodge similarity detectors; they also break code identifiers.
"""
from __future__ import annotations

import unicodedata

# ---------------------------------------------------------------------------
# Invisible / zero-width / formatting characters
# ---------------------------------------------------------------------------

INVISIBLE_CHAR_NAMES: dict[str, str] = {
    "\u00ad": "SOFT HYPHEN",
    "\u034f": "COMBINING GRAPHEME JOINER",
    "\u061c": "ARABIC LETTER MARK",
    "\u115f": "HANGUL CHOSEONG FILLER",
    "\u1160": "HANGUL JUNGSEONG FILLER",
    "\u17b4": "KHMER VOWEL INHERENT AQ",
    "\u17b5": "KHMER VOWEL INHERENT AA",
    "\u180e": "MONGOLIAN VOWEL SEPARATOR",
    "\u200b": "ZERO WIDTH SPACE",
    "\u200c": "ZERO WIDTH NON-JOINER",
    "\u200d": "ZERO WIDTH JOINER",
    "\u200e": "LEFT-TO-RIGHT MARK",
    "\u200f": "RIGHT-TO-LEFT MARK",
    "\u2060": "WORD JOINER",
    "\u2061": "FUNCTION APPLICATION",
    "\u2062": "INVISIBLE TIMES",
    "\u2063": "INVISIBLE SEPARATOR",
    "\u2064": "INVISIBLE PLUS",
    "\u3164": "HANGUL FILLER",
    "\ufeff": "ZERO WIDTH NO-BREAK SPACE (BOM)",
    "\ufff9": "INTERLINEAR ANNOTATION ANCHOR",
    "\ufffa": "INTERLINEAR ANNOTATION SEPARATOR",
    "\ufffb": "INTERLINEAR ANNOTATION TERMINATOR",
}

# Bidi embedding controls U+202A..U+202E and isolates U+2066..U+2069,
# plus deprecated formatting chars U+206A..U+206F.
for _cp in list(range(0x202A, 0x202F)) + list(range(0x2066, 0x2070)):
    INVISIBLE_CHAR_NAMES.setdefault(
        chr(_cp), unicodedata.name(chr(_cp), f"U+{_cp:04X}")
    )

# Unicode Tags block U+E0000..U+E007F - a favourite steganography carrier.
TAG_BLOCK_RANGE = range(0xE0000, 0xE0080)

VARIATION_SELECTOR_RANGE = range(0xFE00, 0xFE10)


def _is_emoji_like(ch: str) -> bool:
    """Rough check for codepoints that commonly join via ZWJ/VS16."""
    if not ch:
        return False
    cp = ord(ch)
    return (
        0x1F000 <= cp <= 0x1FAFF
        or 0x2600 <= cp <= 0x27BF
        or 0x2B00 <= cp <= 0x2BFF
        or 0x1F1E6 <= cp <= 0x1F1FF
        or cp == 0xFE0F
        or 0x2764 <= cp <= 0x2767
        or cp in (0x200D, 0x2640, 0x2642, 0x2695, 0x2696, 0x2708)
    )


def find_invisible(text: str) -> dict[str, list[int]]:
    """Return {character: [offset, ...]} for every invisible char found."""
    found: dict[str, list[int]] = {}
    for i, ch in enumerate(text):
        if ch in INVISIBLE_CHAR_NAMES or ord(ch) in TAG_BLOCK_RANGE:
            found.setdefault(ch, []).append(i)
    return found


def strip_invisible(
    text: str,
    *,
    strip_variation_selectors: bool = False,
) -> tuple[str, dict[str, int]]:
    """Remove invisible/format characters.

    ZWJ and variation selectors are preserved when they sit between/after
    emoji-like codepoints, so emoji sequences (family glyphs, keycaps) are
    not mangled. Returns (clean_text, counts_by_char_name).
    """
    out: list[str] = []
    counts: dict[str, int] = {}
    n = len(text)
    for i, ch in enumerate(text):
        cp = ord(ch)
        keep = False
        if ch == "\u200d":  # ZWJ: keep inside emoji sequences
            prev_ch = out[-1] if out else ""
            next_ch = text[i + 1] if i + 1 < n else ""
            keep = _is_emoji_like(prev_ch) and _is_emoji_like(next_ch)
        elif cp in VARIATION_SELECTOR_RANGE:
            prev_ch = out[-1] if out else ""
            keep = not strip_variation_selectors and _is_emoji_like(prev_ch)
        elif ch in INVISIBLE_CHAR_NAMES or cp in TAG_BLOCK_RANGE:
            keep = False
        else:
            keep = True

        if keep:
            out.append(ch)
        else:
            if cp in TAG_BLOCK_RANGE:
                default_name = f"U+{cp:04X} TAG"
            else:
                default_name = f"U+{cp:04X}"
            name = INVISIBLE_CHAR_NAMES.get(ch, default_name)
            counts[name] = counts.get(name, 0) + 1
    return "".join(out), counts



# ---------------------------------------------------------------------------
# Homoglyphs: visually identical characters from other scripts
# ---------------------------------------------------------------------------

HOMOGLYPH_MAP: dict[str, str] = {
    # Cyrillic -> Latin (single letters only, safe in Latin-dominant docs)
    "\u0430": "a", "\u0410": "A",  # а А
    "\u0435": "e", "\u0415": "E",  # е Е
    "\u043e": "o", "\u041e": "O",  # о О
    "\u0440": "p", "\u0420": "P",  # р Р
    "\u0441": "c", "\u0421": "C",  # с С
    "\u0445": "x", "\u0425": "X",  # х Х
    "\u0443": "y", "\u0423": "Y",  # у У
    "\u0456": "i", "\u0406": "I",  # і І
    "\u0458": "j", "\u0408": "J",  # ј Ј
    "\u0455": "s", "\u0405": "S",  # ѕ Ѕ
    "\u0501": "d", "\u0503": "d",  # ԁ ԃ
    "\u051d": "w", "\u051b": "q",  # ԝ ԛ
    "\u04bb": "h", "\u04ba": "H",  # һ Һ
    "\u04d9": "e", "\u04d8": "E",  # ә Ә
    "\u04e9": "o", "\u04e8": "O",  # ө Ө
    "\u04af": "y", "\u04ae": "Y",  # ү Ү
    "\u0513": "d",  # ԓ
    # Greek -> Latin (confusable letters only)
    "\u03bf": "o", "\u039f": "O",  # ο Ο
    "\u03b1": "a", "\u0391": "A",  # α Α
    "\u03b9": "i", "\u0399": "I",  # ι Ι
    "\u03c1": "p", "\u03a1": "P",  # ρ Ρ
    "\u03c4": "t", "\u03a4": "T",  # τ Τ
    "\u03bd": "v", "\u039d": "N",  # ν Ν
    "\u03b2": "b", "\u0392": "B",  # β Β
    "\u0395": "E",  # Ε
    "\u039a": "K",  # Κ
    "\u039c": "M",  # Μ
    "\u03a7": "X",  # Χ
    "\u03a5": "Y",  # Υ
    "\u0396": "Z",  # Ζ
    "\u0397": "H",  # Η
    # Punctuation lookalikes
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2015": "-",  # horizontal bar
    "\uff0d": "-",  # fullwidth hyphen-minus
    "\uff0e": ".",  # fullwidth full stop
    "\uff0c": ",",  # fullwidth comma
    "\uff1a": ":",  # fullwidth colon
    "\uff1b": ";",  # fullwidth semicolon
    "\u00a0": " ",  # no-break space
    "\u2000": " ",  # en quad .. thin spaces
    "\u2001": " ", "\u2002": " ", "\u2003": " ", "\u2004": " ",
    "\u2005": " ", "\u2006": " ", "\u2007": " ", "\u2008": " ",
    "\u2009": " ", "\u200a": " ", "\u202f": " ", "\u205f": " ",
    "\u3000": " ",  # ideographic space
    # Fullwidth Latin letters/digits A-Z a-z 0-9
    **{chr(cp): chr(cp - 0xFEE0) for cp in range(0xFF01, 0xFF5F)},
}


def normalize_homoglyphs(text: str) -> tuple[str, int]:
    """Replace known homoglyphs with their Latin/ASCII equivalents."""
    out: list[str] = []
    count = 0
    for ch in text:
        repl = HOMOGLYPH_MAP.get(ch)
        if repl is not None and repl != ch:
            out.append(repl)
            count += 1
        else:
            out.append(ch)
    return "".join(out), count


def find_homoglyphs(text: str) -> list[tuple[int, str]]:
    """Return [(offset, char)] for every homoglyph present."""
    return [(i, ch) for i, ch in enumerate(text) if HOMOGLYPH_MAP.get(ch, ch) != ch]


def latin_ratio(text: str) -> float:
    """Fraction of letters that are Latin (vs Cyrillic/Greek/other).

    Used as a safety gate: homoglyph normalization is only applied when a
    document is clearly Latin-script, to avoid mangling genuine Cyrillic or
    Greek text.
    """
    latin = 0
    other = 0
    for ch in text:
        if not ch.isalpha():
            continue
        try:
            name = unicodedata.name(ch, "")
        except ValueError:
            name = ""
        if "LATIN" in name:
            latin += 1
        elif any(s in name for s in ("CYRILLIC", "GREEK")):
            other += 1
    total = latin + other
    if total == 0:
        return 1.0
    return latin / total


def nfc_normalize(text: str) -> str:
    """Apply Unicode NFC normalization."""
    return unicodedata.normalize("NFC", text)
