import re
from decimal import Decimal
from difflib import SequenceMatcher

from rentals.models import House, Rent, Tenant


APARTMENT_PREFIXES = {
    "B": "BLUEVALLEY",
    "E": "EASTWARD",
    "G": "GULF",
    "M": "MUTHAIGA",
    "O": "OASIS BUSINESS CENTER",
}


def normalize_phone(value):
    digits = re.sub(r"\D", "", str(value or ""))

    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    elif len(digits) == 9:
        digits = "254" + digits

    return digits


def normalize_text(value):
    text = str(value or "").upper()
    text = re.sub(r"[^A-Z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def house_number_only(value):
    match = re.search(r"\d+", str(value or ""))

    if not match:
        return ""

    return str(int(match.group()))


def extract_phone_numbers(text):
    return set(re.findall(r"\b254\d{9}\b", text))


def extract_house_number(text):
    cleaned = re.sub(r"\b254\d{9}\b", " ", text)
    cleaned = cleaned.replace("501273", " ")

    explicit_house = re.search(
        r"\bHOUSE\s*0*(\d{1,3})\b",
        cleaned,
    )

    if explicit_house:
        return str(int(explicit_house.group(1)))

    prefixed_house = re.search(
        r"\b([BEGMO])\s*0*(\d{1,3})\b",
        cleaned,
    )

    if prefixed_house:
        return str(int(prefixed_house.group(2)))

    numbers = re.findall(r"\b0*(\d{1,3})\b", cleaned)

    if numbers:
        return str(int(numbers[-1]))

    return None


def extract_apartment_prefix(text):
    match = re.search(
        r"\b([BEGMO])\s*0*\d{1,3}\b",
        text,
    )

    return match.group(1) if match else None


def exact_name_match(tenant_name, text):
    name = normalize_text(tenant_name)

    if not name:
        return False

    pattern = rf"(?<![A-Z0-9]){re.escape(name)}(?![A-Z0-9])"
    return re.search(pattern, text) is not None


def fuzzy_name_score(tenant_name, text):
    name = normalize_text(tenant_name)

    if not name or len(name) < 4:
        return 0

    best_ratio = 0

    for word in text.split():
        if len(word) < 4:
            continue

        ratio = SequenceMatcher(None, name, word).ratio()
        best_ratio = max(best_ratio, ratio)

    if best_ratio >= 0.93:
        return 25

    if best_ratio >= 0.86:
        return 10

    return 0


def tenant_for_house(house):
    """
    Prefer House.tenant. Fall back to the latest rent record.
    """
    if house.tenant_id:
        return house.tenant

    latest_rent = (
        Rent.objects.filter(house=house)
        .select_related("tenant")
        .order_by("-billing_month", "-id")
        .first()
    )

    return latest_rent.tenant if latest_rent else None


def score_house_candidate(transaction, house, tenant, text):
    score = 0
    reasons = []

    statement_house = extract_house_number(text)
    database_house = house_number_only(house.house_number)

    # House number is the strongest signal.
    if statement_house and database_house == statement_house:
        score += 100
        reasons.append("house number")

    prefix = extract_apartment_prefix(text)

    if prefix and house.apartment:
        expected_name = APARTMENT_PREFIXES.get(prefix, "")
        actual_name = normalize_text(house.apartment.name)

        if expected_name == actual_name:
            score += 40
            reasons.append("apartment")
        else:
            score -= 100
            reasons.append("apartment conflict")

    if tenant:
        if exact_name_match(tenant.name, text):
            score += 60
            reasons.append("tenant name")
        else:
            fuzzy_score = fuzzy_name_score(tenant.name, text)

            if fuzzy_score:
                score += fuzzy_score
                reasons.append("similar tenant name")

        phones = extract_phone_numbers(text)
        tenant_phone = normalize_phone(tenant.phone)

        if tenant_phone and tenant_phone in phones:
            score += 35
            reasons.append("phone")

    if transaction.money_in and house.rent_amount:
        payment_amount = Decimal(transaction.money_in)
        rent_amount = Decimal(house.rent_amount)

        if payment_amount == rent_amount:
            score += 25
            reasons.append("exact rent amount")
        elif Decimal("0") < payment_amount < rent_amount:
            score += 10
            reasons.append("partial rent amount")
        elif payment_amount > rent_amount:
            score += 5
            reasons.append("overpayment")

    return score, reasons


def match_by_house(transaction, text):
    statement_house = extract_house_number(text)

    if not statement_house:
        return None

    houses = (
        House.objects.select_related(
            "tenant",
            "apartment",
        )
        .filter(occupied=True)
    )

    candidates = []

    for house in houses:
        if house_number_only(house.house_number) != statement_house:
            continue

        tenant = tenant_for_house(house)

        score, reasons = score_house_candidate(
            transaction,
            house,
            tenant,
            text,
        )

        candidates.append(
            {
                "house": house,
                "tenant": tenant,
                "score": score,
                "reasons": reasons,
            }
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    best = candidates[0]
    second_score = (
        candidates[1]["score"]
        if len(candidates) > 1
        else 0
    )

    gap = best["score"] - second_score

    # A valid house alone can be useful, but duplicate house numbers
    # require enough supporting evidence.
    if best["score"] < 100:
        return None

    if len(candidates) > 1 and gap < 20:
        return {
            "ambiguous": True,
            "best_score": best["score"],
            "gap": gap,
        }

    return {
        "ambiguous": False,
        **best,
    }


def match_without_house(transaction, text):
    results = []
    phones = extract_phone_numbers(text)

    for tenant in Tenant.objects.exclude(name=""):
        score = 0
        reasons = []

        tenant_phone = normalize_phone(tenant.phone)

        if tenant_phone and tenant_phone in phones:
            score += 70
            reasons.append("phone")

        if exact_name_match(tenant.name, text):
            score += 50
            reasons.append("tenant name")
        else:
            fuzzy_score = fuzzy_name_score(tenant.name, text)

            if fuzzy_score:
                score += fuzzy_score
                reasons.append("similar tenant name")

        if score <= 0:
            continue

        house = (
            House.objects.filter(
                tenant=tenant,
                occupied=True,
            )
            .select_related("apartment")
            .first()
        )

        results.append(
            {
                "tenant": tenant,
                "house": house,
                "score": score,
                "reasons": reasons,
            }
        )

    if not results:
        return None

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    best = results[0]
    second_score = results[1]["score"] if len(results) > 1 else 0
    gap = best["score"] - second_score

    if best["score"] < 70 or gap < 20:
        return {
            "ambiguous": True,
            "best_score": best["score"],
            "gap": gap,
        }

    return {
        "ambiguous": False,
        **best,
    }


def auto_match(transaction):
    text = normalize_text(transaction.description)

    transaction.matched_tenant = None
    transaction.matched_house = None
    transaction.auto_matched = False
    transaction.confidence = 0

    if (
        "ACCOUNT STATEMENT CHARGE" in text
        or "EXCISE DUTY" in text
    ):
        transaction.transaction_type = "money_out"
        transaction.suggested_category = "expense"
        transaction.match_notes = "Bank charge or excise duty"
        transaction.save()
        return transaction

    if transaction.money_in and transaction.money_in > 0:
        transaction.transaction_type = "money_in"
        transaction.suggested_category = "rent"
    elif transaction.money_out and transaction.money_out > 0:
        transaction.transaction_type = "money_out"
        transaction.suggested_category = "expense"
    else:
        transaction.transaction_type = "unknown"
        transaction.suggested_category = "unknown"

    # First priority: house number.
    result = match_by_house(transaction, text)

    # Only use tenant/phone matching if no house match is available.
    if result is None:
        result = match_without_house(transaction, text)

    if result is None:
        transaction.match_notes = "No suitable tenant or house match"
        transaction.save()
        return transaction

    if result.get("ambiguous"):
        transaction.match_notes = (
            "Pending review: ambiguous match. "
            f"Best score {result['best_score']}, "
            f"gap {result['gap']}."
        )
        transaction.save()
        return transaction

    tenant = result.get("tenant")
    house = result.get("house")
    score = result.get("score", 0)
    reasons = result.get("reasons", [])

    if not tenant or not house:
        transaction.match_notes = (
            "Pending review: house or tenant is missing."
        )
        transaction.save()
        return transaction

    confidence = min(score, 100)

    transaction.matched_tenant = tenant
    transaction.matched_house = house
    transaction.confidence = confidence
    transaction.auto_matched = confidence >= 95
    transaction.match_notes = (
        f"Matched using {', '.join(reasons)}. "
        f"Score: {score}."
    )
    transaction.save()

    return transaction