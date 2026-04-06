"""Generierung menschenlesbarer Dokumentnamen für MongoDB."""

import random
import re
from typing import Optional

_SUBJECTS = [
    "astronaut",
    "elephant",
    "falcon",
    "lion",
    "otter",
    "robot",
    "tiger",
    "whale",
    "wizard",
    "yeti",
]
_ADJECTIVES = [
    "amber",
    "brisk",
    "curious",
    "gentle",
    "glowing",
    "grand",
    "silent",
    "sunny",
    "swift",
    "vivid",
]
_OBJECTS = [
    "bridge",
    "comet",
    "forest",
    "harbor",
    "lantern",
    "meadow",
    "mountain",
    "pipeline",
    "rocket",
    "valley",
]


def _normalize_part(value: Optional[str], *, fallback: str) -> str:
    if not value:
        return fallback
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or fallback


def build_human_readable_document_id(*, domain: str, document_type: str) -> str:
    """
    Erzeugt IDs im Format:
    subject_adjective_object_domain_documenttype
    """
    subject = random.choice(_SUBJECTS)
    adjective = random.choice(_ADJECTIVES)
    obj = random.choice(_OBJECTS)
    domain_part = _normalize_part(domain, fallback="general")
    document_type_part = _normalize_part(document_type, fallback="doc")
    return f"{subject}_{adjective}_{obj}_{domain_part}_{document_type_part}"
