"""Sealed boxes between the web and the sync container.

The web container has only ``PLANNER_PUBLIC_KEY``: it can seal (encrypt
for the sync container) but not open. The sync container also has
``PLANNER_PRIVATE_KEY``. Used for Microsoft's one-time sign-in code on its
way to the sync container, and for the token cache at rest in the shared
database, so neither can be read from the web container or a copy of the
database.

Keys are X25519 (libsodium sealed boxes, via PyNaCl), base64-encoded.
Generate a pair with ``manage.py planner_keygen``.
"""

from __future__ import annotations

import base64
import json

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from nacl.public import PrivateKey, PublicKey, SealedBox


def generate_keypair() -> tuple[str, str]:
    """Return (public, private) as base64 strings."""
    private = PrivateKey.generate()
    return (base64.b64encode(bytes(private.public_key)).decode(),
            base64.b64encode(bytes(private)).decode())


def _key(name: str) -> bytes:
    value = getattr(settings, name, "")
    if not value:
        raise ImproperlyConfigured(f"{name} is not set (see docs/PLANNER.md).")
    return base64.b64decode(value)


def can_seal() -> bool:
    return bool(settings.PLANNER_PUBLIC_KEY)


def can_open() -> bool:
    return bool(settings.PLANNER_PRIVATE_KEY)


def seal(data: dict | str) -> str:
    """Encrypt for the sync container; returns base64 text."""
    raw = data if isinstance(data, str) else json.dumps(data)
    box = SealedBox(PublicKey(_key("PLANNER_PUBLIC_KEY")))
    return base64.b64encode(box.encrypt(raw.encode())).decode()


def open_sealed(blob: str, *, as_json: bool = True) -> dict | str:
    """Decrypt in the sync container (needs the private key)."""
    box = SealedBox(PrivateKey(_key("PLANNER_PRIVATE_KEY")))
    raw = box.decrypt(base64.b64decode(blob)).decode()
    return json.loads(raw) if as_json else raw
