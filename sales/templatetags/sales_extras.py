from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


@register.filter
def money(value):
    """
    Format money as:
    320000 -> 320,000.00
    """

    try:
        value = Decimal(value)
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return value

    return f"{value:,.2f}"


@register.filter
def qty(value):
    """
    Format quantity without unnecessary
    trailing zeroes.
    """

    try:
        value = Decimal(value)
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return value

    text = format(
        value,
        "f",
    )

    if "." in text:
        text = text.rstrip(
            "0"
        ).rstrip(
            "."
        )

    return text
