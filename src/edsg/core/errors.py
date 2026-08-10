"""Exception hierarchy for EDSG.

Every error raised deliberately by the core layer derives from
:class:`EDSGError`, so user interfaces can catch a single base class and
present ``str(exc)`` directly to the user. Messages are therefore written
to be read by commanders, not developers.
"""

from __future__ import annotations


class EDSGError(Exception):
    """Base class for all errors raised by EDSG."""


class ConfigError(EDSGError):
    """Raised when on-disk configuration cannot be read or written."""


class KeyStoreError(EDSGError):
    """Raised when a signing identity cannot be loaded or created."""


class SignatureError(EDSGError):
    """Raised when a document fails cryptographic verification."""


class DocumentError(EDSGError):
    """Raised when a document is structurally invalid or unsupported."""


class JournalError(EDSGError):
    """Raised when a journal directory is missing or unreadable."""


class CriteriaError(EDSGError):
    """Raised when event criteria are invalid or contradictory."""


class EventStateError(EDSGError):
    """Raised on an illegal event lifecycle transition."""


__all__ = [
    "ConfigError",
    "CriteriaError",
    "DocumentError",
    "EDSGError",
    "EventStateError",
    "JournalError",
    "KeyStoreError",
    "SignatureError",
]
