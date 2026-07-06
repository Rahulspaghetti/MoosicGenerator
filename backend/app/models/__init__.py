"""SQLAlchemy ORM models.

Phase 1: real persistence backing ``/auth/*`` and ``/library/sync``.
Importing this package registers every model on ``Base.metadata`` so that
``Base.metadata.create_all(engine)`` creates all tables for any caller
that imports :mod:`app.models` (rather than each model module directly).
"""

from app.models.artist_genre_cache import ArtistGenreCache
from app.models.generation_job import GenerationJob
from app.models.library_sync_job import LibrarySyncJob
from app.models.oauth_state import OAuthState
from app.models.taste_profile import TasteProfile
from app.models.user_session import UserSession

__all__ = [
    "ArtistGenreCache",
    "GenerationJob",
    "LibrarySyncJob",
    "OAuthState",
    "TasteProfile",
    "UserSession",
]
