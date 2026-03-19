"""
Ironpass — SQLAlchemy declarative base.

All models inherit from this base.
Separate schemas for vault and audit as per architecture.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all Ironpass models."""
    pass
