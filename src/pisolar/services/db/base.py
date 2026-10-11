"""SQLAlchemy declarative base and engine factory."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase

from pisolar.services.db.connection import mysql_connect_args


class Base(DeclarativeBase):
    """Declarative base for all piSolar ORM models."""


def create_db_engine(
    url: str,
    pool_size: int = 5,
    pool_recycle: int = 3600,
    connect_timeout: int = 5,
    read_timeout: int = 10,
    write_timeout: int = 10,
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
    connect_args = mysql_connect_args(url, connect_timeout, read_timeout, write_timeout)
    engine_kwargs: dict = {
        "pool_size": pool_size,
        "pool_recycle": pool_recycle,
        "pool_pre_ping": True,
    }
    if connect_args:
        engine_kwargs["connect_args"] = connect_args
    return create_engine(url, **engine_kwargs)
