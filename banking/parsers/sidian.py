import re
from datetime import datetime
from decimal import Decimal


def clean_amount(value):
    if value in [None, ""]:
        return Decimal("0")

    value = str(value).replace(",", "").replace("KES", "").replace("-", "").strip()

    try:
        return Decimal(value)
    except Exception:
        return Decimal("0")


def clean_date(value):
    if value in [None, ""]:
        return None

    for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except Exception:
            pass

    return None


def parse_sidian_transactions(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    date_pattern = re.compile(r"^\d{1,2}/\d{2}/\d{4}$")
    amount_pattern = re.compile(r"^\d{1,3}(?:,\d{3})*\.\d{2}$")

    transactions = []
    i = 0

    while i < len(lines):
        if not date_pattern.match(lines[i]):
            i += 1
            continue

        transaction_date = clean_date(lines[i])
        details = []
        j = i + 1

        while j < len(lines) and not date_pattern.match(lines[j]):
            details.append(lines[j])
            j += 1

        description_parts = [x for x in details if not amount_pattern.match(x)]
        description = " ".join(description_parts)

        upper_desc = description.upper()

        if "OPENING BALANCE" in upper_desc or "CLOSING BALANCE" in upper_desc:
            i = j
            continue

        amounts = [x for x in details if amount_pattern.match(x)]

        if len(amounts) >= 2:
            amount = clean_amount(amounts[-2])
            balance = clean_amount(amounts[-1])
        elif len(amounts) == 1:
            amount = clean_amount(amounts[-1])
            balance = Decimal("0")
        else:
            i = j
            continue

        is_money_out = (
            "EXCISE DUTY" in upper_desc
            or "ACCOUNT STATEMENT CHARGE" in upper_desc
            or "CHARGE" in upper_desc
            or "DUTY" in upper_desc
        )

        transactions.append({
            "date": transaction_date,
            "description": f"[SIDIAN] {description}",
            "reference": "",
            "money_in": Decimal("0") if is_money_out else amount,
            "money_out": amount if is_money_out else Decimal("0"),
            "balance": balance,
        })

        i = j

    return transactions