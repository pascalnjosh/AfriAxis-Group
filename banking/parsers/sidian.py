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
        .replace("-", "")
        .strip()
    )

    try:
        return Decimal(value)
    except Exception:
        return Decimal("0")


def clean_date(value):
    if value in [None, ""]:
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


def normalize_lines(text):
    raw = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    normalized = []
    i = 0

    while i < len(raw):
        if (
            i + 2 < len(raw)
            and re.match(r"^\d{1,2}-$", raw[i])
            and re.match(r"^\d{1,2}-$", raw[i + 1])
            and re.match(r"^\d{4}$", raw[i + 2])
        ):
            normalized.append(
                f"{raw[i][:-1]}-"
                f"{raw[i + 1][:-1]}-"
                f"{raw[i + 2]}"
            )
            i += 3
            continue

        normalized.append(raw[i])
        i += 1

    return normalized


def extract_sidian_house(description):
    if not description:
        return None

    text = str(description).upper()

    patterns = [
        r"\bRM\s*0*(\d{1,3})\b",
        r"\bROOM\s*0*(\d{1,3})\b",
        r"\bHOUSE\s*0*(\d{1,3})\b",
        r"\bUNIT\s*0*(\d{1,3})\b",
        r"\bB\s*0*(\d{1,3})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            return int(match.group(1))

    # Standard Sidian:
    # phone + house + tenant + paybill
    match = re.search(
        r"\b254\d{9}\s+0*(\d{1,3})\s+[A-Z]",
        text,
    )

    if match:
        number = int(match.group(1))

        # Prevent paybill numbers such as 501273
        # being mistaken for houses.
        if 1 <= number <= 999:
            return number

    return None


def extract_sidian_reference(description):
    if not description:
        return ""

    match = re.search(
        r"\bMPESA\s+TO\s+ACCT\s+([A-Z0-9]+)",
        str(description),
        re.IGNORECASE,
    )

    return match.group(1).upper() if match else ""


def parse_sidian_transactions(text):
    lines = normalize_lines(text)

    date_pattern = re.compile(
        r"^(?:\d{1,2}/\d{2}/\d{4}|\d{1,2}-\d{2}-\d{4})$"
    )

    amount_pattern = re.compile(
        r"^\d{1,3}(?:,\d{3})*\.\d{2}$"
    )

    raw_rows = []
    i = 0

    while i < len(lines):
        if not date_pattern.match(lines[i]):
            i += 1
            continue

        transaction_date = clean_date(lines[i])
        details = []
        j = i + 1

        while (
            j < len(lines)
            and not date_pattern.match(lines[j])
        ):
            details.append(lines[j])
            j += 1

        description_parts = [
            value
            for value in details
            if not amount_pattern.match(value)
            and value != "-"
        ]

        description = " ".join(description_parts).strip()
        upper_desc = description.upper()

        amounts = [
            value
            for value in details
            if amount_pattern.match(value)
        ]

        if "OPENING BALANCE" in upper_desc:
            if amounts:
                raw_rows.append({
                    "opening_balance": clean_amount(amounts[-1])
                })

            i = j
            continue

        if "CLOSING BALANCE" in upper_desc:
            i = j
            continue

        if len(amounts) < 2:
            i = j
            continue

        raw_rows.append({
            "date": transaction_date,
            "description": description,
            "amount": clean_amount(amounts[-2]),
            "balance": clean_amount(amounts[-1]),
        })

        i = j

    transactions = []
    previous_balance = None

    for row in raw_rows:
        if "opening_balance" in row:
            previous_balance = row["opening_balance"]
            continue

        amount = row["amount"]
        balance = row["balance"]
        description = row["description"]
        upper_desc = description.upper()

        money_in = Decimal("0")
        money_out = Decimal("0")

        if previous_balance is not None:
            movement = balance - previous_balance

            if movement > 0:
                money_in = amount

            elif movement < 0:
                money_out = amount

        else:
            # Fallback only when opening balance is unavailable.
            outgoing_markers = [
                "EXCISE DUTY",
                "CHARGE",
                "WITHDRAWAL",
                "MOBILE TRANSACTION",
                "PURCHASES",
            ]

            if any(
                marker in upper_desc
                for marker in outgoing_markers
            ):
                money_out = amount
            else:
                money_in = amount

        house_number = extract_sidian_house(
            description
        )

        reference = extract_sidian_reference(
            description
        )

        if house_number:
            reference = (
                f"{reference} | HOUSE {house_number}"
                if reference
                else f"HOUSE {house_number}"
            )

        transactions.append({
            "date": row["date"],
            "description": f"[SIDIAN] {description}",
            "reference": reference[:150],
            "money_in": money_in,
            "money_out": money_out,
            "balance": balance,
        })

        previous_balance = balance

    return transactions
