"""Tests for MySQL connection helpers."""

from sqlalchemy.exc import DBAPIError, OperationalError

from pisolar.services.db.connection import is_connection_error, mysql_connect_args


class TestIsConnectionError:
    def test_operational_error(self):
        assert is_connection_error(OperationalError("", "", ""))

    def test_dbapi_invalidated(self):
        exc = DBAPIError("", "", "", connection_invalidated=True)
        assert is_connection_error(exc)

    def test_other_error(self):
        assert not is_connection_error(RuntimeError("nope"))


class TestMysqlConnectArgs:
    def test_mysqlconnector_keys(self):
        args = mysql_connect_args(
            "mariadb+mysqlconnector://localhost/pisolar", 5, 10, 10
        )
        assert args == {
            "connection_timeout": 5,
            "read_timeout": 10,
            "write_timeout": 10,
        }

    def test_pymysql_keys(self):
        args = mysql_connect_args("mysql+pymysql://localhost/pisolar", 5, 10, 10)
        assert args == {
            "connect_timeout": 5,
            "read_timeout": 10,
            "write_timeout": 10,
        }
