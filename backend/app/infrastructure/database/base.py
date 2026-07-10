"""SQLAlchemy declarative base (no business models in Module 1)."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for future ORM models (Module 2+)."""
