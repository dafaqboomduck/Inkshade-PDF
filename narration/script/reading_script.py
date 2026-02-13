"""
Builds an ordered reading script from classified blocks.

The script is a flat list of ReadingInstruction objects that the TTS
engine and audio builder consume sequentially.
"""

from typing import Dict, List, Optional, Tuple

from narration.layout.models import ClassifiedBlock, LayoutLabel

from .models import (
    LABEL_TO_ROLE,
    ProsodyRule,
    ReadingInstruction,
    TextRole,
)
from .prosody_rules import SENTENCE_PAUSE, get_prosody
from .text_preprocessor import preprocess_block


def _block_sort_key(cb: ClassifiedBlock) -> Tuple[float, float]:
    """Sort blocks top-to-bottom, then left-to-right."""
    return (cb.bbox[1], cb.bbox[0])


def build_page_script(
    classified_blocks: List[ClassifiedBlock],
    page_index: int,
    speed_multiplier: float = 1.0,
    pause_multiplier: float = 1.0,
    skip_footnotes: bool = True,
    skip_captions: bool = False,
    strip_references: bool = True,
) -> List[ReadingInstruction]:
    """
    Convert classified blocks for one page into reading instructions.

    Body-text blocks are split into per-sentence instructions.
    Titles and headings remain as single instructions.
    Skipped blocks produce no instructions.

    Args:
        classified_blocks: Output from the classifier for this page.
        page_index:        0-based page number.
        speed_multiplier:  Global speed scaling.
        pause_multiplier:  Global pause scaling.
        skip_footnotes:    If True, footnotes are skipped.
        skip_captions:     If True, captions are skipped.
        strip_references:  Remove [N] citation markers from text.

    Returns:
        Ordered list of ReadingInstruction.
    """
    instructions: List[ReadingInstruction] = []

    # Sort blocks by reading order
    sorted_blocks = sorted(classified_blocks, key=_block_sort_key)

    for block_idx, cb in enumerate(sorted_blocks):
        role = LABEL_TO_ROLE.get(cb.label, TextRole.BODY)

        # Apply optional skip overrides
        if role == TextRole.FOOTNOTE and skip_footnotes:
            role = TextRole.SKIP
        if role == TextRole.CAPTION and skip_captions:
            role = TextRole.SKIP

        prosody = get_prosody(role, speed_multiplier, pause_multiplier)

        # Skip entirely
        if prosody.skip:
            continue

        # Decide whether to split into sentences
        split = role == TextRole.BODY

        segments = preprocess_block(
            cb.block.text,
            split=split,
            strip_references=strip_references,
        )

        if not segments:
            continue

        for i, segment_text in enumerate(segments):
            if not segment_text.strip():
                continue

            # For multi-sentence body blocks: first sentence gets the
            # block's pause_before, last gets pause_after, middle
            # sentences get a small inter-sentence pause.
            if split and len(segments) > 1:
                seg_prosody = ProsodyRule(
                    pause_before=(
                        prosody.pause_before
                        if i == 0
                        else SENTENCE_PAUSE * pause_multiplier
                    ),
                    pause_after=(
                        prosody.pause_after
                        if i == len(segments) - 1
                        else SENTENCE_PAUSE * pause_multiplier
                    ),
                    speed_factor=prosody.speed_factor,
                    skip=False,
                )
            else:
                seg_prosody = prosody

            instructions.append(
                ReadingInstruction(
                    text=segment_text,
                    role=role,
                    prosody=seg_prosody,
                    page_index=page_index,
                    block_index=block_idx,
                    characters=cb.block.all_characters,
                )
            )

    return instructions


def build_document_script(
    all_classified: Dict[int, List[ClassifiedBlock]],
    speed_multiplier: float = 1.0,
    pause_multiplier: float = 1.0,
    skip_footnotes: bool = True,
    skip_captions: bool = False,
    strip_references: bool = True,
    announce_pages: bool = False,
    page_transition_pause: float = 1.0,
) -> List[ReadingInstruction]:
    """
    Build a complete document reading script from all pages.

    Args:
        all_classified:       Dict[page_index → ClassifiedBlock list].
        speed_multiplier:     Global speed scaling.
        pause_multiplier:     Global pause scaling.
        skip_footnotes:       Skip footnote blocks.
        skip_captions:        Skip caption blocks.
        strip_references:     Remove [N] markers.
        announce_pages:       Insert "Page N" announcements.
        page_transition_pause: Silence between pages (seconds).

    Returns:
        Flat list of ReadingInstruction for the whole document.
    """
    script: List[ReadingInstruction] = []

    sorted_pages = sorted(all_classified.keys())

    for i, page_idx in enumerate(sorted_pages):
        blocks = all_classified[page_idx]

        # Page announcement
        if announce_pages:
            prosody = get_prosody(
                TextRole.SECTION_HEADER, speed_multiplier, pause_multiplier
            )
            script.append(
                ReadingInstruction(
                    text=f"Page {page_idx + 1}.",
                    role=TextRole.SECTION_HEADER,
                    prosody=prosody,
                    page_index=page_idx,
                    block_index=-1,
                )
            )

        # Page content
        page_script = build_page_script(
            blocks,
            page_idx,
            speed_multiplier=speed_multiplier,
            pause_multiplier=pause_multiplier,
            skip_footnotes=skip_footnotes,
            skip_captions=skip_captions,
            strip_references=strip_references,
        )
        script.extend(page_script)

        # Page transition pause (except after the last page)
        if i < len(sorted_pages) - 1:
            transition = ProsodyRule(
                pause_before=0.0,
                pause_after=page_transition_pause * pause_multiplier,
                speed_factor=1.0,
                skip=False,
            )
            script.append(
                ReadingInstruction(
                    text="",
                    role=TextRole.PAGE_TRANSITION,
                    prosody=transition,
                    page_index=page_idx,
                    block_index=-1,
                )
            )

    return script


# -----------------------------------------------------------------
# Debug preview
# -----------------------------------------------------------------


def preview_script(script: List[ReadingInstruction]) -> str:
    """
    Format the reading script as a human-readable string for review.

    Example output::

        [PAGE 1]
        [TITLE, pause=1.5s|1.2s, speed=0.85x] "Introduction to ML"
        [BODY, speed=1.0x] "Machine learning is a subfield..."
        [PAUSE 0.3s]
        [PAGE_TRANSITION 1.0s]
        [PAGE 2]
        ...
    """
    lines: List[str] = []
    current_page = -1

    for inst in script:
        # Page header
        if inst.page_index != current_page:
            current_page = inst.page_index
            lines.append(f"\n[PAGE {current_page + 1}]")

        p = inst.prosody

        # Page transition (silence only)
        if inst.role == TextRole.PAGE_TRANSITION:
            lines.append(f"[PAGE_TRANSITION {p.pause_after:.1f}s]")
            continue

        # Build tag
        pauses = ""
        if p.pause_before > 0 or p.pause_after > 0:
            pauses = f", pause={p.pause_before:.1f}s|{p.pause_after:.1f}s"

        speed = f", speed={p.speed_factor:.2f}x" if p.speed_factor != 1.0 else ""

        preview = inst.text[:80]
        lines.append(f'[{inst.role.name}{pauses}{speed}] "{preview}"')

    return "\n".join(lines)
