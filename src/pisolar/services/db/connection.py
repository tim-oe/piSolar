"""MySQL driver helpers for connection errors and connect timeouts."""

from __future__ import annotations

from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError


def is_connection_error(exc: BaseException) -> bool:
    """True for errors that indicate the database is unreachable."""
    if isinstance(exc, (OperationalError, InterfaceError)):
        return True
    if isinstance(exc, DBAPIError) and bool(
        getattr(exc, "connection_invalidated", False)
    ):
        return True
    return False


def mysql_connect_args(
    url: str,
    connect_timeout: int,
    read_timeout: int,
    write_timeout: int,
) -> dict[str, int]:
    """Return driver-specific timeout keyword arguments for create_engine."""
    driver = make_url(url).drivername
    if "mysqlconnector" in driver:
        return {
            "connection_timeout": connect_timeout,
            "read_timeout": read_timeout,
            "write_timeout": write_timeout,
        }
    if "pymysql" in driver or driver in ("mysql", "mariadb"):
        return {
            "connect_timeout": connect_timeout,
            "read_timeout": read_timeout,
            "write_timeout": write_timeout,
        }
    return {}
