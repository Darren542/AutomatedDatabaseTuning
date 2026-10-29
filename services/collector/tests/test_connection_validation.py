from unittest.mock import Mock

import pyodbc
import pytest

from collector.connection_validation import ConnectionValidationService, ValidationCode
from collector.targets import SqlCredentials, TargetConfiguration


def target(**overrides):
    return TargetConfiguration(**dict(dict(name="Demo", server="localhost", database="Demo"), **overrides))


def driver():
    cursor = Mock()
    cursor.fetchone.side_effect = [(1,), (0,)]
    connection = Mock()
    connection.cursor.return_value = cursor
    connect = Mock(return_value=connection)
    return connect, connection, cursor


def test_success_binds_database_sets_both_timeouts_and_closes_resources():
    connect, connection, cursor = driver()
    result = ConnectionValidationService(connect).validate(target(connection_timeout_seconds=3, query_timeout_seconds=4))
    assert result.connected
    assert connect.call_args.kwargs == {"timeout": 3, "autocommit": True}
    assert connection.timeout == 4
    assert cursor.execute.call_args_list[0].args == ("SELECT CASE WHEN DB_ID(?) = DB_ID() THEN 1 ELSE 0 END", "Demo")
    cursor.close.assert_called_once()
    connection.close.assert_called_once()
    text = connect.call_args.args[0]
    assert "Trusted_Connection=yes" in text
    assert "Encrypt=yes;TrustServerCertificate=no" in text
    assert "PWD=" not in text


def test_sql_credentials_and_odbc_attribute_injection_are_quoted(caplog):
    connect, _, _ = driver()
    password = " secret};Encrypt=no;PWD={value "
    result = ConnectionValidationService(connect).validate(
        target(authentication="sql", database="Demo;Trusted_Connection=yes"),
        SqlCredentials("test;user", password),
    )
    text = connect.call_args.args[0]
    assert "DATABASE={Demo;Trusted_Connection=yes};" in text
    assert "UID={test;user};" in text
    assert "PWD={ secret}};Encrypt=no;PWD={value };" in text
    assert password not in repr(result) + caplog.text
    assert result.connected


@pytest.mark.parametrize("mode,credentials", [("sql", None), ("windows", SqlCredentials("user", "secret"))])
def test_invalid_authentication_never_connects(mode, credentials):
    connect = Mock()
    result = ConnectionValidationService(connect).validate(target(authentication=mode), credentials)
    assert result.code == ValidationCode.INVALID_CONFIGURATION
    connect.assert_not_called()


@pytest.mark.parametrize("state,code", [
    ("28000", ValidationCode.AUTHENTICATION_FAILED),
    ("HYT00", ValidationCode.TIMEOUT), ("HYT01", ValidationCode.TIMEOUT),
    ("IM002", ValidationCode.DRIVER_UNAVAILABLE), ("IM003", ValidationCode.DRIVER_UNAVAILABLE),
    ("08001", ValidationCode.CONNECTION_FAILED),
    ("3D000", ValidationCode.DATABASE_UNAVAILABLE), ("42000", ValidationCode.VALIDATION_FAILED),
])
def test_driver_errors_are_safe_results(state, code, caplog):
    connect = Mock(side_effect=pyodbc.Error(state, "raw diagnostic PWD=do-not-expose"))
    result = ConnectionValidationService(connect).validate(target())
    assert result.code == code
    assert not result.connected
    assert "do-not-expose" not in repr(result) + caplog.text


@pytest.mark.parametrize("row", [None, (0,)])
def test_wrong_database_is_not_success(row):
    connect, connection, cursor = driver()
    cursor.fetchone.side_effect = None
    cursor.fetchone.return_value = row
    result = ConnectionValidationService(connect).validate(target())
    assert result.code == ValidationCode.DATABASE_UNAVAILABLE
    connection.close.assert_called_once()


@pytest.mark.parametrize("failure_at", ["timeout", "cursor", "execute", "fetchone"])
def test_connection_is_closed_after_probe_failure(failure_at):
    connect, connection, cursor = driver()
    if failure_at == "timeout":
        from unittest.mock import PropertyMock
        type(connection).timeout = PropertyMock(side_effect=pyodbc.Error("HYT00", "private"))
    elif failure_at == "cursor":
        connection.cursor.side_effect = pyodbc.Error("HYT00", "private")
    else:
        getattr(cursor, failure_at).side_effect = pyodbc.Error("HYT00", "private")
    result = ConnectionValidationService(connect).validate(target())
    assert result.code == ValidationCode.TIMEOUT
    connection.close.assert_called_once()
    if failure_at not in ("timeout", "cursor"):
        cursor.close.assert_called_once()


def test_cursor_cleanup_error_does_not_prevent_connection_close():
    connect, connection, cursor = driver()
    cursor.close.side_effect = pyodbc.Error("HY000", "private")
    result = ConnectionValidationService(connect).validate(target())
    assert result.connected
    connection.close.assert_called_once()
