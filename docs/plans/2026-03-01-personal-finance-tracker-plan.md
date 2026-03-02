# Personal Finance Tracker — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local-only personal finance dashboard that consolidates spending, investments, fixed expenses, and net worth from CSV imports into a single view.

**Architecture:** Flask web app serving Jinja2 templates with Chart.js visualizations and htmx for tab switching. SQLite database stores all financial data. A watch folder auto-imports CSVs on app startup with format auto-detection and deduplication.

**Tech Stack:** Python 3, Flask, SQLAlchemy, SQLite, Jinja2, Chart.js, htmx, pytest

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `app.py`
- Create: `config.py`
- Create: `templates/base.html`
- Test: `tests/test_app.py`

**Step 1: Create virtual environment and requirements**

```
requirements.txt:
flask==3.1.*
sqlalchemy==2.0.*
pytest==8.*
```

Run: `cd ~/personal-finance-tracker && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`

**Step 2: Write the failing test**

```python
# tests/test_app.py
import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    with app.test_client() as client:
        yield client

def test_homepage_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Finance Tracker" in response.data
```

Run: `pytest tests/test_app.py -v`
Expected: FAIL — `app` module doesn't exist yet

**Step 3: Write minimal Flask app**

```python
# config.py
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    DB_PATH = os.path.join(BASE_DIR, "data", "finance.db")
    IMPORT_FOLDER = os.path.join(BASE_DIR, "imports")
    PROCESSED_FOLDER = os.path.join(BASE_DIR, "imports", "processed")
    SECRET_KEY = "dev-local-only"
```

