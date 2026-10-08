import pytest
from fastapi.testclient import TestClient

from autotuner_api.app import create_app
from autotuner_api.config import Settings


def test_health_and_openapi_do_not_expose_environment_secrets(monkeypatch):
    monkeypatch.setenv("SQLSERVER_PASSWORD", "test-secret-do-not-return")
    with TestClient(create_app(Settings())) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "autotuner-api"}
        schema = client.get("/openapi.json")
        assert "/api/v1/health" in schema.json()["paths"]
        assert "test-secret-do-not-return" not in response.text + schema.text


def test_environment_overrides_explicit_file_without_mutating_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("AUTOTUNER_API_HOST", raising=False)
    monkeypatch.setenv("AUTOTUNER_API_PORT", "9001")
    env = tmp_path / ".env"
    env.write_text("AUTOTUNER_API_HOST=localhost\nAUTOTUNER_API_PORT=9000\n")
    settings = Settings.load(env)
    assert settings == Settings(host="localhost", port=9001)
    import os
    assert "AUTOTUNER_API_HOST" not in os.environ


@pytest.mark.parametrize("value", ["0", "65536", "invalid", ""])
def test_invalid_port_fails_before_startup(value, tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOTUNER_API_PORT", value)
    with pytest.raises(ValueError, match="AUTOTUNER_API_PORT"):
        Settings.load(tmp_path / "missing.env")


def test_defaults_without_configuration(tmp_path, monkeypatch):
    monkeypatch.delenv("AUTOTUNER_API_HOST", raising=False)
    monkeypatch.delenv("AUTOTUNER_API_PORT", raising=False)
    assert Settings.load(tmp_path / "missing.env") == Settings()


def test_empty_host_rejected():
    with pytest.raises(ValueError, match="AUTOTUNER_API_HOST"):
        Settings(host=" ")
