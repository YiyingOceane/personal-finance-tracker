"""Parse PDF bank/credit card statements into transactions."""

import re
from datetime import datetime

import pdfplumber

from categorizer import categorize


def _deduplicate_chars(text):
    """Fix doubled characters from PDF rendering (e.g. 'AACCCCOOUUNNTT' -> 'ACCOUNT')."""
    # Replace known doubled-char headers
    replacements = {
        "AACCCCOOUUNNTT AACCTTIIVVIITTYY": "ACCOUNT ACTIVITY",
        "AACCCCOOUUNNTT SSUUMMMMAARRYY": "ACCOUNT SUMMARY",
        "CCHHEECCKKIINNGG SSUUMMMMAARRYY": "CHECKING SUMMARY",
        "TTRRAANNSSAACCTTIIOONN DDEETTAAIILL": "TRANSACTION DETAIL",
        "YYeeaarr--ttoo--ddaattee ttoottaallss": "Year-to-date totals",
    }
    for doubled, clean in replacements.items():
        text = text.replace(doubled, clean)
    return text


def parse_pdf(filepath):
    """Detect PDF type and extract transactions + metadata."""
    with pdfplumber.open(filepath) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    full_text = _deduplicate_chars(full_text)

    if "ACCOUNT ACTIVITY" in full_text and ("PURCHASE" in full_text or "PAYMENTS" in full_text):
        return parse_chase_credit_card(full_text)
    elif "TRANSACTION DETAIL" in full_text and "CHECKING SUMMARY" in full_text:
        return parse_chase_checking(full_text)
    elif "CHECKING SUMMARY" in full_text:
        return parse_chase_checking_no_activity(full_text)
    else:
        return None


def _extract_statement_year(text):
    """Extract the statement year from common date patterns in the text."""
    # Look for patterns like "January 21, 2026throughFebruary 18, 2026" or "Opening/Closing Date 01/11/26 - 02/10/26"
    match = re.search(r"(\w+ \d{1,2}, (\d{4})).*?through", text)
    if match:
        return int(match.group(2))
    match = re.search(r"Opening/Closing Date \d{2}/\d{2}/(\d{2})", text)
    if match:
        return 2000 + int(match.group(1))
    # Fallback: look for any 4-digit year near "202"
    match = re.search(r"(202\d)", text)
    if match:
        return int(match.group(1))
    return datetime.now().year


def _extract_statement_period(text):
    """Extract statement start and end months."""
    # "January 21, 2026throughFebruary 18, 2026"
    match = re.search(r"(\w+ \d{1,2}, \d{4})\s*through\s*(\w+ \d{1,2}, \d{4})", text)
    if match:
        try:
            start = datetime.strptime(match.group(1), "%B %d, %Y")
            end = datetime.strptime(match.group(2), "%B %d, %Y")
            return start, end
        except ValueError:
            pass
    # "Opening/Closing Date 01/11/26 - 02/10/26"
    match = re.search(r"Opening/Closing Date (\d{2}/\d{2}/\d{2}) - (\d{2}/\d{2}/\d{2})", text)
    if match:
        try:
            start = datetime.strptime(match.group(1), "%m/%d/%y")
            end = datetime.strptime(match.group(2), "%m/%d/%y")
            return start, end
        except ValueError:
            pass
    return None, None


