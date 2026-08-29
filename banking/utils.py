from decimal import Decimal

from .models import BankTransaction
from .pdf_utils import extract_pdf_text
from .parsers.sidian import parse_sidian_transactions
from .parsers.equity import parse_equity_transactions


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


def create_transaction(statement_upload, data):
    account = statement_upload.bank_account

    category_map = {
        "RENT": "rent",
        "WATER": "water",
        "WIFI": "wifi",
    }

    transaction_date = data["date"]
    description = data["description"]
    reference = data.get("reference", "")
    money_in = clean_amount(data.get("money_in", 0))
    money_out = clean_amount(data.get("money_out", 0))
    balance = clean_amount(data.get("balance", 0))

    upper_description = str(description).upper()

    bank_charge_markers = [
        "EXCISE DUTY",
        "ACCOUNT STATEMENT CHARGE",
        "TRANSACTION + SMS CHARGE",
        "SMS CHARGE",
        "BANK CHARGE",
        "TRANSFER CHARGE",
        "LEDGER FEE",
        "SERVICE CHARGE",
        "COMMISSION",
    ]

    if money_out > Decimal("0"):
        if any(
            marker in upper_description
            for marker in bank_charge_markers
        ):
            suggested_category = "bank_charge"
        else:
            suggested_category = "unknown"

    elif money_in > Decimal("0"):
        suggested_category = category_map.get(
            account.purpose,
            "unknown",
        )

    else:
        suggested_category = "unknown"

    transaction, created = BankTransaction.objects.get_or_create(
        bank_account=account,
        transaction_date=transaction_date,
        reference=reference,
        money_in=money_in,
        money_out=money_out,
        defaults={
            "statement_upload": statement_upload,
            "description": description,
            "balance": balance,
            "suggested_category": suggested_category,
            "match_status": "pending",
        },
    )

    if created:
        match_house_for_transaction(transaction)
        transaction.refresh_from_db()
        match_tenant_for_transaction(transaction)

    return transaction

def process_pdf_statement(statement_upload):
    text = extract_pdf_text(
        statement_upload.file.path
    )

    validate_statement_account(
        statement_upload,
        text,
    )

    bank_name = (
        statement_upload
        .bank_account
        .bank_name
        .upper()
    )

    if "SIDIAN" in bank_name:
        transactions = parse_sidian_transactions(text)

        for item in transactions:
            create_transaction(
                statement_upload,
                item,
            )

        statement_upload.processed = True
        statement_upload.save(
            update_fields=["processed"]
        )

        return len(transactions)

    if "EQUITY" in bank_name:
        transactions = parse_equity_transactions(text)

        for item in transactions:
            create_transaction(
                statement_upload,
                item,
            )

        statement_upload.processed = True
        statement_upload.save(
            update_fields=["processed"]
        )

        return len(transactions)

    raise ValueError(
        "PDF parser for this bank is not ready yet."
    )


def process_bank_statement(statement_upload):
    filename = statement_upload.file.name.lower()

    if filename.endswith(".pdf"):
        return process_pdf_statement(
            statement_upload
        )

    raise ValueError(
        "Only PDF processing is active right now."
    )


