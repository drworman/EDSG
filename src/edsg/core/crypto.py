"""Signing identities and signed document envelopes.

EDSG uses Ed25519 for all document signing. Keys are small, verification
is fast, and the primitive has no parameter choices to get wrong.

Threat model
------------
Signing protects documents *in transit*. It guarantees that an invitation
presented to a participant is the one the organizer produced, and that a
submission opened by an organizer is byte-for-byte what the participant
generated. It does **not** and cannot prove that a participant's journal
files were themselves unmodified: journals are plain text on the
participant's own machine. EDSG is a tool for running friendly
competitions among commanders who broadly trust each other, and the
standings report surfaces the evidence an organizer needs to spot
implausible results. See ``docs/SECURITY.md``.
"""

from __future__ import annotations

import base64
import contextlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from edsg.core.canonical import CANONICAL_FORM, canonical_bytes
from edsg.core.errors import DocumentError, KeyStoreError, SignatureError
from edsg.core.paths import ensure_config_dir, keys_dir

SIGNATURE_ALGORITHM = "ed25519"

#: Number of hex characters shown in a human-comparable fingerprint.
FINGERPRINT_LENGTH = 32


def _b64encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64decode(text: str) -> bytes:
    try:
        return base64.b64decode(text.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise DocumentError("Malformed base64 data in document.") from exc


def fingerprint(public_key_b64: str) -> str:
    """Return a short, human-comparable fingerprint of a public key.

    Rendered in groups of four characters so two people can read it to
    each other over voice comms without losing their place.
    """
    digest = hashes.Hash(hashes.SHA256())
    digest.update(_b64decode(public_key_b64))
    hexed = digest.finalize().hex()[:FINGERPRINT_LENGTH].upper()
    return " ".join(hexed[i : i + 4] for i in range(0, len(hexed), 4))


@dataclass(frozen=True)
class Identity:
    """A signing identity: an Ed25519 key pair plus a display label."""

    label: str
    private_key: Ed25519PrivateKey
    created: str

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self.private_key.public_key()

    @property
    def public_key_b64(self) -> str:
        raw = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return _b64encode(raw)

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.public_key_b64)

    def sign(self, message: bytes) -> str:
        """Sign ``message`` and return a base64 signature."""
        return _b64encode(self.private_key.sign(message))


def generate_identity(label: str) -> Identity:
    """Create a brand new identity in memory."""
    return Identity(
        label=label,
        private_key=Ed25519PrivateKey.generate(),
        created=datetime.now(UTC).isoformat(timespec="seconds"),
    )


def _key_path(name: str) -> Path:
    safe = "".join(ch for ch in name if ch.isalnum() or ch in "-_") or "default"
    return keys_dir() / f"{safe}.key"


def save_identity(identity: Identity, name: str) -> Path:
    """Persist ``identity`` to the key store, owner-readable only.

    The private key is written unencrypted, which matches the value at
    stake: compromise lets an attacker impersonate an event organizer,
    not access a Frontier account. ``docs/SECURITY.md`` says so plainly
    rather than implying protection that is not there.
    """
    ensure_config_dir()
    directory = keys_dir()
    directory.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        with contextlib.suppress(OSError):
            directory.chmod(0o700)

    path = _key_path(name)
    blob = identity.private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    header = (
        f"# EDSG signing identity\n"
        f"# label: {identity.label}\n"
        f"# created: {identity.created}\n"
        f"# fingerprint: {identity.fingerprint}\n"
    ).encode()

    try:
        # Create with a restrictive mode from the outset rather than
        # widening then narrowing, which would leave a race window.
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(header + blob)
    except OSError as exc:
        raise KeyStoreError(f"Could not write signing key to {path}: {exc}") from exc
    return path


def load_identity(name: str) -> Identity | None:
    """Load an identity by name, or return ``None`` if absent."""
    path = _key_path(name)
    if not path.is_file():
        return None
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise KeyStoreError(f"Could not read signing key {path}: {exc}") from exc

    label = name
    created = ""
    for line in data.split(b"\n"):
        if not line.startswith(b"#"):
            break
        text = line.decode("utf-8", errors="replace")
        if "label:" in text:
            label = text.split("label:", 1)[1].strip()
        elif "created:" in text:
            created = text.split("created:", 1)[1].strip()

    try:
        key = serialization.load_pem_private_key(data, password=None)
    except (ValueError, TypeError) as exc:
        raise KeyStoreError(f"Signing key {path} is corrupt or unreadable.") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise KeyStoreError(f"Signing key {path} is not an Ed25519 key.")

    return Identity(label=label, private_key=key, created=created)


