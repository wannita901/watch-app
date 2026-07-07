import os

import pytest
from fastapi.testclient import TestClient

TEST_API_KEY = "test-key"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("API_KEY", TEST_API_KEY)
    # fresh app per test so lifespan creates the tmp db
    from importlib import reload

    import db
    import main

    reload(db)
    reload(main)
    with TestClient(main.app) as c:
        yield c


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from importlib import reload

    import db

    reload(db)
    connection = db.connect()
    yield connection
    connection.close()
