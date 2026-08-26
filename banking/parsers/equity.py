import re
from datetime import datetime
from decimal import Decimal


def clean_amount(value):
    if value in [None, ""]:
        return Decimal("0")

    value = (
        str(value)
        .replace(",", "")
        .replace("KES", "")
        .strip()
    )

    try:
        return Decimal(value)
    except Exception:
        return Decimal("0")


def clean_date(value):
    if not value:
        return None

    for fmt in [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
    ]:
        try:
            return datetime.strptime(
                str(value).strip(),
                fmt,
            ).date()
        except Exception:
            pass

    return None


def parse_equity_transactions(text):
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    # Equity transaction references seen in the real statements:
    # S27609180
    # 542190256
    reference_pattern = re.compile(
        r"^(?:S\d+|\d{7,})$",
        re.IGNORECASE,
    )

    date_pattern = re.compile(
        r"^\d{2}/\d{2}/\d{4}$"
    )

    amount_pattern = re.compile(
        r"^-?\d{1,3}(?:,\d{3})*\.\d{2}$"
    )

    house_pattern = re.compile(
        r"#\s*0*(\d+)"
    )

    ignored_headers = {
        "TRANSACTIONS",
        "TRANSACTION DETAILS",
        "PAYMENT REFERENCE",
        "VALUE DATE",
        "CREDIT (MONEY",
        "IN)",
        "DEBIT (MONEY OUT)",
        "BALANCE",
        "TOTAL",
    }

    raw_rows = []

    first_ref_index = None

    for index, line in enumerate(lines):
        if reference_pattern.match(line):
            if (
                index + 3 < len(lines)
                and date_pattern.match(lines[index + 1])
                and amount_pattern.match(lines[index + 2])
                and amount_pattern.match(lines[index + 3])
            ):
                first_ref_index = index
                break

    if first_ref_index is None:
        return []

    # Start description immediately after the last Balance header.
    cursor = 0

    for index in range(first_ref_index):
        if lines[index].upper() == "BALANCE":
            cursor = index + 1

    i = first_ref_index

    while i < len(lines):
        reference_line = lines[i]

        if not reference_pattern.match(reference_line):
            i += 1
            continue

        if i + 3 >= len(lines):
            break

        date_line = lines[i + 1]
        amount_line = lines[i + 2]
        balance_line = lines[i + 3]

        if not (
            date_pattern.match(date_line)
            and amount_pattern.match(amount_line)
            and amount_pattern.match(balance_line)
        ):
            i += 1
            continue

        description_lines = [
            line
            for line in lines[cursor:i]
            if line.upper() not in ignored_headers
        ]

        description = " ".join(
            description_lines
        ).strip()

        raw_rows.append(
            {
                "date": clean_date(date_line),
                "description": description,
                "bank_reference": reference_line.upper(),
                "amount": clean_amount(amount_line),
                "balance": clean_amount(balance_line),
            }
        )

        cursor = i + 4
        i = i + 4

    transactions = []

    previous_balance = None

    for row in raw_rows:
        description = row["description"]
        upper_description = description.upper()
        amount = row["amount"]
        balance = row["balance"]

        money_in = Decimal("0")
        money_out = Decimal("0")

        # Best method: running-balance movement.
        if previous_balance is not None:
            difference = balance - previous_balance

            if difference > 0:
                money_in = amount
            elif difference < 0:
                money_out = amount
            else:
                # No balance movement: fall back to description.
                if any(
                    marker in upper_description
                    for marker in [
                        "CHARGE",
                        "REVDN",
                        "REVERSAL",
                        "WITHDRAW",
                        "DEBIT",
                    ]
                ):
                    money_out = amount
                else:
                    money_in = amount

        else:
            # First parsed row has no previous running balance
            # available inside this parser.
            if any(
                marker in upper_description
                for marker in [
                    "CHARGE",
                    "REVDN",
                    "REVERSAL",
                    "WITHDRAW",
                    "DEBIT",
                ]
            ):
                money_out = amount
            else:
                money_in = amount

        house_match = house_pattern.search(
            description
        )

        reference = row["bank_reference"]

        if house_match:
            reference = (
                f"{reference} | "
                f"HOUSE {int(house_match.group(1))}"
            )

        transactions.append(
            {
                "date": row["date"],
                "description": (
                    f"[EQUITY] {description}"
                ),
                "reference": reference[:150],
                "money_in": money_in,
                "money_out": money_out,
                "balance": balance,
            }
        )

        previous_balance = balance

    return transactions
