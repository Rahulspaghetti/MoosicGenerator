"""Tokens are encrypted at rest and decrypt transparently on read."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.models import UserSession

PLAINTEXT_ACCESS = "access-token-plaintext-secret"
PLAINTEXT_REFRESH = "refresh-token-plaintext-secret"


def test_tokens_stored_as_ciphertext_but_read_back_as_plaintext(db_session) -> None:
    db_session.add(
        UserSession(
            session_id="sess_crypto_1",
            spotify_user_id="user-crypto",
            display_name="Grace Hopper",
            access_token=PLAINTEXT_ACCESS,
            refresh_token=PLAINTEXT_REFRESH,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db_session.commit()
    db_session.expire_all()

    # Raw column bytes must NOT contain the plaintext.
    raw = db_session.execute(
        text("SELECT access_token, refresh_token FROM user_sessions WHERE session_id='sess_crypto_1'")
    ).one()
    assert raw.access_token != PLAINTEXT_ACCESS
    assert PLAINTEXT_ACCESS not in raw.access_token
    assert PLAINTEXT_REFRESH not in raw.refresh_token
    # Fernet tokens start with the version byte 0x80 -> base64 "gAAAAA".
    assert raw.access_token.startswith("gAAAAA")

    # ORM read decrypts transparently.
    session = db_session.get(UserSession, "sess_crypto_1")
    assert session.access_token == PLAINTEXT_ACCESS
    assert session.refresh_token == PLAINTEXT_REFRESH


def test_null_refresh_token_stays_null(db_session) -> None:
    db_session.add(
        UserSession(
            session_id="sess_crypto_2",
            spotify_user_id="user-crypto-2",
            display_name="Ada",
            access_token=PLAINTEXT_ACCESS,
            refresh_token=None,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db_session.commit()
    assert db_session.get(UserSession, "sess_crypto_2").refresh_token is None
