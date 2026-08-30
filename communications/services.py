import re

from django.conf import settings
from django.utils import timezone

from .models import SmsMessage


def normalize_kenyan_phone(value):
    digits = re.sub(r"\D", "", str(value or ""))

    if digits.startswith("254") and len(digits) == 12:
        return "+" + digits

    if digits.startswith("0") and len(digits) == 10:
        return "+254" + digits[1:]

    if len(digits) == 9:
        return "+254" + digits

    return str(value or "").strip()


def create_sms(
    *,
    phone,
    message,
    bill_type=SmsMessage.BillType.GENERAL,
    recipient_name="",
    reference="",
    tenant=None,
    rent=None,
    water_bill=None,
    wifi_customer=None,
    user=None,
):
    phone = normalize_kenyan_phone(phone)

    if not phone:
        raise ValueError("SMS recipient phone number is required.")

    sms = SmsMessage.objects.create(
        phone_number=phone,
        recipient_name=recipient_name or "",
        bill_type=bill_type,
        message=message,
        reference=reference or "",
        tenant=tenant,
        rent=rent,
        water_bill=water_bill,
        wifi_customer=wifi_customer,
        created_by=user,
        status=SmsMessage.Status.QUEUED,
    )

    return sms


def send_sms_record(sms):
    """
    Safe V7 behaviour.

    SMS_MODE=TEST:
        Records message but does not claim real delivery.

    SMS_MODE=LIVE:
        Intentionally refuses to fake delivery until a real
        SMS provider implementation and credentials are supplied.
    """

    mode = getattr(settings, "SMS_MODE", "TEST").upper()

    if mode != "LIVE":
        sms.status = SmsMessage.Status.TEST
        sms.provider = "TEST"
        sms.sent_at = timezone.now()

        sms.save(
            update_fields=[
                "status",
                "provider",
                "sent_at",
            ]
        )

        print(
            f"[AFRIAXIS SMS TEST] "
            f"{sms.phone_number}: {sms.message}"
        )

        return sms

    sms.status = SmsMessage.Status.FAILED
    sms.provider = "UNCONFIGURED"
    sms.error_message = (
        "SMS_MODE is LIVE but no live SMS provider "
        "has been configured."
    )

    sms.save(
        update_fields=[
            "status",
            "provider",
            "error_message",
        ]
    )

    raise RuntimeError(sms.error_message)


def queue_and_send_sms(**kwargs):
    sms = create_sms(**kwargs)
    return send_sms_record(sms)
