"""Reading script generation with prosody annotations."""

from .models import LABEL_TO_ROLE, ProsodyRule, ReadingInstruction, TextRole
from .prosody_rules import DEFAULT_PROSODY, get_prosody
from .reading_script import (
    build_document_script,
    build_page_script,
    preview_script,
)
from .text_preprocessor import clean_text, preprocess_block, split_sentences

__all__ = [
    "TextRole",
    "ProsodyRule",
    "ReadingInstruction",
    "LABEL_TO_ROLE",
    "DEFAULT_PROSODY",
    "get_prosody",
    "build_page_script",
    "build_document_script",
    "preview_script",
    "clean_text",
    "split_sentences",
    "preprocess_block",
]
