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
    service.validate.return_value = ConnectionValidationResult(ValidationCode.CONNECTED, "Connected.", database_connected=True, query_store_readable=True, index_usage_readable=True, metadata_readable=True, ddl_restricted=True, source_state_readable=True, index_operational_readable=True, missing_indexes_readable=True)
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
    assert response.json()["collector_ready"] is True
    assert response.json()["code"] == "connected"
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
    assert response.json()["connected"] is False
    assert response.json()["code"] == code.value


def test_endpoint_does_not_implement_saving_and_openapi_describes_password(api):
    client, _ = api
    schema = client.get("/openapi.json").json()
    assert "post" in schema["paths"]["/api/v1/targets"]
    schema = client.get("/openapi.json").json()
    password = schema["components"]["schemas"]["CredentialsRequest"]["properties"]["password"]
    assert password["writeOnly"] is True
    assert password["format"] == "password"
    assert "credentials" not in schema["components"]["schemas"]["TestConnectionResponse"]["properties"]


def elevated_result(**changes):
    capabilities=dict(database_connected=True,query_store_readable=True,index_usage_readable=True,
        metadata_readable=True,ddl_restricted=False,source_state_readable=True,
        index_operational_readable=True,missing_indexes_readable=True)
    capabilities.update(changes)
    return ConnectionValidationResult(ValidationCode.EXCESSIVE_PERMISSIONS,'Permission warning.',**capabilities)


def save_repository(client):
    from types import SimpleNamespace
    from uuid import uuid4
    from autotuner_api.routes.targets import get_target_repository
    repository=Mock()
    repository.create.side_effect=lambda config,credential_reference:SimpleNamespace(
        target_id=uuid4(),configuration=config,credential_reference=credential_reference,is_enabled=True)
    client.app.dependency_overrides[get_target_repository]=lambda:repository
    return repository


def test_elevated_connection_can_be_saved_after_explicit_acknowledgement(api):
    client,service=api;repository=save_repository(client)
    service.validate.return_value=elevated_result()
    tested=client.post('/api/v1/targets/test-connection',json=payload()).json()
    assert tested['collector_ready'] and tested['code']=='excessive_permissions' and not tested['ddl_restricted']
    assert client.post('/api/v1/targets',json=payload()).status_code==428
    repository.create.assert_not_called()
    response=client.post('/api/v1/targets',json=payload(acknowledge_excessive_permissions=True))
    assert response.status_code==201
    assert 'acknowledge_excessive_permissions' not in response.json()
    repository.create.assert_called_once()


@pytest.mark.parametrize('capability',['database_connected','query_store_readable','index_usage_readable',
    'metadata_readable','source_state_readable','index_operational_readable','missing_indexes_readable'])
def test_permission_acknowledgement_never_bypasses_missing_required_access(api,capability):
    client,service=api;repository=save_repository(client)
    service.validate.return_value=elevated_result(**{capability:False})
    response=client.post('/api/v1/targets',json=payload(acknowledge_excessive_permissions=True))
    assert response.status_code==422
    repository.create.assert_not_called()


def test_save_rechecks_permissions_even_after_a_restricted_test_passes(api):
    client,service=api;repository=save_repository(client)
    restricted=service.validate.return_value
    service.validate.side_effect=[restricted,elevated_result(),elevated_result()]
    assert client.post('/api/v1/targets/test-connection',json=payload()).json()['ddl_restricted'] is True
    assert client.post('/api/v1/targets',json=payload()).status_code==428
    assert client.post('/api/v1/targets',json=payload(acknowledge_excessive_permissions=True)).status_code==201
    repository.create.assert_called_once()