def match_erp_bank_transaction(bank_transaction):
    from datetime import timedelta

    from purchasing.models import SupplierPayment
    from sales.models import SalesReceipt

    transaction = bank_transaction

    transaction.matched_sales_receipt = None
    transaction.matched_supplier_payment = None

    # AFRICORE service accounts use Rent / Water / Wi-Fi workflows
    # only for incoming funds. Outgoing funds require separate review.
    if transaction.bank_account.purpose in {
        "RENT",
        "WATER",
        "WIFI",
    }:
        category_map = {
            "RENT": "rent",
            "WATER": "water",
            "WIFI": "wifi",
        }

        if transaction.money_in > Decimal("0.00"):
            transaction.suggested_category = (
                category_map[
                    transaction.bank_account.purpose
                ]
            )

            transaction.match_notes = (
                f"{transaction.bank_account.get_purpose_display()} "
                f"incoming transaction awaiting tenant/service matching."
            )

        elif transaction.money_out > Decimal("0.00"):
            description = str(
                transaction.description or ""
            ).upper()

            bank_charge_markers = (
                "EXCISE DUTY",
                "ACCOUNT STATEMENT CHARGE",
                "TRANSACTION + SMS CHARGE",
                "SMS CHARGE",
                "BANK CHARGE",
                "TRANSFER CHARGE",
                "LEDGER FEE",
                "SERVICE CHARGE",
                "COMMISSION",
            )

            if any(
                marker in description
                for marker in bank_charge_markers
            ):
                transaction.suggested_category = "bank_charge"
                transaction.match_notes = (
                    "Recognized bank charge awaiting Finance approval."
                )
            else:
                transaction.suggested_category = "unknown"
                transaction.match_notes = (
                    "Outgoing transaction requires Finance review."
                )

        else:
            transaction.suggested_category = "unknown"
            transaction.match_notes = (
                "Zero-value transaction requires Finance review."
            )

        transaction.auto_matched = False
        transaction.confidence = 0

        transaction.save(
            update_fields=[
                "matched_sales_receipt",
                "matched_supplier_payment",
                "suggested_category",
                "auto_matched",
                "confidence",
                "match_notes",
            ]
        )

        return transaction

    # Generic ERP customer receipts
    if transaction.money_in > Decimal("0.00"):
        date_from = (
            transaction.transaction_date
            - timedelta(days=3)
        )

        date_to = (
            transaction.transaction_date
            + timedelta(days=3)
        )

        receipts = (
            SalesReceipt.objects
            .filter(
                bank_account=transaction.bank_account,
                status="POSTED",
                amount=transaction.money_in,
                receipt_date__range=(
                    date_from,
                    date_to,
                ),
            )
            .exclude(
                bank_transactions__match_status="approved",
            )
            .order_by(
                "receipt_date",
                "id",
            )
        )

        exact_reference = receipts.filter(
            reference__iexact=transaction.reference,
        ).first()

        match = exact_reference or receipts.first()

        if match:
            transaction.matched_sales_receipt = match
            transaction.suggested_category = (
                "customer_receipt"
            )
            transaction.auto_matched = True

            transaction.confidence = (
                100
                if exact_reference
                else 90
            )

            transaction.match_notes = (
                f"Matched customer receipt "
                f"{match.receipt_number}"
            )

            transaction.save(
                update_fields=[
                    "matched_sales_receipt",
                    "matched_supplier_payment",
                    "suggested_category",
                    "auto_matched",
                    "confidence",
                    "match_notes",
                ]
            )

            return transaction

    # Generic ERP supplier payments
    if transaction.money_out > Decimal("0.00"):
        date_from = (
            transaction.transaction_date
            - timedelta(days=3)
        )

        date_to = (
            transaction.transaction_date
            + timedelta(days=3)
        )

        payments = (
            SupplierPayment.objects
            .filter(
                bank_account=transaction.bank_account,
                posted=True,
                amount=transaction.money_out,
                payment_date__range=(
                    date_from,
                    date_to,
                ),
            )
            .exclude(
                bank_transactions__match_status="approved",
            )
            .order_by(
                "payment_date",
                "id",
            )
        )

        exact_reference = payments.filter(
            reference__iexact=transaction.reference,
        ).first()

        match = exact_reference or payments.first()

        if match:
            transaction.matched_supplier_payment = (
                match
            )

            transaction.suggested_category = (
                "supplier_payment"
            )

            transaction.auto_matched = True

            transaction.confidence = (
                100
                if exact_reference
                else 90
            )

            transaction.match_notes = (
                f"Matched supplier payment "
                f"{match.reference}"
            )

            transaction.save(
                update_fields=[
                    "matched_sales_receipt",
                    "matched_supplier_payment",
                    "suggested_category",
                    "auto_matched",
                    "confidence",
                    "match_notes",
                ]
            )

            return transaction

    transaction.auto_matched = False
    transaction.confidence = 0

    transaction.save(
        update_fields=[
            "matched_sales_receipt",
            "matched_supplier_payment",
            "auto_matched",
            "confidence",
        ]
    )

    return transaction





def extract_house_number(text):
    import re

    if not text:
        return None

    patterns = [
        r"HOUSE\s+NUMBER\s*[:#-]?\s*(\d+)",
        r"HOUSE[:\s#-]*(\d+)",
        r"#\s*(\d+)",
        r"ROOM[:\s#-]*(\d+)",
        r"\b(?:UNIT|RM)\s*[:#-]?\s*(\d+)\b",
    ]

    upper_text = str(text).upper()

    for pattern in patterns:
        match = re.search(pattern, upper_text)

        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None

    return None


