from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from autotuner_api.app import create_app
from autotuner_api.config import Settings
from autotuner_api.routes.recommendations import get_repository, get_service
from recommender.engine import analyze
from recommender.fixtures import acceptance_bundle


@pytest.fixture
def api():
    app = create_app(Settings())
    service, repository = Mock(), Mock()
    service.analyze.return_value = dict(analyze(acceptance_bundle()), analysis_id=str(uuid4()))
    repository.get.return_value = service.analyze.return_value
    repository.list.return_value = []
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_repository] = lambda: repository
    with TestClient(app) as client:
        yield client, service, repository


def test_analyze_returns_ranked_advisory_recommendations(api):
    client, service, _ = api
    batch = str(uuid4())
    response = client.post('/api/v1/recommendations/analyze', json={'batch_id': batch})
    assert response.status_code == 201
    assert response.json()['recommendations'][0]['action'] == 'CREATE'
    assert service.analyze.call_args.args[0].hex == batch.replace('-', '')


@pytest.mark.parametrize('body', [
    {}, {'batch_id': 'bad'}, {'batch_id': str(uuid4()), 'weights': {'read_weight': -1}},
    {'batch_id': str(uuid4()), 'weights': {'minimum_drop_hours': 0}},
    {'batch_id': str(uuid4()), 'execute': True},
])
def test_invalid_requests_cannot_execute_or_relax_drop_safety(api, body):
    client, service, _ = api
    assert client.post('/api/v1/recommendations/analyze', json=body).status_code == 422
    service.analyze.assert_not_called()


@pytest.mark.parametrize('error,status', [(KeyError('missing'), 404), (ValueError('Collect fresh metadata.'), 422)])
def test_missing_or_ineligible_collection_has_explicit_error(api, error, status):
    client, service, _ = api
    service.analyze.side_effect = error
    assert client.post('/api/v1/recommendations/analyze', json={'batch_id': str(uuid4())}).status_code == status


def test_saved_analysis_can_be_reopened(api):
    client, _, repository = api
    analysis_id = str(uuid4())
    assert client.get(f'/api/v1/recommendations/analyses/{analysis_id}').status_code == 200
    assert client.get('/api/v1/recommendations/analyses').json() == []
    repository.get.assert_called_once()


def test_no_execute_endpoint_is_exposed(api):
    client, _, _ = api
    assert client.post('/api/v1/recommendations/execute', json={}).status_code == 404