def load_or_create_identity(name: str, label: str) -> Identity:
    """Return the named identity, creating and persisting it if absent."""
    existing = load_identity(name)
    if existing is not None:
        return existing
    identity = generate_identity(label)
    save_identity(identity, name)
    return identity


def sign_document(
    identity: Identity,
    doc_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Wrap ``payload`` in a signed envelope.

    The envelope's ``signature`` covers the canonical encoding of an inner
    structure that includes the document type and the signer's public key.
    Binding those in prevents a signature being lifted from one document
    type and replayed on another.
    """
    signed_core = {
        "canonical_form": CANONICAL_FORM,
        "doc_type": doc_type,
        "payload": payload,
        "public_key": identity.public_key_b64,
        "signed_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    signature = identity.sign(canonical_bytes(signed_core))
    return {
        "edsg": {
            "algorithm": SIGNATURE_ALGORITHM,
            "signature": signature,
            "signer_label": identity.label,
        },
        **signed_core,
    }


def verify_document(
    envelope: dict[str, Any],
    expected_type: str | None = None,
) -> dict[str, Any]:
    """Verify a signed envelope and return its payload.

    Raises :class:`SignatureError` if verification fails and
    :class:`DocumentError` if the envelope is structurally wrong. The two
    are distinct because they mean very different things to a user: one
    is a tampered or mismatched file, the other is the wrong file.
    """
    if not isinstance(envelope, dict):
        raise DocumentError("Document is not a JSON object.")

    meta = envelope.get("edsg")
    if not isinstance(meta, dict):
        raise DocumentError("Document is not an EDSG file (missing header).")

    algorithm = meta.get("algorithm")
    if algorithm != SIGNATURE_ALGORITHM:
        raise DocumentError(f"Unsupported signature algorithm: {algorithm!r}.")

    canonical_form = envelope.get("canonical_form")
    if canonical_form != CANONICAL_FORM:
        raise DocumentError(
            f"Document uses encoding {canonical_form!r}, which this version "
            f"of EDSG cannot verify. Expected {CANONICAL_FORM!r}."
        )

    doc_type = envelope.get("doc_type")
    if expected_type is not None and doc_type != expected_type:
        raise DocumentError(
            f"Expected {expected_type} file but this is a {doc_type} file."
        )

    public_key_b64 = envelope.get("public_key")
    signature_b64 = meta.get("signature")
    if not isinstance(public_key_b64, str) or not isinstance(signature_b64, str):
        raise DocumentError("Document is missing its key or signature.")

    signed_core = {
        "canonical_form": canonical_form,
        "doc_type": doc_type,
        "payload": envelope.get("payload"),
        "public_key": public_key_b64,
        "signed_at": envelope.get("signed_at"),
    }

    try:
        public_key = Ed25519PublicKey.from_public_bytes(_b64decode(public_key_b64))
    except ValueError as exc:
        raise DocumentError("Document contains an invalid public key.") from exc

    try:
        public_key.verify(_b64decode(signature_b64), canonical_bytes(signed_core))
    except InvalidSignature as exc:
        raise SignatureError(
            "Signature check FAILED. This file has been modified since it "
            "was signed, or it was not produced by the key it claims."
        ) from exc

    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise DocumentError("Document payload is not a JSON object.")
    return payload


def envelope_public_key(envelope: dict[str, Any]) -> str:
    """Return the base64 public key recorded in an envelope."""
    key = envelope.get("public_key")
    if not isinstance(key, str):
        raise DocumentError("Document does not carry a public key.")
    return key


__all__ = [
    "FINGERPRINT_LENGTH",
    "SIGNATURE_ALGORITHM",
    "Identity",
    "envelope_public_key",
    "fingerprint",
    "generate_identity",
    "load_identity",
    "load_or_create_identity",
    "save_identity",
    "sign_document",
    "verify_document",
]