```python
# app.py
from flask import Flask, render_template
from config import Config
import os

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    # Ensure data and import directories exist
    os.makedirs(os.path.dirname(app.config["DB_PATH"]), exist_ok=True)
    os.makedirs(app.config["IMPORT_FOLDER"], exist_ok=True)
    os.makedirs(app.config["PROCESSED_FOLDER"], exist_ok=True)

    @app.route("/")
    def index():
        return render_template("index.html")

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
```

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Finance Tracker</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <script src="https://unpkg.com/htmx.org@2"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f5f5; color: #333; }
        nav { background: #1a1a2e; color: white; padding: 1rem 2rem; display: flex; gap: 2rem; align-items: center; }
        nav a { color: #ccc; text-decoration: none; padding: 0.5rem 1rem; border-radius: 4px; }
        nav a:hover, nav a.active { color: white; background: #16213e; }
        nav h1 { font-size: 1.2rem; margin-right: auto; }
        .container { max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }
        .card { background: white; border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .card h2 { margin-bottom: 1rem; font-size: 1.1rem; color: #555; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem; }
        .stat { text-align: center; }
        .stat .value { font-size: 2rem; font-weight: bold; }
        .stat .label { color: #888; font-size: 0.9rem; }
        .positive { color: #2ecc71; }
        .negative { color: #e74c3c; }
        .change { font-size: 0.85rem; margin-top: 0.25rem; }
        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #eee; }
        th { color: #888; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; }
        .import-banner { background: #d4edda; border: 1px solid #c3e6cb; padding: 0.75rem 1rem; border-radius: 4px; margin-bottom: 1rem; }
        select, input { padding: 0.4rem 0.8rem; border: 1px solid #ddd; border-radius: 4px; }
    </style>
</head>
<body>
    <nav>
        <h1>Finance Tracker</h1>
        <a href="/" {% if request.path == "/" %}class="active"{% endif %}>Overview</a>
        <a href="/spending" {% if request.path == "/spending" %}class="active"{% endif %}>Spending</a>
        <a href="/investments" {% if request.path == "/investments" %}class="active"{% endif %}>Investments</a>
        <a href="/fixed" {% if request.path == "/fixed" %}class="active"{% endif %}>Fixed Expenses</a>
        <a href="/accounts" {% if request.path == "/accounts" %}class="active"{% endif %}>Accounts</a>
        <a href="/import" {% if request.path == "/import" %}class="active"{% endif %}>Import</a>
    </nav>
    <div class="container">
        {% block content %}{% endblock %}
    </div>
</body>
</html>
```

```html
<!-- templates/index.html -->
{% extends "base.html" %}
{% block content %}
<h2>Welcome to Finance Tracker</h2>
<p>Your personal finance dashboard.</p>
{% endblock %}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_app.py -v`
Expected: PASS

---

### Task 2: Database Models

**Files:**
- Create: `models.py`
- Create: `database.py`
- Test: `tests/test_models.py`

**Step 1: Write failing tests for models**

```python
# tests/test_models.py
import pytest
import os
from database import init_db, get_session
from models import Account, Transaction, Balance, CsvProfile

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
    txn = Transaction(date="2026-01-15", amount=-45.50, category="Dining",
                      description="Restaurant ABC", account_id=account.id)
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
        name="Chase Checking",
        institution="Chase",
        column_mapping='{"date": "Posting Date", "amount": "Amount", "description": "Description", "category": "Type"}',
        date_format="%m/%d/%Y"
    )
    db_session.add(profile)
    db_session.commit()
    result = db_session.query(CsvProfile).first()
    assert result.institution == "Chase"

def test_transaction_duplicate_detection(db_session):
    account = Account(name="Chase", account_type="checking", institution="Chase")
    db_session.add(account)
    db_session.commit()
    txn = Transaction(date="2026-01-15", amount=-45.50, category="Dining",
                      description="Restaurant ABC", account_id=account.id)
    db_session.add(txn)
    db_session.commit()
    assert txn.fingerprint is not None
    # Same transaction data should produce same fingerprint
    txn2 = Transaction(date="2026-01-15", amount=-45.50, category="Dining",
                       description="Restaurant ABC", account_id=account.id)
    assert txn2.fingerprint == txn.fingerprint
```

Run: `pytest tests/test_models.py -v`
Expected: FAIL — modules don't exist

**Step 2: Implement database and models**

```python
# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()
_engines = {}

def init_db(db_path):
    engine = create_engine(f"sqlite:///{db_path}")
    _engines[db_path] = engine
    Base.metadata.create_all(engine)
    return engine

def get_session(db_path):
    engine = _engines.get(db_path)
    if not engine:
        engine = init_db(db_path)
    Session = sessionmaker(bind=engine)
    return Session()
```

```python
# models.py
import hashlib
from sqlalchemy import Column, Integer, String, Float, ForeignKey, event
from sqlalchemy.orm import relationship
from database import Base

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    account_type = Column(String, nullable=False)  # checking, credit_card, brokerage, fsa, hsa, mortgage, savings
    institution = Column(String, nullable=False)
    transactions = relationship("Transaction", back_populates="account")
    balances = relationship("Balance", back_populates="account")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    date = Column(String, nullable=False)       # YYYY-MM-DD
    amount = Column(Float, nullable=False)       # negative = expense, positive = income
    category = Column(String, default="Uncategorized")
    description = Column(String)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    fingerprint = Column(String, index=True)     # for dedup
    account = relationship("Account", back_populates="transactions")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._compute_fingerprint()

    def _compute_fingerprint(self):
        raw = f"{self.date}|{self.amount}|{self.description}|{self.account_id}"
        self.fingerprint = hashlib.sha256(raw.encode()).hexdigest()[:16]

class Balance(Base):
    __tablename__ = "balances"
    id = Column(Integer, primary_key=True)
    month = Column(String, nullable=False)       # YYYY-MM
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    balance = Column(Float, nullable=False)
    account = relationship("Account", back_populates="balances")

class CsvProfile(Base):
    __tablename__ = "csv_profiles"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    institution = Column(String, nullable=False)
    column_mapping = Column(String, nullable=False)   # JSON string
    date_format = Column(String, default="%Y-%m-%d")
    account_type = Column(String, default="checking")
```

**Step 3: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: ALL PASS

---

### Task 3: CSV Import Engine

**Files:**
- Create: `importer.py`
- Test: `tests/test_importer.py`
- Test fixtures: `tests/fixtures/chase_checking.csv`, `tests/fixtures/amex_credit.csv`

**Step 1: Create test CSV fixtures**

```csv
# tests/fixtures/chase_checking.csv
Posting Date,Description,Amount,Type,Balance,Check or Slip #
01/15/2026,RESTAURANT ABC,-45.50,DEBIT_CARD,,
01/14/2026,GROCERY STORE,-123.45,DEBIT_CARD,,
01/13/2026,PAYROLL DEPOSIT,5000.00,CREDIT,,
```

```csv
# tests/fixtures/amex_credit.csv
Date,Description,Amount
01/15/2026,AMAZON PURCHASE,89.99
01/14/2026,GAS STATION,42.30
01/10/2026,PAYMENT RECEIVED,-500.00
```

Note: Amex CSVs treat charges as positive and payments as negative (opposite of most banks). The importer should handle sign normalization per profile.

**Step 2: Write failing tests**

```python
# tests/test_importer.py
import pytest
import os
import shutil
from importer import detect_csv_format, parse_csv, scan_import_folder, import_file
from database import init_db, get_session
from models import Account, Transaction, CsvProfile

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

@pytest.fixture
def db_session(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    session = get_session(db_path)
    # Seed with known profiles
    chase_profile = CsvProfile(
        name="Chase Checking", institution="Chase", account_type="checking",
        column_mapping='{"date": "Posting Date", "amount": "Amount", "description": "Description"}',
        date_format="%m/%d/%Y"
    )
    amex_profile = CsvProfile(
        name="Amex Credit", institution="Amex", account_type="credit_card",
        column_mapping='{"date": "Date", "amount": "Amount", "description": "Description"}',
        date_format="%m/%d/%Y"
    )
    session.add_all([chase_profile, amex_profile])
    session.commit()
    yield session
    session.close()

def test_detect_chase_format(db_session):
    filepath = os.path.join(FIXTURES, "chase_checking.csv")
    profile = detect_csv_format(filepath, db_session)
    assert profile is not None
    assert profile.institution == "Chase"

def test_detect_amex_format(db_session):
    filepath = os.path.join(FIXTURES, "amex_credit.csv")
    profile = detect_csv_format(filepath, db_session)
    assert profile is not None
    assert profile.institution == "Amex"

def test_parse_chase_csv(db_session):
    filepath = os.path.join(FIXTURES, "chase_checking.csv")
    profile = detect_csv_format(filepath, db_session)
    account = Account(name="Chase Checking", account_type="checking", institution="Chase")
    db_session.add(account)
    db_session.commit()
    transactions = parse_csv(filepath, profile, account.id)
    assert len(transactions) == 3
    assert transactions[0].amount == -45.50
    assert transactions[2].amount == 5000.00

def test_deduplication(db_session):
    filepath = os.path.join(FIXTURES, "chase_checking.csv")
    profile = detect_csv_format(filepath, db_session)
    account = Account(name="Chase Checking", account_type="checking", institution="Chase")
    db_session.add(account)
    db_session.commit()
    # Import once
    txns1 = import_file(filepath, profile, account.id, db_session)
    assert len(txns1) == 3
    # Import same file again — should add 0 new
    txns2 = import_file(filepath, profile, account.id, db_session)
    assert len(txns2) == 0
    assert db_session.query(Transaction).count() == 3

def test_scan_import_folder(tmp_path, db_session):
    import_dir = tmp_path / "imports"
    import_dir.mkdir()
    processed_dir = import_dir / "processed"
    processed_dir.mkdir()
    # Copy fixture into import folder
    shutil.copy(os.path.join(FIXTURES, "chase_checking.csv"), str(import_dir))
    files = scan_import_folder(str(import_dir))
    assert len(files) == 1
    assert files[0].endswith(".csv")
```

Run: `pytest tests/test_importer.py -v`
Expected: FAIL — `importer` module doesn't exist

**Step 3: Implement importer**

```python
# importer.py
import csv
import json
import os
from datetime import datetime
from models import Transaction, CsvProfile

def scan_import_folder(import_folder):
    """Return list of CSV files in import folder (not in processed/)."""
    files = []
    for f in os.listdir(import_folder):
        if f.lower().endswith(".csv") and os.path.isfile(os.path.join(import_folder, f)):
            files.append(os.path.join(import_folder, f))
    return sorted(files)

def detect_csv_format(filepath, db_session):
    """Match a CSV file to a known CsvProfile by comparing column headers."""
    with open(filepath, "r") as f:
        reader = csv.reader(f)
        headers = next(reader)
    headers_set = set(h.strip() for h in headers)

    profiles = db_session.query(CsvProfile).all()
    best_match = None
    best_score = 0
    for profile in profiles:
        mapping = json.loads(profile.column_mapping)
        expected_cols = set(mapping.values())
        score = len(expected_cols & headers_set) / len(expected_cols)
        if score > best_score:
            best_score = score
            best_match = profile
    return best_match if best_score >= 0.5 else None

def parse_csv(filepath, profile, account_id):
    """Parse CSV into Transaction objects using profile's column mapping."""
    mapping = json.loads(profile.column_mapping)
    transactions = []
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row.get(mapping["date"], "").strip()
            amount_str = row.get(mapping["amount"], "0").strip()
            description = row.get(mapping.get("description", ""), "").strip()
            category = row.get(mapping.get("category", ""), "Uncategorized").strip() or "Uncategorized"

            try:
                date = datetime.strptime(date_str, profile.date_format).strftime("%Y-%m-%d")
                amount = float(amount_str.replace(",", ""))
            except (ValueError, AttributeError):
                continue  # Skip unparseable rows

            txn = Transaction(
                date=date, amount=amount, category=category,
                description=description, account_id=account_id
            )
            transactions.append(txn)
    return transactions

def import_file(filepath, profile, account_id, db_session):
    """Parse CSV and insert only non-duplicate transactions. Returns list of new transactions."""
    transactions = parse_csv(filepath, profile, account_id)
    existing_fps = set(
        fp for (fp,) in db_session.query(Transaction.fingerprint)
        .filter(Transaction.account_id == account_id).all()
    )
    new_txns = [t for t in transactions if t.fingerprint not in existing_fps]
    db_session.add_all(new_txns)
    db_session.commit()
    return new_txns

def move_to_processed(filepath, processed_folder):
    """Move imported file to processed folder."""
    os.makedirs(processed_folder, exist_ok=True)
    dest = os.path.join(processed_folder, os.path.basename(filepath))
    os.rename(filepath, dest)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_importer.py -v`
Expected: ALL PASS

---

### Task 4: Account Management Pages

**Files:**
- Modify: `app.py` — add account routes
- Create: `templates/accounts.html`
- Create: `templates/import.html`
- Test: `tests/test_accounts.py`

**Step 1: Write failing tests**

```python
# tests/test_accounts.py
import pytest
from app import create_app
from database import init_db, get_session
from models import Account

@pytest.fixture
def app(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app({"TESTING": True, "DB_PATH": db_path})
    init_db(db_path)
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

def test_accounts_page(client):
    response = client.get("/accounts")
    assert response.status_code == 200
    assert b"Accounts" in response.data

def test_add_account(client, app):
    response = client.post("/accounts", data={
        "name": "Chase Checking",
        "account_type": "checking",
        "institution": "Chase"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Chase Checking" in response.data
```

Run: `pytest tests/test_accounts.py -v`
Expected: FAIL

**Step 2: Implement account routes and templates**

Add routes to `app.py` for:
- `GET /accounts` — list all accounts
- `POST /accounts` — create new account
- `GET /import` — import page showing watch folder status
- `POST /import/scan` — trigger watch folder scan

Create `templates/accounts.html` with:
- Table of existing accounts (name, type, institution, last import date)
- Form to add new account (name, type dropdown, institution)

Create `templates/import.html` with:
- Watch folder path display
- List of pending files found
- Import button
- Recent import history

**Step 3: Run tests to verify they pass**

Run: `pytest tests/test_accounts.py -v`
Expected: ALL PASS

---

### Task 5: Spending Breakdown Tab

**Files:**
- Modify: `app.py` — add spending routes
- Create: `templates/spending.html`
- Test: `tests/test_spending.py`

**Step 1: Write failing tests**

```python
# tests/test_spending.py
import pytest
from app import create_app
from database import init_db, get_session
from models import Account, Transaction

@pytest.fixture
def app(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app({"TESTING": True, "DB_PATH": db_path})
    init_db(db_path)
    # Seed test data
    session = get_session(db_path)
    account = Account(name="Chase", account_type="checking", institution="Chase")
    session.add(account)
    session.commit()
    txns = [
        Transaction(date="2026-01-15", amount=-45.50, category="Dining", description="Restaurant", account_id=account.id),
        Transaction(date="2026-01-10", amount=-123.45, category="Groceries", description="Grocery Store", account_id=account.id),
        Transaction(date="2026-01-05", amount=-60.00, category="Dining", description="Pizza Place", account_id=account.id),
        Transaction(date="2025-12-15", amount=-30.00, category="Dining", description="Cafe", account_id=account.id),
        Transaction(date="2025-12-10", amount=-100.00, category="Groceries", description="Grocery Store", account_id=account.id),
    ]
    session.add_all(txns)
    session.commit()
    session.close()
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

def test_spending_page_loads(client):
    response = client.get("/spending?month=2026-01")
    assert response.status_code == 200

def test_spending_api_returns_category_data(client):
    response = client.get("/api/spending?month=2026-01")
    assert response.status_code == 200
    data = response.get_json()
    assert "categories" in data
    assert "comparison" in data
    # Dining total: 45.50 + 60.00 = 105.50
    dining = next(c for c in data["categories"] if c["name"] == "Dining")
    assert dining["total"] == 105.50

def test_spending_comparison_vs_last_month(client):
    response = client.get("/api/spending?month=2026-01")
    data = response.get_json()
    # Jan dining: 105.50, Dec dining: 30.00 → change: +75.50
    dining_cmp = next(c for c in data["comparison"] if c["name"] == "Dining")
    assert dining_cmp["change"] == 75.50
```

Run: `pytest tests/test_spending.py -v`
Expected: FAIL

**Step 2: Implement spending routes**

Add to `app.py`:
- `GET /spending` — renders spending page with month selector
- `GET /api/spending?month=YYYY-MM` — JSON API returning:
  - `categories`: list of `{name, total}` for the month
  - `comparison`: list of `{name, current, previous, change}` vs prior month
  - `transactions`: list of transactions for the month

**Step 3: Implement spending template**

`templates/spending.html`:
- Month selector (dropdown or arrows)
- Pie/donut chart: spending by category (Chart.js)
- Bar chart: category comparison vs last month (current vs previous side by side)
- Highlight cards: "Dining: +$75.50 vs last month" with red/green indicators
- Transaction table below with sortable columns

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_spending.py -v`
Expected: ALL PASS

---

### Task 6: Investments Tab

**Files:**
- Modify: `app.py` — add investment routes
- Create: `templates/investments.html`
- Test: `tests/test_investments.py`

**Step 1: Write failing tests**

```python
# tests/test_investments.py
import pytest
from app import create_app
from database import init_db, get_session
from models import Account, Balance

@pytest.fixture
def app(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app({"TESTING": True, "DB_PATH": db_path})
    init_db(db_path)
    session = get_session(db_path)
    # Create investment accounts
    personal = Account(name="Fidelity Brokerage", account_type="brokerage", institution="Fidelity")
    rsu = Account(name="E*Trade RSU", account_type="rsu", institution="E*Trade")
    espp = Account(name="E*Trade ESPP", account_type="espp", institution="E*Trade")
    session.add_all([personal, rsu, espp])
    session.commit()
    # Add monthly balance snapshots
    for month, vals in [("2025-10", [40000, 15000, 5000]),
                         ("2025-11", [42000, 15500, 5200]),
                         ("2025-12", [41000, 16000, 5100]),
                         ("2026-01", [45000, 16500, 5500])]:
        for acct, val in zip([personal, rsu, espp], vals):
            session.add(Balance(month=month, account_id=acct.id, balance=val))
    session.commit()
    session.close()
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

def test_investments_page_loads(client):
    response = client.get("/investments")
    assert response.status_code == 200

def test_investments_api(client):
    response = client.get("/api/investments")
    data = response.get_json()
    assert "accounts" in data
    assert len(data["accounts"]) == 3
    # Total portfolio value for latest month
    assert data["total_current"] == 45000 + 16500 + 5500
```

Run: `pytest tests/test_investments.py -v`
Expected: FAIL

**Step 2: Implement investment routes and template**

Add to `app.py`:
- `GET /investments` — renders investments page
- `GET /api/investments` — JSON returning account balances over time

`templates/investments.html`:
- Line chart: total portfolio value over time
- Stacked area or grouped line chart: personal vs RSU vs ESPP
- Summary cards: current value, total gain/loss
- Table: each holding with latest balance and month-over-month change

**Step 3: Run tests**

Run: `pytest tests/test_investments.py -v`
Expected: ALL PASS

---

### Task 7: Fixed Expenses Tab

**Files:**
- Modify: `app.py` — add fixed expense routes
- Create: `templates/fixed.html`
- Test: `tests/test_fixed.py`

**Step 1: Write failing tests**

Test that the page loads and the API returns recurring expenses grouped (mortgage, utilities, subscriptions, etc.), plus loan balance tracking.

**Step 2: Implement**

Add to `app.py`:
- `GET /fixed` — renders fixed expenses page
- `GET /api/fixed?month=YYYY-MM` — JSON returning recurring bills and loan balances

`templates/fixed.html`:
- Summary card: total fixed monthly expenses
- Bar chart: fixed expenses by category
- Mortgage section: payment amount, remaining balance (from Balance snapshots), payoff progress bar
- Table of recurring transactions detected (same description + similar amount each month)

**Step 3: Run tests**

Run: `pytest tests/test_fixed.py -v`
Expected: ALL PASS

---

### Task 8: Overview / Net Worth Tab

**Files:**
- Modify: `app.py` — enhance index route
- Modify: `templates/index.html`
- Test: `tests/test_overview.py`

**Step 1: Write failing tests**

Test that the overview API returns:
- Net worth (sum of all account balances, latest month)
- Net worth trend over time
- Income summary for current month
- FSA/HSA balances
- Total savings

**Step 2: Implement**

Enhance `GET /` and add `GET /api/overview`:
- Returns: net_worth, net_worth_history, income_this_month, savings_total, fsa_balance, hsa_balance

`templates/index.html`:
- Top row: big number cards (Net Worth, Monthly Income, Total Savings, FSA, HSA)
- Line chart: net worth trend over time
- Income breakdown: salary vs interest vs other
- Quick links to other tabs

**Step 3: Run tests**

Run: `pytest tests/test_overview.py -v`
Expected: ALL PASS

---

### Task 9: Polish and Integration

**Files:**
- Modify: multiple templates for consistent styling
- Create: `templates/components/` — shared chart configs, table macros
- Test: `tests/test_integration.py`

**Step 1: Integration test**

Write a test that:
1. Creates accounts
2. Imports CSVs
3. Verifies spending API returns correct data
4. Verifies overview totals are correct

**Step 2: Add drag-and-drop to import page**

Add JavaScript to `templates/import.html`:
- Drag-and-drop zone for CSV files
- Uploads via `POST /import/upload`
- Shows results inline

**Step 3: Add quick-links page**

Create a simple template where user can save bookmark URLs to their bank export pages, stored in a JSON config file.

**Step 4: Final test run**

Run: `pytest tests/ -v`
Expected: ALL PASS

---

## Summary

| Task | What | Key files |
|------|------|-----------|
| 1 | Project scaffolding | `app.py`, `config.py`, `templates/base.html` |
| 2 | Database models | `models.py`, `database.py` |
| 3 | CSV import engine | `importer.py`, watch folder logic |
| 4 | Account management | `/accounts`, `/import` pages |
| 5 | Spending breakdown | `/spending` with charts + comparison |
| 6 | Investments | `/investments` with portfolio tracking |
| 7 | Fixed expenses | `/fixed` with mortgage + recurring |
| 8 | Overview / Net worth | `/` dashboard with net worth trend |
| 9 | Polish + integration | Drag-and-drop, quick links, styling |
