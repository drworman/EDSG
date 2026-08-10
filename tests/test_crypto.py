"""Signing, verification and tamper detection."""

from __future__ import annotations

import copy

import pytest

from edsg.core.canonical import canonical_bytes, canonical_text
from edsg.core.crypto import (
    fingerprint,
    generate_identity,
    load_identity,
    load_or_create_identity,
    save_identity,
    sign_document,
    verify_document,
)
from edsg.core.errors import DocumentError, SignatureError


def test_canonical_encoding_is_order_independent():
    assert canonical_text({"b": 1, "a": 2}) == canonical_text({"a": 2, "b": 1})


def test_canonical_encoding_rejects_nan():
    with pytest.raises(ValueError):
        canonical_bytes({"value": float("nan")})


def test_canonical_encoding_preserves_non_ascii():
    assert "Ā" in canonical_text({"system": "Ā"})


def test_round_trip_verifies(identity):
    envelope = sign_document(identity, "edsg.test", {"value": 42})
    assert verify_document(envelope, "edsg.test") == {"value": 42}


def test_tampered_payload_fails(identity):
    envelope = sign_document(identity, "edsg.test", {"score": 1})
    envelope["payload"]["score"] = 9999
    with pytest.raises(SignatureError):
        verify_document(envelope)


def test_tampered_signature_fails(identity):
    envelope = sign_document(identity, "edsg.test", {"score": 1})
    signature = envelope["edsg"]["signature"]
    envelope["edsg"]["signature"] = ("A" if signature[0] != "A" else "B") + signature[
        1:
    ]
    with pytest.raises(SignatureError):
        verify_document(envelope)


def test_substituted_key_fails(identity):
    """A forger cannot swap in their own key and re-sign the same payload."""
    envelope = sign_document(identity, "edsg.test", {"score": 1})
    attacker = generate_identity("attacker")
    envelope["public_key"] = attacker.public_key_b64
    with pytest.raises(SignatureError):
        verify_document(envelope)


def test_document_type_is_bound_into_the_signature(identity):
    """A signature must not transplant from one document type to another."""
    envelope = sign_document(identity, "edsg.invitation", {"a": 1})
    forged = copy.deepcopy(envelope)
    forged["doc_type"] = "edsg.submission"
    with pytest.raises(SignatureError):
        verify_document(forged)


def test_wrong_expected_type_is_reported_clearly(identity):
    envelope = sign_document(identity, "edsg.submission", {"a": 1})
    with pytest.raises(DocumentError, match=r"Expected edsg\.invitation"):
        verify_document(envelope, "edsg.invitation")


def test_missing_header_is_rejected():
    with pytest.raises(DocumentError):
        verify_document({"payload": {}})


def test_unknown_canonical_form_is_rejected(identity):
    envelope = sign_document(identity, "edsg.test", {})
    envelope["canonical_form"] = "something-from-the-future"
    with pytest.raises(DocumentError, match="cannot verify"):
        verify_document(envelope)


def test_fingerprint_is_stable_and_grouped(identity):
    value = fingerprint(identity.public_key_b64)
    assert value == identity.fingerprint
    assert all(len(part) == 4 for part in value.split(" "))


def test_distinct_keys_have_distinct_fingerprints():
    assert generate_identity("a").fingerprint != generate_identity("b").fingerprint


def test_identity_persists_across_loads():
    original = load_or_create_identity("organizer", "Test Organizer")
    again = load_or_create_identity("organizer", "ignored")
    assert original.fingerprint == again.fingerprint


def test_saved_key_is_owner_readable_only(identity):
    import sys

    path = save_identity(identity, "perm-check")
    if sys.platform != "win32":
        assert oct(path.stat().st_mode)[-3:] == "600"
    assert load_identity("perm-check").fingerprint == identity.fingerprint


def test_missing_identity_returns_none():
    assert load_identity("never-created") is None
