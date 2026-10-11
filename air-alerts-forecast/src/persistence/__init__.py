"""Optional PostgreSQL persistence for compact provenance and source records."""

from .repository import PersistenceRepository, get_repository

__all__ = ["PersistenceRepository", "get_repository"]