def parse_chase_credit_card(text):
    """Parse Chase credit card statement PDF."""
    year = _extract_statement_year(text)
    start_date, end_date = _extract_statement_period(text)

    # Extract account last 4 digits
    acct_match = re.search(r"Account Number:.*?(\d{4})\s*$", text, re.MULTILINE)
    last4 = acct_match.group(1) if acct_match else "Unknown"

    # Extract balance from ACCOUNT SUMMARY section
    bal_match = re.search(r"New Balance \$([\d,]+\.\d{2})", text)
    new_balance = float(bal_match.group(1).replace(",", "")) if bal_match else 0

    # Parse transactions from ACCOUNT ACTIVITY section
    # Pattern: MM/DD description amount
    transactions = []
    # Find the ACCOUNT ACTIVITY section
    activity_match = re.search(r"ACCOUNT ACTIVITY(.*?)(?:\d{4} Totals|Year-to-date|$)", text, re.DOTALL)
    if not activity_match:
        return {
            "type": "chase_credit_card", "last4": last4,
            "balance": new_balance, "transactions": [], "year": year,
        }

    activity_text = activity_match.group(1)
    # Match lines like: 01/09 SONGQIREN Plano TX 14.08
    # or: 01/13 LYFT *2 RIDES 09-14 SAN FRANCISCO CA -.79
    txn_pattern = re.compile(r"(\d{2}/\d{2})\s+(.+?)\s+(-?[\d,]+\.\d{2})$", re.MULTILINE)

    in_payments = False
    for match in txn_pattern.finditer(activity_text):
        date_str = match.group(1)
        description = match.group(2).strip()
        amount_str = match.group(3)

        # Check if we're in PAYMENTS section
        preceding = activity_text[:match.start()]
        if "PAYMENTS AND OTHER CREDITS" in preceding:
            after_purchase = preceding.rfind("PURCHASE")
            after_payments = preceding.rfind("PAYMENTS AND OTHER CREDITS")
            in_payments = after_payments > after_purchase if after_purchase > 0 else True

        month = int(date_str[:2])
        day = int(date_str[3:])

        # Determine year based on statement period
        if start_date and end_date:
            txn_year = end_date.year if month <= end_date.month else start_date.year
        else:
            txn_year = year

        try:
            date = datetime(txn_year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            continue

        amount = float(amount_str.replace(",", ""))
        # Credit card: purchases are positive in statement but are expenses (negative for us)
        # Payments/credits are negative in statement (positive for us, but we keep as-is)
        if not in_payments and amount > 0:
            amount = -amount  # Purchases become negative (expenses)

        # Simple category detection
        category = categorize(description)

        transactions.append({
            "date": date, "amount": amount,
            "description": description, "category": category,
        })

    return {
        "type": "chase_credit_card", "last4": last4,
        "balance": new_balance, "transactions": transactions, "year": year,
    }


def parse_chase_checking(text):
    """Parse Chase checking account statement PDF."""
    year = _extract_statement_year(text)
    start_date, end_date = _extract_statement_period(text)

    # Extract ending balance
    bal_match = re.search(r"Ending Balance\s+\$?([\d,]+\.\d{2})", text)
    ending_balance = float(bal_match.group(1).replace(",", "")) if bal_match else 0

    # Parse transactions from TRANSACTION DETAIL section
    # Pattern: MM/DD description amount balance
    transactions = []
    detail_match = re.search(r"TRANSACTION DETAIL(.*?)(?:Ending Balance|$)", text, re.DOTALL)
    if not detail_match:
        return {
            "type": "chase_checking", "balance": ending_balance,
            "transactions": [], "year": year,
        }

    detail_text = detail_match.group(1)
    # Match: 02/02 Zelle Payment To Yi Fan 27892233372 -44.80 30,066.59
    txn_pattern = re.compile(
        r"(\d{2}/\d{2})\s+(.+?)\s+(-?[\d,]+\.\d{2})\s+[\d,]+\.\d{2}$",
        re.MULTILINE,
    )

    for match in txn_pattern.finditer(detail_text):
        date_str = match.group(1)
        description = match.group(2).strip()
        amount_str = match.group(3)

        month = int(date_str[:2])
        day = int(date_str[3:])

        if start_date and end_date:
            txn_year = end_date.year if month <= end_date.month else start_date.year
        else:
            txn_year = year

        try:
            date = datetime(txn_year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            continue

        amount = float(amount_str.replace(",", ""))
        category = categorize(description)

        transactions.append({
            "date": date, "amount": amount,
            "description": description, "category": category,
        })

    return {
        "type": "chase_checking", "balance": ending_balance,
        "transactions": transactions, "year": year,
    }


def parse_chase_checking_no_activity(text):
    """Parse Chase checking statement with no transactions."""
    year = _extract_statement_year(text)
    bal_match = re.search(r"Ending Balance\s+\$?([\d,]+\.\d{2})", text)
    ending_balance = float(bal_match.group(1).replace(",", "")) if bal_match else 0

    return {
        "type": "chase_checking", "balance": ending_balance,
        "transactions": [], "year": year,
    }


