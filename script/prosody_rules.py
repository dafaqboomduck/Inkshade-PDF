"""
Prosody rule definitions: TextRole → ProsodyRule mappings.

All values are tuneable defaults.  The pipeline accepts global
multipliers (speed_multiplier, pause_multiplier) that scale on top
of these per-role values.
"""

from .models import ProsodyRule, TextRole

# -----------------------------------------------------------------
# Default prosody table
# -----------------------------------------------------------------

DEFAULT_PROSODY: dict[TextRole, ProsodyRule] = {
    TextRole.TITLE: ProsodyRule(
        pause_before=1.5,
        pause_after=1.2,
        speed_factor=0.85,
    ),
    TextRole.SECTION_HEADER: ProsodyRule(
        pause_before=1.2,
        pause_after=0.8,
        speed_factor=0.88,
    ),
    TextRole.BODY: ProsodyRule(
        pause_before=0.0,  # sentence-level pauses handled inline
        pause_after=0.3,  # paragraph gap
        speed_factor=1.0,
    ),
    TextRole.LIST_ITEM: ProsodyRule(
        pause_before=0.2,
        pause_after=0.25,
        speed_factor=0.97,
    ),
    TextRole.CAPTION: ProsodyRule(
        pause_before=0.6,
        pause_after=0.6,
        speed_factor=0.95,
    ),
    TextRole.FOOTNOTE: ProsodyRule(
        pause_before=0.8,
        pause_after=0.5,
        speed_factor=1.05,
    ),
    TextRole.FORMULA: ProsodyRule(
        skip=True,
    ),
    TextRole.PAGE_TRANSITION: ProsodyRule(
        pause_before=0.0,
        pause_after=1.0,
        skip=False,  # silence-only, no speech
        speed_factor=1.0,
    ),
    TextRole.SKIP: ProsodyRule(
        skip=True,
    ),
}

# Pause inserted between sentences within a body paragraph
SENTENCE_PAUSE: float = 0.15

# Extra pauses after specific punctuation (added to sentence pause)
COLON_PAUSE: float = 0.10
SEMICOLON_PAUSE: float = 0.08


def get_prosody(
    role: TextRole,
    speed_multiplier: float = 1.0,
    pause_multiplier: float = 1.0,
) -> ProsodyRule:
    """
    Look up the prosody rule for *role* and apply global multipliers.

    Returns a new ProsodyRule instance (does not mutate the defaults).
    """
    base = DEFAULT_PROSODY.get(role, DEFAULT_PROSODY[TextRole.BODY])
    return ProsodyRule(
        pause_before=base.pause_before * pause_multiplier,
        pause_after=base.pause_after * pause_multiplier,
        speed_factor=base.speed_factor * speed_multiplier,
        skip=base.skip,
    )
