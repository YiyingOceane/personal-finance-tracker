"""Parse Citi PDF statements: credit cards (Costco Visa, Double Cash) and savings."""

import re
from datetime import datetime

import pdfplumber

from categorizer import categorize
from parse_utils import clean_amount_unsigned


def is_citi_pdf(filepath):
    """Check if a PDF is a Citi statement."""
    try:
        with pdfplumber.open(filepath) as pdf:
            text = pdf.pages[0].extract_text() or ""
        return ("Citi" in text or "citicards" in text.lower()) and (
            "STATEMENT" in text or "Account Statement" in text
        )
    except (FileNotFoundError, PermissionError):
        raise
    except Exception:
        return False


def parse_citi_pdf(filepath):
    """Parse a Citi PDF statement. Returns account info and transactions."""
    with pdfplumber.open(filepath) as pdf:
        pages_text = [page.extract_text() or "" for page in pdf.pages]
    full_text = "\n".join(pages_text)
    first_page = pages_text[0]

    if "Citi Priority" in first_page or "Accelerate Savings" in first_page:
        return _parse_savings(pages_text, full_text)
    else:
        return _parse_credit_card(pages_text, full_text)


def _parse_credit_card(pages_text, full_text):
    """Parse a Citi credit card statement."""
    first_page = pages_text[0]

    # Card name
    card_name = "Citi Card"
    if "Costco Anywhere" in full_text:
        card_name = "Citi Costco Visa"
    elif "Double Cash" in full_text:
        card_name = "Citi Double Cash"
    elif "Custom Cash" in full_text:
        card_name = "Citi Custom Cash"

    # Account number (last 4)
    acct_match = re.search(r"ending\s*in[:\s]*(\d{4})", full_text)
    last4 = acct_match.group(1) if acct_match else "0000"

    # Balance
    bal_match = re.search(r"New balance(?:\s+as of \d{2}/\d{2}/\d{2})?:\s*\$?([\d,]+\.\d{2})", first_page)
    balance = clean_amount_unsigned(bal_match.group(1)) if bal_match else 0

    # Statement date
    stmt_match = re.search(r"as of (\d{2}/\d{2}/\d{2})", first_page)
    if stmt_match:
        try:
            stmt_date = datetime.strptime(stmt_match.group(1), "%m/%d/%y")
            month = stmt_date.strftime("%Y-%m")
            year = stmt_date.year
        except ValueError:
            month = datetime.now().strftime("%Y-%m")
            year = datetime.now().year
    else:
        month = datetime.now().strftime("%Y-%m")
        year = datetime.now().year

    # Parse transactions
    transactions = []
    for page_text in pages_text:
        transactions.extend(_parse_cc_transactions(page_text, year))

    return {
        "type": "citi_credit_card",
        "card_name": card_name,
        "last4": last4,
        "balance": -balance,
        "month": month,
        "transactions": transactions,
    }


def _parse_cc_transactions(text, year):
    """Extract transactions from a Citi credit card page.

    Handles multi-column PDF merging: the right column (rewards) appends
    junk text after the real transaction amount. We take the FIRST dollar
    amount following the date+description as the transaction amount.
    """
    transactions = []
    lines = text.split("\n")

    for i, line in enumerate(lines):
        line = line.strip()

        # Must start with MM/DD
        if not re.match(r"\d{2}/\d{2}\s", line):
            continue

        # Extract dates
        date_match = re.match(r"(\d{2}/\d{2})\s+(?:(\d{2}/\d{2})\s+)?", line)
        if not date_match:
            continue

        rest = line[date_match.end():]
        post_date = date_match.group(2) or date_match.group(1)

        # Skip non-transaction lines
        if any(skip in rest for skip in [
            "Days in billing", "Annual percentage", "Balance subject",
            "Standard Purch", "Standard Adv",
        ]):
            continue

        # Find the FIRST dollar amount in the rest of the line
        amt_match = re.search(r"(-?\$?[\d,]+\.\d{2})", rest)
        if not amt_match:
            # Some transactions (TikTok) have the amount on the next line
            # via "Digital account number ending in XXXX -$7.33"
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if "Digital account number" in next_line:
                    next_amt = re.search(r"(-?\$?[\d,]+\.\d{2})", next_line)
                    if next_amt:
                        amt_match = next_amt
                        rest = rest  # description stays from current line
            if not amt_match:
                continue

        description = rest[:amt_match.start()].strip()
        amount = clean_amount_unsigned(amt_match.group(1))

        # Check if the original string had a negative sign
        raw_amt = amt_match.group(1)
        is_negative_on_stmt = raw_amt.startswith("-")

        # Skip autopay / payment lines — these are transfers
        if "AUTOPAY" in description or "AUTO-PMT" in description:
            continue

        # Determine the transaction amount for our system:
        # Negative on statement = credit/refund → positive for us
        # Positive on statement = purchase → negative for us (expense)
        if is_negative_on_stmt:
            amount = abs(amount)  # refund = positive
        else:
            amount = -amount  # purchase = negative (expense)

        # Build full date
        m_num, d_num = int(post_date[:2]), int(post_date[3:])
        try:
            full_date = datetime(year, m_num, d_num).strftime("%Y-%m-%d")
        except ValueError:
            try:
                full_date = datetime(year - 1, m_num, d_num).strftime("%Y-%m-%d")
            except ValueError:
                continue

        # Clean description: remove location state codes at end, trailing junk
        description = re.sub(r"\s+\d{10,}.*", "", description)  # remove long numbers (card refs)

        category = categorize(description)

        transactions.append({
            "date": full_date,
            "description": description,
            "amount": amount,
            "category": category,
        })

    return transactions


