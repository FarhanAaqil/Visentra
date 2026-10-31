"""Ed25519 signing for inference evidence and assurance certificates (Pillar IV).

The private key comes from SIGNING_KEY (hex encoded 32 byte seed) or is
generated once and stored under storage/keys with owner-only permissions.
Signatures cover the SHA-256 of a canonical JSON encoding, so key order and
whitespace never change what was signed.
"""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from backend import storage
from backend.config import settings

ALGORITHM = "Ed25519"

# Fields bound into every inference signature.
BINDING_FIELDS = (
    "inference_id",
    "dataset_merkle_root",
    "model_id",
    "model_sha256",
    "arch_fingerprint",
    "input_sha256",
    "config_sha256",
    "output",
    "timestamp",
)


def _load_or_create() -> Ed25519PrivateKey:
    if settings.signing_key:
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(settings.signing_key))
    path = storage.area("keys") / "ed25519_private.pem"
    if path.exists():
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        assert isinstance(key, Ed25519PrivateKey)
        return key
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    return key


@lru_cache(maxsize=1)
def _keypair(root: str, seed_hint: str) -> tuple[Ed25519PrivateKey, str]:  # noqa: ARG001 (cache keys)
    key = _load_or_create()
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    return key, pub


def keypair() -> tuple[Ed25519PrivateKey, str]:
    return _keypair(settings.storage_root, settings.signing_key[:8])


def public_key_hex() -> str:
    return keypair()[1]


def key_id(pub_hex: str | None = None) -> str:
    return hashlib.sha256(bytes.fromhex(pub_hex or public_key_hex())).hexdigest()[:16]


def _normalise(value: Any) -> Any:
    """Make numbers language-neutral: JavaScript has no int/float split, so 75.0 comes back as 75."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_normalise(v) for v in value]
    return value


def canonical_bytes(payload: Any) -> bytes:
    """Sorted, compact JSON with integral floats as integers, so every JSON stack agrees on the bytes."""
    text = json.dumps(_normalise(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


def binding_tuple(evidence: dict[str, Any]) -> dict[str, Any]:
    return {k: evidence.get(k) for k in BINDING_FIELDS}


def binding_digest(evidence: dict[str, Any]) -> bytes:
    return hashlib.sha256(canonical_bytes(binding_tuple(evidence))).digest()


def sign_digest(digest: bytes) -> tuple[str, str]:
    key, pub = keypair()
    return key.sign(digest).hex(), pub


def verify_digest(digest: bytes, signature_hex: str | None, public_key: str | None = None) -> bool:
    if not signature_hex:
        return False
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key or public_key_hex()))
        pub.verify(bytes.fromhex(signature_hex), digest)
        return True
    except (ValueError, InvalidSignature):
        return False


def sign_evidence_tuple(evidence: dict[str, Any]) -> tuple[str, str]:
    return sign_digest(binding_digest(evidence))


def verify_evidence_signature(
    evidence: dict[str, Any], signature_hex: str | None, public_key: str | None = None
) -> bool:
    return verify_digest(binding_digest(evidence), signature_hex, public_key)


def sign_document(document: dict[str, Any]) -> dict[str, Any]:
    """Wrap ``document`` with a detached signature over its canonical JSON."""
    signature, pub = sign_digest(hashlib.sha256(canonical_bytes(document)).digest())
    return {
        "document": document,
        "signature": {"algorithm": ALGORITHM, "public_key": pub, "key_id": key_id(pub), "value": signature},
    }


def verify_document(envelope: dict[str, Any]) -> bool:
    sig = envelope.get("signature") or {}
    digest = hashlib.sha256(canonical_bytes(envelope.get("document"))).digest()
    return verify_digest(digest, sig.get("value"), sig.get("public_key"))
