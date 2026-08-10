"""Deterministic JSON encoding.

Signatures are computed over bytes, so the mapping from a document to
those bytes must be stable across platforms, Python versions and
round-trips through disk. This module defines that mapping and is
deliberately tiny: any change to it invalidates every signature ever
produced, so it is versioned via ``CANONICAL_FORM`` in the envelope.
"""

from __future__ import annotations

import json
from typing import Any

#: Identifier recorded in signed envelopes. Bump only on a breaking change
#: to the encoding, and then only with a migration path.
CANONICAL_FORM = "edsg-canonical-json-1"


def canonical_bytes(payload: Any) -> bytes:
    """Serialise ``payload`` to canonical UTF-8 bytes.

    Keys are sorted, separators are minimal, non-ASCII characters are
    preserved rather than escaped, and NaN/Infinity are rejected because
    they are not valid JSON and do not survive interchange.
    """
    text = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return text.encode("utf-8")


def canonical_text(payload: Any) -> str:
    """Return the canonical encoding of ``payload`` as ``str``."""
    return canonical_bytes(payload).decode("utf-8")


def pretty_text(payload: Any) -> str:
    """Return a human-readable encoding, for display and file output.

    Only the canonical form is ever signed or verified; this exists so
    that files written to disk remain diff-friendly and inspectable.
    """
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


__all__ = ["CANONICAL_FORM", "canonical_bytes", "canonical_text", "pretty_text"]