def match_house_for_transaction(bank_transaction):
    from rentals.models import House

    transaction = bank_transaction
    account = transaction.bank_account
    apartment = account.apartment

    if not apartment:
        transaction.matched_house = None
        transaction.match_notes = (
            transaction.match_notes
            or "Bank account serves all apartments; house requires separate matching."
        )
        transaction.save(
            update_fields=[
                "matched_house",
                "match_notes",
            ]
        )
        return transaction

    house_number = (
        extract_house_number(transaction.reference)
        or extract_house_number(transaction.description)
    )

    if house_number is None:
        transaction.matched_house = None
        transaction.match_notes = (
            f"{account.get_purpose_display()} transaction "
            f"for {apartment.name}; no house number detected."
        )
        transaction.save(
            update_fields=[
                "matched_house",
                "match_notes",
            ]
        )
        return transaction

    house = (
        House.objects
        .filter(
            apartment=apartment,
            house_number=str(house_number),
        )
        .first()
    )

    if not house:
        transaction.matched_house = None
        transaction.match_notes = (
            f"House {house_number} was detected, "
            f"but it does not exist in {apartment.name}."
        )
        transaction.save(
            update_fields=[
                "matched_house",
                "match_notes",
            ]
        )
        return transaction

    transaction.matched_house = house
    transaction.match_notes = (
        f"Matched {apartment.name} House {house.house_number} "
        f"from bank statement reference."
    )

    transaction.save(
        update_fields=[
            "matched_house",
            "match_notes",
        ]
    )

    return transaction



def extract_equity_tenant_details(text):
    import re

    if not text:
        return {
            "name": None,
            "phone": None,
        }

    value = str(text)

    phone_match = re.search(
        r"\b(254\d{9})\b",
        value,
    )

    house_name_match = re.search(
        r"#\s*\d+\s+(.+?)(?=\s+[A-Za-z0-9]{10,}\b|$)",
        value,
    )

    name = None

    if house_name_match:
        name = house_name_match.group(1).strip()

        # Remove common trailing fragments introduced
        # by statement formatting.
        name = re.sub(
            r"/[A-Za-z0-9]+$",
            "",
            name,
        ).strip()

    return {
        "name": name,
        "phone": (
            phone_match.group(1)
            if phone_match
            else None
        ),
    }


