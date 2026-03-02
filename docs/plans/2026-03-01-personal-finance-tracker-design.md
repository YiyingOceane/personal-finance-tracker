# Personal Finance Tracker — Design

## Problem
Too many accounts across too many places (credit cards, banks, brokerage, FSA/HSA, mortgage). No single view of full financial picture since Mint shut down.

## Goals
- All data stays local (privacy-first)
- Single dashboard for complete financial overview
- Minimize friction of getting data in (watch folder auto-import)
- Start with CSV import, optionally add SimpleFIN/Teller later

## Architecture
- **Backend:** Python + Flask
- **Database:** SQLite (single file, easy to back up)
- **Frontend:** Jinja templates + Chart.js + htmx (snappy tab switching)
- **Import:** Watch folder with auto-detection + drag-and-drop fallback

## Dashboard Tabs

### Tab 1: Spending Breakdown
- Monthly spending by category (bar/pie chart)
- Month-over-month comparison highlighting changes ("+$200 on dining vs last month")
- Transaction table filterable by account, category, date

### Tab 2: Investments
- Stock portfolio value over time (line chart)
- Sections: personal investments, company RSU, ESPP
- Gain/loss summary per holding

### Tab 3: Fixed Expenses
- Housing/mortgage payment tracking
- Other recurring bills
- Remaining loan balance

### Tab 4: Overview / Net Worth
- Total savings across all accounts
- Income summary (salary + interest + other)
- FSA/HSA balances
- Net worth trend over time

## Data Model

### Accounts
- name, type (checking, credit card, brokerage, FSA, mortgage...), institution

### Transactions
- date, amount, category, description, account

### Balances
- Monthly snapshots per account (for stocks, FSA, mortgage balance)

### CSV Profiles
- Saved column mappings per institution

## Import Flow
1. App scans watch folder on startup
2. Auto-detects file format by column headers
3. Parses, deduplicates, categorizes
4. Moves processed files to `processed/` subfolder
5. Shows import summary on dashboard

## Tech Decisions
- SQLite chosen for simplicity and portability (one file = entire financial history)
- Flask over FastAPI for simpler templating (no separate frontend build)
- htmx for SPA-like tab switching without React complexity
- Chart.js for lightweight, well-documented charting
- Watch folder pattern to minimize import friction

## Future Enhancements
- SimpleFIN ($15/year) or Teller (free tier) for automated bank sync
- Auto-categorization with rules engine
- Export/reporting features
