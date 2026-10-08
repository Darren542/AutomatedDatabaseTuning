from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from autotuner_api.app import create_app
from autotuner_api.config import Settings
from autotuner_api.routes.targets import get_validation_service
from collector.connection_validation import ConnectionValidationResult, ValidationCode


@pytest.fixture
def api():
    service = Mock()
    service.validate.return_value = ConnectionValidationResult(ValidationCode.CONNECTED, "Connected.")
    app = create_app(Settings())
    app.dependency_overrides[get_validation_service] = lambda: service
    with TestClient(app) as client:
        yield client, service


def payload(**changes):
    return {"name": "Local demo", "server": r"localhost\SQLEXPRESS", "database": "WideWorldImporters", **changes}


def test_windows_request_maps_to_domain_and_returns_only_result(api):
    client, service = api
    response = client.post("/api/v1/targets/test-connection", json=payload(trust_server_certificate=True))
    assert response.status_code == 200
    assert response.json() == {"connected": True, "code": "connected", "message": "Connected."}
    target, credentials = service.validate.call_args.args
    assert target.server == r"localhost\SQLEXPRESS"
    assert target.trust_server_certificate is True
    assert credentials is None


def test_sql_credentials_are_transient_and_not_echoed(api, caplog):
    client, service = api
    secret = " secret;{} "
    response = client.post("/api/v1/targets/test-connection", json=payload(
        authentication="sql", credentials={"username": "private-user", "password": secret}))
    assert response.status_code == 200
    assert service.validate.call_args.args[1].password == secret
    assert secret not in response.text + caplog.text
    assert "private-user" not in response.text + caplog.text


@pytest.mark.parametrize("changes", [
    {"authentication": "sql"},
    {"credentials": {"username": "user", "password": "secret"}},
    {"database": " "}, {"server": "\u0000"},
    {"authentication": "sql", "credentials": {"username": "user", "password": ""}},
    {"connection_timeout_seconds": 0}, {"query_timeout_seconds": True},
    {"encrypt": "false"}, {"server": 123}, {"authentication": "other"},
    {"credentials": {"username": "user", "password": {"secret-value": "secret-value"}}},
    {"secret-value": "secret-value"},
])
def test_invalid_input_never_connects_or_echoes_body(api, changes, caplog):
    client, service = api
    response = client.post("/api/v1/targets/test-connection", json=payload(**changes))
    assert response.status_code == 422
    assert "secret-value" not in response.text + caplog.text
    assert "secret\"" not in response.text
    service.validate.assert_not_called()


def test_malformed_json_is_safe(api):
    client, service = api
    response = client.post("/api/v1/targets/test-connection", content='{"password":"secret-value",', headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "secret-value" not in response.text
    service.validate.assert_not_called()


@pytest.mark.parametrize("code", [ValidationCode.AUTHENTICATION_FAILED, ValidationCode.TIMEOUT, ValidationCode.CONNECTION_FAILED])
def test_connection_failures_are_completed_tests_not_success(api, code):
    client, service = api
    service.validate.return_value = ConnectionValidationResult(code, "Safe failure message.")
    response = client.post("/api/v1/targets/test-connection", json=payload())
    assert response.status_code == 200
    assert response.json() == {"connected": False, "code": code.value, "message": "Safe failure message."}


def test_endpoint_does_not_implement_saving_and_openapi_describes_password(api):
    client, _ = api
    assert client.post("/api/v1/targets", json=payload()).status_code == 404
    schema = client.get("/openapi.json").json()
    password = schema["components"]["schemas"]["CredentialsRequest"]["properties"]["password"]
    assert password["writeOnly"] is True
    assert password["format"] == "password"
    assert "credentials" not in schema["components"]["schemas"]["TestConnectionResponse"]["properties"]
