import subprocess
import sys


def test_repository_import_does_not_depend_on_api_import_order():
    result = subprocess.run([sys.executable, '-c',
        'from collector.repository.collection_lock import target_collection_lock; '
        'from collector.collection import CollectionRunner; '
        'from collector.repository.evidence import SqlEvidenceRepository'],
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
