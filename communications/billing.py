from decimal import Decimal

from communications.models import SmsMessage
from communications.services import queue_and_send_sms


def money(value):
    value = Decimal(str(value or 0))
    return f"{value:,.2f}"


def property_name(tenant):
    apartment = getattr(tenant, "apartment", None)
    return getattr(apartment, "name", "AFRICORE HEIGHTS")


def house_number_for_tenant(tenant):
    try:
        house = tenant.houses.filter(
            occupied=True
        ).first()
    except Exception:
        house = None

    if house:
        return house.house_number

    try:
        house = tenant.house_set.filter(
            occupied=True
        ).first()
    except Exception:
        house = None

    return getattr(house, "house_number", "-")


def send_rent_bill_sms(rent, user=None):

    tenant = rent.tenant

    house = getattr(rent, "house", None)

    house_no = (
        getattr(house, "house_number", None)
        or house_number_for_tenant(tenant)
    )

    due = getattr(rent, "due_date", None)

    due_text = (
        due.strftime("%d %b %Y")
        if due
        else "-"
    )

    balance = getattr(rent, "balance", None)

    if balance is None:
        balance = (
            Decimal(str(rent.amount or 0))
            - Decimal(str(rent.amount_paid or 0))
        )

    message = (
        f"AFRIAXIS / AFRICORE HEIGHTS\n"
        f"RENT BILL\n"
        f"Tenant: {tenant.name}\n"
        f"Property: {property_name(tenant)}\n"
        f"House: {house_no}\n"
        f"Rent Due: KES {money(balance)}\n"
        f"Due Date: {due_text}\n"
        f"Please pay through the designated "
        f"AFRICORE HEIGHTS RENT bank account."
    )

    return queue_and_send_sms(
        phone=tenant.phone,
        recipient_name=tenant.name,
        message=message,
        bill_type=SmsMessage.BillType.RENT,
        reference=f"RENT-{rent.pk}",
        tenant=tenant,
        rent=rent,
        user=user,
    )


def send_water_bill_sms(water_bill, user=None):

    tenant = water_bill.tenant

    message = (
        f"AFRIAXIS / AFRICORE HEIGHTS\n"
        f"WATER BILL\n"
        f"Tenant: {tenant.name}\n"
        f"Property: {property_name(tenant)}\n"
        f"House: {house_number_for_tenant(tenant)}\n"
        f"Units Used: {water_bill.units_used}\n"
        f"Water Due: KES {money(water_bill.total_amount)}\n"
        f"Please pay through the designated "
        f"AFRICORE HEIGHTS WATER bank account."
    )

    return queue_and_send_sms(
        phone=tenant.phone,
        recipient_name=tenant.name,
        message=message,
        bill_type=SmsMessage.BillType.WATER,
        reference=f"WATER-{water_bill.pk}",
        tenant=tenant,
        water_bill=water_bill,
        user=user,
    )


def send_wifi_bill_sms(customer, user=None):

    package = customer.package

    if package:
        amount = package.price
        package_name = package.name
    else:
        amount = Decimal("0")
        package_name = "Not assigned"

    expiry = getattr(customer, "expiry_date", None)

    expiry_text = (
        expiry.strftime("%d %b %Y")
        if expiry
        else "-"
    )

    message = (
        f"AFRIAXIS / AFRICORE HEIGHTS\n"
        f"WI-FI BILL\n"
        f"Customer: {customer.name}\n"
        f"Package: {package_name}\n"
        f"Amount Due: KES {money(amount)}\n"
        f"Expiry: {expiry_text}\n"
        f"Please use the designated Wi-Fi payment channel."
    )

    return queue_and_send_sms(
        phone=customer.phone,
        recipient_name=customer.name,
        message=message,
        bill_type=SmsMessage.BillType.WIFI,
        reference=f"WIFI-{customer.pk}",
        wifi_customer=customer,
        user=user,
    )
