"""Application-level encryption for secrets at rest.

Spotify OAuth tokens are stored in the database, so they are encrypted with
Fernet (AES-128-CBC + HMAC-SHA256 authenticated encryption) before they ever
touch a column, and decrypted transparently on read. The key comes from the
``TOKEN_ENCRYPTION_KEY`` setting and is never persisted alongside the data.

Usage: declare a column as ``mapped_column(EncryptedString(...))`` and read/write
it with plaintext ``str`` as normal — encryption is invisible to callers.
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet
from sqlalchemy import String, TypeDecorator

from app.core.config import get_settings


@lru_cache
def _get_fernet() -> Fernet:
    """Return a process-wide :class:`Fernet` built from ``TOKEN_ENCRYPTION_KEY``.

    Raises:
        RuntimeError: If the key is unset. Failing loud here (rather than
            silently storing plaintext) prevents accidentally running with an
            insecure configuration.
    """
    key = get_settings().TOKEN_ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"` and put it in your .env."
        )
    return Fernet(key.encode())


class EncryptedString(TypeDecorator):
    """A SQLAlchemy string column whose value is Fernet-encrypted at rest.

    Plaintext in the application, ciphertext (URL-safe base64) in the database.
    ``None`` passes through unchanged so nullable columns stay nullable.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: object) -> str | None:
        """Encrypt on the way into the database."""
        if value is None:
            return None
        return _get_fernet().encrypt(value.encode()).decode()

    def process_result_value(self, value: str | None, dialect: object) -> str | None:
        """Decrypt on the way out of the database."""
        if value is None:
            return None
        return _get_fernet().decrypt(value.encode()).decode()
