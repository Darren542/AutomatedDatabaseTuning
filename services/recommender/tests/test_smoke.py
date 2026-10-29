import pytest
from recommender.main import main


def test_cli_requires_an_explicit_collection_before_any_analysis(monkeypatch):
    monkeypatch.setattr('sys.argv', ['autotuner-recommender'])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