def _parse_savings(pages_text, full_text):
    """Parse a Citi savings/banking statement."""
    first_page = pages_text[0]

    # Account number
    acct_match = re.search(r"(?:Citi Priority Account|Account)\s+(\d{10,})", full_text)
    acct_num = acct_match.group(1) if acct_match else ""

    # Statement period
    period_match = re.search(r"(\w+ \d{1,2})\s*-\s*(\w+ \d{1,2},?\s*\d{4})", first_page)
    if period_match:
        try:
            end_str = period_match.group(2).replace(",", "")
            end_date = datetime.strptime(end_str.strip(), "%B %d %Y")
            month = end_date.strftime("%Y-%m")
            year = end_date.year
        except ValueError:
            month = datetime.now().strftime("%Y-%m")
            year = datetime.now().year
    else:
        month = datetime.now().strftime("%Y-%m")
        year = datetime.now().year

    # Balances from summary
    this_period_match = re.search(
        r"Insured Money Market Accounts\s+([\d,.]+)\s+([\d,.]+)", full_text
    )
    if not this_period_match:
        this_period_match = re.search(
            r"Citi Priority Relationship Total\s+\$?([\d,.]+)\s+\$?([\d,.]+)", full_text
        )
    opening_balance = clean_amount_unsigned(this_period_match.group(1)) if this_period_match else 0
    closing_balance = clean_amount_unsigned(this_period_match.group(2)) if this_period_match else 0

    # Interest earned
    interest_match = re.search(
        r"Citi Priority Relationship Total\s+\$?[\d,.]+\s+\$?[\d,.]+\s+.*?"
        r"Citi Priority Relationship Total\s+\$?([\d,.]+)\s+\$?([\d,.]+)",
        full_text, re.DOTALL,
    )
    interest_this_period = clean_amount_unsigned(interest_match.group(1)) if interest_match else 0
    interest_ytd = clean_amount_unsigned(interest_match.group(2)) if interest_match else 0

    # APY
    apy_match = re.search(r"Annual Percentage Yield Earned\s+([\d.]+)%", full_text)
    apy = float(apy_match.group(1)) if apy_match else 0

    # Parse transactions
    transactions = _parse_savings_transactions(pages_text, year)

    return {
        "type": "citi_savings",
        "account_number": acct_num,
        "account_name": "Citi Accelerate Savings",
        "opening_balance": opening_balance,
        "closing_balance": closing_balance,
        "balance": closing_balance,
        "interest_this_period": interest_this_period,
        "interest_ytd": interest_ytd,
        "apy": apy,
        "month": month,
        "transactions": transactions,
    }


def _parse_savings_transactions(pages_text, year):
    """Extract transactions from Citi savings statement."""
    transactions = []

    for page_text in pages_text:
        lines = page_text.split("\n")
        for line in lines:
            line = line.strip()

            # Pattern: MM/DD/YY Description Numbers...
            match = re.match(r"(\d{2}/\d{2}/\d{2})\s+(.+)", line)
            if not match:
                continue

            date_str = match.group(1)
            rest = match.group(2).strip()

            # Skip balance lines
            if "Opening Balance" in rest or "Closing Balance" in rest:
                continue

            try:
                txn_date = datetime.strptime(date_str, "%m/%d/%y").strftime("%Y-%m-%d")
            except ValueError:
                continue

            # Extract all numbers from the rest of the line
            # Format: Description [amount_subtracted] [amount_added] balance
            # We need to find the amounts. The last number is always the running balance.
            nums = re.findall(r"[\d,]+\.\d{2}", rest)
            if not nums:
                continue

            # Remove the numbers from the description
            desc_part = re.sub(r"\s*[\d,]+\.\d{2}.*", "", rest).strip()

            # Determine if it's a credit or debit from the description
            is_credit = any(kw in desc_part for kw in [
                "Credit", "Interest paid", "Deposit",
            ])
            is_debit = any(kw in desc_part for kw in [
                "Electronic Debit", "Debit", "Withdrawal",
            ])

            # The first number is the transaction amount
            amount_val = clean_amount_unsigned(nums[0])

            if is_debit:
                amount = -amount_val
            elif is_credit:
                amount = amount_val
            else:
                # Ambiguous — if multiple numbers, first is usually the txn amount
                # Positive by default for unknown
                amount = amount_val

            category = categorize(desc_part)

            if "Interest paid" in desc_part:
                category = "Interest"
            elif "FID BKG SVC" in desc_part or "MONEYLINE" in desc_part:
                category = "Transfer"
            elif "Instant Payment" in desc_part or "Payment Credit" in desc_part:
                category = "Transfer"

            transactions.append({
                "date": txn_date,
                "description": desc_part,
                "amount": amount,
                "category": category,
            })

    return transactions


