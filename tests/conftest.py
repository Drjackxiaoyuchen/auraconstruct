import pytest


@pytest.fixture(autouse=True)
def isolated_local_data(tmp_path,monkeypatch):
    monkeypatch.setenv('AURACONSTRUCT_DATA_DIR',str(tmp_path/'private-data'))
    monkeypatch.delenv('AURACONSTRUCT_PLANNOTATE',raising=False)
    monkeypatch.delenv('AURACONSTRUCT_LIBRARY',raising=False)
