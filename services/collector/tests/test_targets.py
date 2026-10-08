from dataclasses import asdict

import pytest

from collector.targets import SqlCredentials, TargetConfiguration, TargetConfigurationError


def target(**overrides):
    return TargetConfiguration(**dict(dict(name="Demo", server=r"localhost\SQLEXPRESS", database="WideWorldImporters"), **overrides))


@pytest.mark.parametrize("field,value", [
    ("name", ""), ("server", " "), ("database", None), ("database", "x\x00y"),
    ("authentication", "other"), ("driver", "arbitrary-driver"),
    ("connection_timeout_seconds", 0), ("connection_timeout_seconds", 61),
    ("connection_timeout_seconds", True), ("query_timeout_seconds", "5"),
    ("encrypt", "false"), ("trust_server_certificate", 1),
])
def test_invalid_configuration_rejected(field, value):
    with pytest.raises(TargetConfigurationError):
        target(**{field: value})


def test_metadata_has_no_credentials_and_credentials_repr_is_redacted():
    assert "password" not in asdict(target())
    credentials = SqlCredentials("private-user", " secret;with}characters ")
    assert credentials.password == " secret;with}characters "
    assert "secret" not in repr(credentials)
    assert "private-user" not in repr(credentials)


@pytest.mark.parametrize("username,password", [("", "secret"), ("user", ""), ("user", "a\x00b")])
def test_invalid_credentials_have_safe_errors(username, password):
    with pytest.raises(TargetConfigurationError) as error:
        SqlCredentials(username, password)
    assert "secret" not in str(error.value)
