import pytest

from database import get_session, init_db
from models import Account, Balance, CsvProfile, Transaction


@pytest.fixture
def db_session(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    session = get_session(db_path)
    yield session
    session.close()


def test_create_account(db_session):
    account = Account(name="Chase Checking", account_type="checking", institution="Chase")
    db_session.add(account)
    db_session.commit()
    result = db_session.query(Account).first()
    assert result.name == "Chase Checking"
    assert result.account_type == "checking"


def test_create_transaction(db_session):
    account = Account(name="Chase", account_type="checking", institution="Chase")
    db_session.add(account)
    db_session.commit()
    txn = Transaction(
        date="2026-01-15", amount=-45.50, category="Dining",
        description="Restaurant ABC", account_id=account.id,
    )
    db_session.add(txn)
    db_session.commit()
    result = db_session.query(Transaction).first()
    assert result.amount == -45.50
    assert result.account.name == "Chase"


def test_create_balance_snapshot(db_session):
    account = Account(name="Fidelity", account_type="brokerage", institution="Fidelity")
    db_session.add(account)
    db_session.commit()
    balance = Balance(month="2026-01", account_id=account.id, balance=50000.00)
    db_session.add(balance)
    db_session.commit()
    result = db_session.query(Balance).first()
    assert result.balance == 50000.00


def test_create_csv_profile(db_session):
    profile = CsvProfile(
        name="Chase Checking", institution="Chase",
        column_mapping='{"date": "Posting Date", "amount": "Amount", "description": "Description"}',
        date_format="%m/%d/%Y",
    )
    db_session.add(profile)
    db_session.commit()
    result = db_session.query(CsvProfile).first()
    assert result.institution == "Chase"


def test_transaction_fingerprint(db_session):
    account = Account(name="Chase", account_type="checking", institution="Chase")
    db_session.add(account)
    db_session.commit()
    txn = Transaction(
        date="2026-01-15", amount=-45.50, category="Dining",
        description="Restaurant ABC", account_id=account.id,
    )
    db_session.add(txn)
    db_session.commit()
    assert txn.fingerprint is not None
    # Same data should produce same fingerprint
    txn2 = Transaction(
        date="2026-01-15", amount=-45.50, category="Dining",
        description="Restaurant ABC", account_id=account.id,
    )
    assert txn2.fingerprint == txn.fingerprint