def normalize_tenant_name(value):
    import re

    if not value:
        return ""

    value = str(value).upper().strip()
    value = re.sub(r"[^A-Z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def match_tenant_for_transaction(bank_transaction):
    from rentals.models import Tenant

    transaction = bank_transaction
    account = transaction.bank_account
    house = transaction.matched_house

    if not house:
        return transaction

    bank_name = account.bank_name.upper()

    if "EQUITY" in bank_name:
        details = extract_equity_tenant_details(
            transaction.description
        )

    elif "SIDIAN" in bank_name:
        details = extract_sidian_tenant_details(
            transaction.description
        )

    else:
        return transaction

    tenant_name = details["name"]
    phone = details["phone"]

    apartment = account.apartment

    # 1. Prefer tenant already assigned to the matched house.
    # This works even when the bank description has no tenant name.
    tenant = house.tenant

    if tenant:
        # If statement phone confirms the existing house tenant,
        # or the tenant has no phone yet, keep the existing tenant.
        if phone and not tenant.phone:
            tenant.phone = phone
            tenant.save(
                update_fields=["phone"]
            )

        transaction.matched_tenant = tenant

        transaction.match_notes = (
            f"Matched {apartment.name} "
            f"House {house.house_number}; "
            f"existing tenant {tenant.name}."
        )

        transaction.save(
            update_fields=[
                "matched_tenant",
                "match_notes",
            ]
        )

        return transaction

    # 2. If no tenant is assigned to the house, try phone first.
    tenant = None

    if phone:
        tenant = (
            Tenant.objects
            .filter(
                apartment=apartment,
                phone=phone,
            )
            .first()
        )

    if tenant:
        house.tenant = tenant
        house.occupied = True
        house.save(
            update_fields=[
                "tenant",
                "occupied",
            ]
        )

        transaction.matched_tenant = tenant
        transaction.match_notes = (
            f"Matched {apartment.name} "
            f"House {house.house_number}; "
            f"tenant {tenant.name} matched by phone."
        )

        transaction.save(
            update_fields=[
                "matched_tenant",
                "match_notes",
            ]
        )

        return transaction

    # A name is required only if neither house nor phone matched.
    if not tenant_name:
        transaction.match_notes = (
            f"{transaction.match_notes} "
            f"House matched but tenant identity could not be confirmed."
        ).strip()

        transaction.save(
            update_fields=["match_notes"]
        )

        return transaction

    # 3. Match normalized tenant name.

    if tenant:
        transaction.matched_tenant = tenant

        # Fill missing phone if available.
        if phone and not tenant.phone:
            tenant.phone = phone
            tenant.save(
                update_fields=["phone"]
            )

        transaction.match_notes = (
            f"Matched {apartment.name} "
            f"House {house.house_number}; "
            f"existing tenant {tenant.name}."
        )

        transaction.save(
            update_fields=[
                "matched_tenant",
                "match_notes",
            ]
        )

        return transaction

    # 2. Match same phone in same apartment.
    tenant = None

    if phone:
        tenant = (
            Tenant.objects
            .filter(
                apartment=apartment,
                phone=phone,
            )
            .first()
        )

    # 3. Match normalized tenant name.
    if not tenant:
        wanted_name = normalize_tenant_name(
            tenant_name
        )

        for candidate in Tenant.objects.filter(
            apartment=apartment
        ):
            if (
                normalize_tenant_name(candidate.name)
                == wanted_name
            ):
                tenant = candidate
                break

    created = False

    # 4. Create only if no safe match exists.
    if not tenant:
        tenant = Tenant.objects.create(
            apartment=apartment,
            name=tenant_name.strip(),
            phone=phone or "",
            active=True,
        )
        created = True

    # Fill missing phone on matched tenant.
    if phone and not tenant.phone:
        tenant.phone = phone
        tenant.save(
            update_fields=["phone"]
        )

    house.tenant = tenant
    house.occupied = True
    house.save(
        update_fields=[
            "tenant",
            "occupied",
        ]
    )

    transaction.matched_tenant = tenant

    transaction.match_notes = (
        f"Matched {apartment.name} "
        f"House {house.house_number}; "
        f"tenant {tenant.name}"
        f"{' created from statement' if created else ' matched to existing tenant'}."
    )

    transaction.save(
        update_fields=[
            "matched_tenant",
            "match_notes",
        ]
    )

    return transaction






def extract_sidian_tenant_details(text):
    import re

    if not text:
        return {
            "name": None,
            "phone": None,
        }

    value = str(text)

    phone_match = re.search(
        r"\b(254\d{9})\b",
        value,
    )

    # Examples:
    # 254746001589 50 CHARLES 352192
    # 254768188722 49 Donata 352192
    # 254715120929 RM31 352192
    name_match = re.search(
        r"\b254\d{9}\s+"
        r"(?:(?:RM|ROOM|B)\s*)?0*\d{1,3}\s+"
        r"([A-Za-z][A-Za-z .'-]*?)"
        r"\s+\d{5,8}\b",
        value,
        re.IGNORECASE,
    )

    name = None

    if name_match:
        name = name_match.group(1).strip()

    return {
        "name": name,
        "phone": (
            phone_match.group(1)
            if phone_match
            else None
        ),
    }



def extract_statement_account_number(text, bank_name):
    import re

    if not text:
        return None

    value = str(text)
    bank = str(bank_name).upper()

    patterns = []

    if "SIDIAN" in bank:
        patterns = [
            r"Account\s*No\.?\s*:?\s*(\d{8,20})",
            r"Account\s+No\.?\s*(\d{8,20})",
        ]

    elif "EQUITY" in bank:
        patterns = [
            r"Account\s+Number\s*(\d{8,20})",
            r"Account\s*Number\s*:?\s*(\d{8,20})",
        ]

    elif "KCB" in bank:
        patterns = [
            r"Account\s*:?\s*(\d{8,20})",
            r"Account\s+Number\s*:?\s*(\d{8,20})",
        ]

    elif "NCBA" in bank:
        patterns = [
            r"Account\s+Number\s*:?\s*(\d{8,20})",
        ]

    elif "FAMILY" in bank:
        patterns = [
            r"Account\s+Number\s*:?\s*(\d{8,20})",
            r"Account\s+No\.?\s*:?\s*(\d{8,20})",
        ]

    else:
        patterns = [
            r"Account\s+Number\s*:?\s*(\d{8,20})",
            r"Account\s+No\.?\s*:?\s*(\d{8,20})",
            r"Account\s*:?\s*(\d{8,20})",
        ]

    compact = re.sub(
        r"\s+",
        " ",
        value,
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            compact,
            re.IGNORECASE,
        )

        if match:
            return match.group(1)

    # Sidian PDF extraction often splits the labels and values.
    # Look for any known-looking account number after Account No.
    if "SIDIAN" in bank:
        match = re.search(
            r"Account\s+No\..{0,250}?(\d{10,20})",
            compact,
            re.IGNORECASE,
        )

        if match:
            return match.group(1)

    return None


def validate_statement_account(statement_upload, text):
    account = statement_upload.bank_account

    expected = str(
        account.account_number
    ).strip()

    detected = extract_statement_account_number(
        text,
        account.bank_name,
    )

    if not detected:
        raise ValueError(
            f"Could not detect the bank account number "
            f"inside this {account.bank_name} statement. "
            f"Expected account {expected}. "
            f"Statement was not processed."
        )

    expected_clean = (
        expected
        .replace(" ", "")
        .replace("-", "")
    )

    detected_clean = (
        detected
        .replace(" ", "")
        .replace("-", "")
    )

    if detected_clean != expected_clean:
        raise ValueError(
            f"Wrong statement account. "
            f"PDF account is {detected}; "
            f"selected AfriCore account is {expected}. "
            f"Nothing was imported."
        )

    return detected






