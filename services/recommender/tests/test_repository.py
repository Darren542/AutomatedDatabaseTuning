from contextlib import nullcontext
from unittest.mock import Mock

import pytest

from recommender.engine import analyze
from recommender.fixtures import acceptance_bundle
from recommender.repository import RecommendationRepository, canonical_json
from recommender.service import RecommendationService


def test_service_saves_only_after_successful_analysis():
    repository = Mock()
    repository.load.return_value = acceptance_bundle()
    repository.save.side_effect = lambda bundle, result: result
    result = RecommendationService(repository).analyze('id')
    assert result['recommendations']
    repository.save.assert_called_once()


def test_ineligible_analysis_is_not_persisted():
    repository = Mock()
    repository.load.return_value = dict(acceptance_bundle(), metadata_observed_at_utc='2020-01-01T00:00:00Z')
    with pytest.raises(ValueError): RecommendationService(repository).analyze('id')
    repository.save.assert_not_called()


def test_analysis_is_parameterized_append_only_and_inputs_are_snapshotted(monkeypatch):
    conn = Mock(); cursor = conn.cursor.return_value
    monkeypatch.setattr('recommender.repository.repository_connection', lambda settings: nullcontext(conn))
    bundle = acceptance_bundle()
    result = RecommendationRepository().save(bundle, analyze(bundle))
    sql, *values = cursor.execute.call_args.args
    assert sql.count('?') == len(values)
    assert 'INSERT INTO dbo.RecommendationAnalysis' in sql
    assert values[-2] == canonical_json(bundle)
    assert result['input_hash'] and result['analysis_id']
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()


def test_save_failure_rolls_back(monkeypatch):
    conn = Mock(); conn.cursor.return_value.execute.side_effect = RuntimeError('write failure')
    monkeypatch.setattr('recommender.repository.repository_connection', lambda settings: nullcontext(conn))
    with pytest.raises(RuntimeError): RecommendationRepository().save(acceptance_bundle(), analyze(acceptance_bundle()))
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
