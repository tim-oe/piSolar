"""Shared pytest fixtures for services/db tests.

A single MySQL container is started once for the entire test session.
Each test function gets a fresh set of tables (created on setup, dropped
on teardown) so tests are fully isolated without needing transaction
rollback gymnastics.
"""

import re

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from testcontainers.mysql import MySqlContainer

from pisolar.services.db.base import Base

_MYSQL_IMAGE = "mysql:8.0"


def _pymysql_url(raw: str) -> str:
    """Normalise any mysql:// variant to mysql+pymysql:// (our installed driver)."""
    return re.sub(r"^mysql(\+\w+)?://", "mysql+pymysql://", raw)


@pytest.fixture(scope="session")
def mysql_url(request):
    """Start a MySQL 8 container once for the whole pytest session."""
    container = MySqlContainer(_MYSQL_IMAGE)
    container.start()
    request.addfinalizer(container.stop)
    yield _pymysql_url(container.get_connection_url())


@pytest.fixture
def engine(mysql_url):
    """Return an engine with all tables freshly created; drop them after the test."""
    eng = create_engine(mysql_url)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def session(engine):
    """Provide a plain SQLAlchemy session for ORM-level assertions."""
    with Session(engine) as sess:
        yield sess
