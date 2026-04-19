"""SQLAlchemy declarative base and engine factory."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all piSolar ORM models."""


def create_db_engine(
    url: str,
    pool_size: int = 5,
    pool_recycle: int = 3600,
) -> Engine:
    """Create and return a SQLAlchemy engine.

    Args:
        url: SQLAlchemy database URL (e.g. mysql+pymysql://user:pass@host/db)
        pool_size: Number of persistent connections in the pool.
        pool_recycle: Seconds before recycling idle connections (prevents
            MySQL ``wait_timeout`` disconnects).

    Returns:
        Configured :class:`~sqlalchemy.engine.Engine` instance.
    """
    return create_engine(
        url,
        pool_size=pool_size,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,
    )
