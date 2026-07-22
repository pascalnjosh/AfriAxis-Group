from django import forms
from django.forms import formset_factory


class CommercialInvoiceForm(forms.Form):
    INVOICE_TYPE_CHOICES = (
        ("COMMERCIAL", "Commercial Invoice"),
        ("SERVICE", "Service Invoice"),
    )

    customer_name = forms.CharField(
        max_length=200,
        label="Customer Name",
    )

    customer_phone = forms.CharField(
        max_length=30,
        required=False,
        label="Phone",
    )

    customer_email = forms.EmailField(
        required=False,
        label="Email",
    )

    customer_address = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
            }
        ),
        label="Address",
    )

    customer_kra_pin = forms.CharField(
        max_length=30,
        required=False,
        label="KRA PIN",
    )

    invoice_type = forms.ChoiceField(
        choices=INVOICE_TYPE_CHOICES,
        initial="COMMERCIAL",
    )

    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "type": "date",
            }
        ),
    )

    currency = forms.CharField(
        max_length=3,
        initial="KES",
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
            }
        ),
    )

    terms = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
            }
        ),
    )


class CommercialInvoiceLineForm(forms.Form):
    item_code = forms.CharField(
        max_length=100,
        required=False,
        label="Item Code",
    )

    description = forms.CharField(
        max_length=255,
        label="Description",
    )

    quantity = forms.DecimalField(
        min_value=0.01,
        decimal_places=2,
        max_digits=14,
        initial=1,
    )

    unit = forms.CharField(
        max_length=30,
        initial="EA",
    )

    unit_price = forms.DecimalField(
        min_value=0,
        decimal_places=2,
        max_digits=14,
    )

    discount_rate = forms.DecimalField(
        min_value=0,
        max_value=100,
        decimal_places=2,
        max_digits=5,
        initial=0,
    )

    tax_rate = forms.DecimalField(
        min_value=0,
        max_value=100,
        decimal_places=2,
        max_digits=5,
        initial=0,
    )


CommercialInvoiceLineFormSet = formset_factory(
    CommercialInvoiceLineForm,
    extra=0,
    min_num=1,
    validate_min=True,
    can_delete=True,
)


