import pytest

from app import create_app
from database import get_session, init_db
from models import Account, Balance, CsvProfile, Transaction


@pytest.fixture
def app(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app({
        "TESTING": True,
        "DB_PATH": db_path,
        "IMPORT_FOLDER": str(tmp_path / "imports"),
        "PROCESSED_FOLDER": str(tmp_path / "imports" / "processed"),
    })
    init_db(db_path)
    # Seed test data
    session = get_session(db_path)
    account = Account(name="Chase Checking", account_type="checking", institution="Chase")
    brokerage = Account(name="Fidelity", account_type="brokerage", institution="Fidelity")
    session.add_all([account, brokerage])
    session.commit()

    txns = [
        Transaction(date="2026-01-15", amount=-45.50, category="Dining", description="Restaurant", account_id=account.id),
        Transaction(date="2026-01-10", amount=-123.45, category="Groceries", description="Grocery Store", account_id=account.id),
        Transaction(date="2026-01-05", amount=-60.00, category="Dining", description="Pizza Place", account_id=account.id),
        Transaction(date="2025-12-15", amount=-30.00, category="Dining", description="Cafe", account_id=account.id),
        Transaction(date="2025-12-10", amount=-100.00, category="Groceries", description="Grocery Store", account_id=account.id),
        Transaction(date="2026-01-01", amount=5000.00, category="Income", description="Payroll", account_id=account.id),
    ]
    session.add_all(txns)

    for month, val in [("2025-11", 42000), ("2025-12", 41000), ("2026-01", 45000)]:
        session.add(Balance(month=month, account_id=brokerage.id, balance=val))

    session.commit()
    session.close()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_accounts_page(client):
    response = client.get("/accounts")
    assert response.status_code == 200
    assert b"Chase Checking" in response.data


def test_add_account(client):
    response = client.post("/accounts", data={
        "name": "Amex Gold",
        "account_type": "credit_card",
        "institution": "Amex",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Amex Gold" in response.data


def test_import_page(client):
    response = client.get("/import")
    assert response.status_code == 200
    assert b"Watch Folder" in response.data


def test_spending_page(client):
    response = client.get("/spending?month=2026-01")
    assert response.status_code == 200


def test_spending_api(client):
    response = client.get("/api/spending?month=2026-01")
    assert response.status_code == 200
    data = response.get_json()
    assert "categories" in data
    assert "comparison" in data
    dining = next(c for c in data["categories"] if c["name"] == "Dining")
    assert dining["total"] == 105.50


def test_spending_comparison(client):
    response = client.get("/api/spending?month=2026-01")
    data = response.get_json()
    dining_cmp = next(c for c in data["comparison"] if c["name"] == "Dining")
    assert dining_cmp["change"] == 75.50


def test_investments_page(client):
    response = client.get("/investments")
    assert response.status_code == 200


def test_investments_api(client):
    response = client.get("/api/investments")
    data = response.get_json()
    assert data["total_current"] == 45000
    assert len(data["accounts"]) == 1


def test_fixed_page(client):
    response = client.get("/fixed")
    assert response.status_code == 200


def test_overview_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Net Worth" in response.data


def test_overview_api(client):
    response = client.get("/api/overview")
    data = response.get_json()
    assert len(data["net_worth_history"]) == 3
