import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app({
        "TESTING": True,
        "DB_PATH": db_path,
        "IMPORT_FOLDER": str(tmp_path / "imports"),
        "PROCESSED_FOLDER": str(tmp_path / "imports" / "processed"),
    })
    with app.test_client() as client:
        yield client


def test_homepage_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Finance Tracker" in response.data
