"""
Text preprocessing for TTS consumption.

Cleans raw PDF text, expands abbreviations, removes artefacts,
and splits into sentences.
"""

import re
from typing import List

# -----------------------------------------------------------------
# Abbreviation expansions (configurable)
# -----------------------------------------------------------------

ABBREVIATIONS = {
    "Fig.": "Figure",
    "fig.": "figure",
    "Figs.": "Figures",
    "figs.": "figures",
    "Eq.": "Equation",
    "eq.": "equation",
    "Eqs.": "Equations",
    "eqs.": "equations",
    "Sec.": "Section",
    "sec.": "section",
    "Chap.": "Chapter",
    "chap.": "chapter",
    "Vol.": "Volume",
    "vol.": "volume",
    "No.": "Number",
    "no.": "number",
    "Ref.": "Reference",
    "ref.": "reference",
    "Refs.": "References",
    "refs.": "references",
    "Dept.": "Department",
    "dept.": "department",
    "Approx.": "Approximately",
    "approx.": "approximately",
    "et al.": "and others",
    "i.e.": "that is",
    "e.g.": "for example",
    "vs.": "versus",
    "Dr.": "Doctor",
    "Prof.": "Professor",
    "Jr.": "Junior",
    "Sr.": "Senior",
    "St.": "Saint",
    "Govt.": "Government",
    "govt.": "government",
    "Assn.": "Association",
}

# -----------------------------------------------------------------
# Regex patterns
# -----------------------------------------------------------------

# Hyphenation at line break: "com-\nputer" → "computer"
_RE_HYPHEN_LINEBREAK = re.compile(r"(\w)-\s*\n\s*(\w)")

# Reference markers: [1], [2,3], [1-3], [12, 15]
_RE_REFERENCE_MARKER = re.compile(r"\s*\[\d+(?:\s*[,\-–]\s*\d+)*\]")

# URLs
_RE_URL = re.compile(
    r"https?://[^\s)<>\]\"']+"
    r"|www\.[^\s)<>\]\"']+",
    re.IGNORECASE,
)

# Multiple whitespace / newlines → single space
_RE_MULTI_WHITESPACE = re.compile(r"[ \t]+")
_RE_MULTI_NEWLINE = re.compile(r"\n\s*\n+")

# Sentence splitting — split on . ! ? followed by space + uppercase,
# but not after known abbreviations.  Python lookbehind requires
# fixed width, so we use a forward-scanning approach instead.
_SENT_ABBREVS = {
    "Mr",
    "Mrs",
    "Ms",
    "Dr",
    "Prof",
    "Jr",
    "Sr",
    "St",
    "vs",
    "etc",
    "al",
    "Vol",
    "No",
    "Fig",
    "Eq",
    "Sec",
    "Inc",
    "Corp",
    "Ltd",
    "Gen",
    "Gov",
    "Rep",
    "Sen",
}
_RE_SENTENCE_BOUNDARY = re.compile(
    r"([.!?])"  # sentence-ending punctuation
    r"(\s+)"  # whitespace
    r'(?=[A-Z"])'  # followed by uppercase or quote
)

# Ellipsis normalisation
_RE_ELLIPSIS = re.compile(r"\.{2,}|…")

# Em/en dash normalisation
_RE_DASHES = re.compile(r"[—–]")


# -----------------------------------------------------------------
# Public API
# -----------------------------------------------------------------


def clean_text(text: str, strip_references: bool = True) -> str:
    """
    Clean raw PDF block text for TTS synthesis.

    Steps:
    1. Rejoin hyphenated line breaks
    2. Normalise whitespace and newlines
    3. Optionally strip reference markers
    4. Replace URLs with "link to <domain>"
    5. Expand abbreviations
    6. Normalise dashes and ellipses
    7. Strip stray non-ASCII artefacts
    """
    if not text:
        return ""

    t = text

    # 1. Rejoin hyphenated words split across lines
    t = _RE_HYPHEN_LINEBREAK.sub(r"\1\2", t)

    # 2. Collapse newlines into spaces (PDF lines ≠ sentences)
    t = t.replace("\n", " ")
    t = _RE_MULTI_WHITESPACE.sub(" ", t)

    # 3. Strip reference markers
    if strip_references:
        t = _RE_REFERENCE_MARKER.sub("", t)

    # 4. Replace URLs
    def _url_to_speech(m):
        url = m.group(0)
        # Extract domain
        domain = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        return f"link to {domain}"

    t = _RE_URL.sub(_url_to_speech, t)

    # 5. Expand abbreviations (longest match first to handle "et al." etc.)
    for abbr, expansion in sorted(ABBREVIATIONS.items(), key=lambda x: -len(x[0])):
        t = t.replace(abbr, expansion)

    # 6. Normalise dashes and ellipses
    t = _RE_ELLIPSIS.sub("...", t)
    t = _RE_DASHES.sub(" — ", t)

    # 7. Final whitespace cleanup
    t = _RE_MULTI_WHITESPACE.sub(" ", t).strip()

    return t


def split_sentences(text: str) -> List[str]:
    """
    Split cleaned text into sentences.

    Uses a forward-scanning approach: finds candidate boundaries
    (punctuation + space + uppercase) and checks whether the word
    before the punctuation is a known abbreviation.

    Returns a list of non-empty sentence strings.
    """
    if not text:
        return []

    sentences = []
    last = 0

    for m in _RE_SENTENCE_BOUNDARY.finditer(text):
        # Check the word immediately before the punctuation
        start = m.start()
        preceding = text[max(0, start - 10) : start].rstrip()
        word_before = preceding.split()[-1] if preceding else ""

        if word_before in _SENT_ABBREVS:
            continue  # not a real sentence boundary

        # Split point is right after the punctuation
        split_at = m.start() + 1  # include the punctuation char
        sentence = text[last:split_at].strip()
        if sentence:
            sentences.append(sentence)
        last = split_at

    # Remainder
    tail = text[last:].strip()
    if tail:
        sentences.append(tail)

    return sentences


def preprocess_block(
    text: str,
    split: bool = True,
    strip_references: bool = True,
) -> List[str]:
    """
    Full preprocessing: clean + optionally split into sentences.

    Args:
        text:             Raw block text.
        split:            If True, return per-sentence list.
                          If False, return single-element list.
        strip_references: Remove [1]-style citation markers.

    Returns:
        List of cleaned text segments.
    """
    cleaned = clean_text(text, strip_references=strip_references)
    if not cleaned:
        return []

    if split:
        return split_sentences(cleaned)
    return [cleaned]
