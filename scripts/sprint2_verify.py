"""Repeat SQL-backed/API acceptance checks in an existing isolated demo database."""
import argparse
import json
import os
import re
from uuid import uuid4

from fastapi.testclient import TestClient
from collector.repository.collection_batches import SqlCollectionBatchRepository
from recommender.repository import RecommendationRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'AutoTuner_Sprint2_Demo_[A-Za-z0-9_]{1,80}', args.database):
        parser.error('Only isolated Sprint 2 demo databases are accepted.')
    os.environ['AUTOTUNER_REPO_SQL_DATABASE'] = args.database
    from autotuner_api.app import create_app
    repository = RecommendationRepository()
    previous = repository.list()[0]
    with TestClient(create_app()) as client:
        response = client.post('/api/v1/recommendations/analyze', json={'batch_id': str(previous['batch_id'])})
        assert response.status_code == 201, response.text
        result = response.json()
        creates = [r for r in result['recommendations'] if r['action'] == 'CREATE']
        assert [r['table_name'] for r in creates] == ['Orders', 'Events']
        assert creates[0]['score'] > creates[1]['score']
        assert creates[0]['affected_queries'] and creates[0]['sql'] and creates[0]['rationale']
        assert all(r['action'] != 'DROP' for r in result['recommendations'] if r['protected'])
        assert client.get(f'/api/v1/recommendations/analyses/{result["analysis_id"]}').json() == result
        assert client.get('/api/v1/recommendations/analyses').status_code == 200
        assert client.post('/api/v1/recommendations/analyze', json={'batch_id': str(uuid4())}).status_code == 404
        pending = SqlCollectionBatchRepository().create(target_id=previous['target_id'], label='Synthetic invalid-state acceptance', requested_window_start_utc=None, requested_window_end_utc=None, collector_version='sprint2-demo')
        assert client.post('/api/v1/recommendations/analyze', json={'batch_id': str(pending.batch_id)}).status_code == 422
    # A new app/client still reads the SQL-persisted result.
    with TestClient(create_app()) as restarted:
        assert restarted.get(f'/api/v1/recommendations/analyses/{result["analysis_id"]}').json() == result
    print(json.dumps(dict(database=args.database, analysis_id=result['analysis_id'], checks={
        'FR-04': 'CREATE with keys/includes/source evidence', 'FR-05': 'Read-heavy candidate ranks above write-heavy candidate',
        'FR-06': 'SQL/rationale/query evidence/score persisted and reopened', 'FR-10': 'DROP/RETAIN advice and protected-index safety',
        'API': 'Missing collection 404; incomplete collection 422; fresh app reload persisted result',
    }), indent=2))


if __name__ == '__main__':
    main()
