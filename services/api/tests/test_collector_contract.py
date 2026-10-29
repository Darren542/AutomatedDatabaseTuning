from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from fastapi.testclient import TestClient

from autotuner_api.app import create_app
from autotuner_api.config import Settings
from autotuner_api.routes.targets import get_target_repository, get_validation_service
from autotuner_api.routes.collections import CollectionResponse, CreateCollectionRequest
from collector.connection_validation import ConnectionValidationResult, ValidationCode


def test_connected_but_unready_target_cannot_be_saved():
    service=Mock()
    service.validate.return_value=ConnectionValidationResult(ValidationCode.EXCESSIVE_PERMISSIONS, 'Restricted account required.', database_connected=True)
    repository=Mock()
    app=create_app(Settings())
    app.dependency_overrides[get_target_repository]=lambda:repository
    app.dependency_overrides[get_validation_service]=lambda:service
    with TestClient(app) as client:
        response=client.post('/api/v1/targets',json={'name':'Unsafe','server':'localhost','database':'Demo'})
    assert response.status_code==422
    repository.create.assert_not_called()


def test_saved_sql_reference_is_resolved_server_side(monkeypatch):
    repository=Mock()
    repository.get.return_value=SimpleNamespace(configuration=SimpleNamespace(authentication=SimpleNamespace(value='sql')),credential_reference='TEST')
    resolver=Mock(return_value=object())
    monkeypatch.setattr('autotuner_api.routes.targets.resolve_credentials',resolver)
    service=Mock()
    service.validate.return_value=ConnectionValidationResult(ValidationCode.INSUFFICIENT_PERMISSIONS,'Access missing.',database_connected=True)
    app=create_app(Settings())
    app.dependency_overrides[get_target_repository]=lambda:repository
    app.dependency_overrides[get_validation_service]=lambda:service
    with TestClient(app) as client:
        response=client.post(f'/api/v1/targets/{uuid4()}/test-connection')
    assert response.status_code==200
    assert response.json()['connected'] is True
    assert response.json()['collector_ready'] is False
    resolver.assert_called_once_with('TEST')


def test_collection_response_marks_naive_repository_dates_as_utc():
    now=datetime(2026,10,12,12)
    batch=CollectionResponse(batch_id=uuid4(),target_id=uuid4(),label=None,
        requested_window_start_utc=None,requested_window_end_utc=None,
        effective_window_start_utc=now,effective_window_end_utc=now,window_source='Explicit',
        force_metadata=False,collection_started_at_utc=now,collection_completed_at_utc=None,
        status='Collecting',completeness_percent=0,collector_version='test',failure_reason=None,
        created_at_utc=now,updated_at_utc=now)
    assert batch.created_at_utc.tzinfo==timezone.utc
    assert '2026-10-12T12:00:00Z' in batch.model_dump_json()
