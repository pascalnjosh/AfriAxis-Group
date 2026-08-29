from datetime import timedelta
from decimal import Decimal, InvalidOperation

from accounts.decorators import operations_required
from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from enterprise.models import Branch, Company
from enterprise.services import (
    get_delivery_reference,
    get_invoice_reference,
)
from inventory.models import StorageLocation, Warehouse

from .models import (
    Customer,
    DeliveryNote,
    DeliveryNoteLine,
    Product,
    SalesInvoice,
    SalesInvoiceLine,
    SalesOrder,
    SalesOrderLine,
    SalesReceipt,
)
from .services import (
    post_delivery_note,
    post_sales_invoice,
)


FAS_COMPANY_NAME = "FAIRLANE AGRISERVICE AND SUPPLIERS"
FAS_BRANCH_CODE = "FAS-HQ"
FAS_WAREHOUSE_CODE = "FAS-MAIN"
FAS_FINISHED_LOCATION_CODE = "FINISHED"


def _fas_company():
    return Company.objects.get(
        name=FAS_COMPANY_NAME,
        active=True,
    )


def _fas_branch(company):
    return Branch.objects.get(
        company=company,
        code=FAS_BRANCH_CODE,
        active=True,
    )


def _fas_warehouse(company):
    return Warehouse.objects.get(
        company=company,
        code=FAS_WAREHOUSE_CODE,
    )


def _fas_finished_location(warehouse):
    return StorageLocation.objects.get(
        warehouse=warehouse,
        code=FAS_FINISHED_LOCATION_CODE,
    )


def _decimal_value(value, field_name):
    try:
        return Decimal(str(value).strip())
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        raise ValueError(
            f"{field_name} must be a valid number."
        )


def _next_sales_order_number():
    today = timezone.localdate()

    prefix = f"FAS-SO-{today.year}-"

    last_order = (
        SalesOrder.objects
        .filter(
            order_number__startswith=prefix
        )
        .order_by("-id")
        .first()
    )

    number = 1

    if last_order:
        try:
            number = (
                int(
                    last_order.order_number.rsplit(
                        "-",
                        1,
                    )[-1]
                )
                + 1
            )
        except (
            ValueError,
            IndexError,
        ):
            number = (
                SalesOrder.objects
                .filter(
                    order_number__startswith=prefix
                )
                .count()
                + 1
            )

    return f"{prefix}{number:04d}"


def _number_to_words_under_1000(number):
    ones = [
        "",
        "One",
        "Two",
        "Three",
        "Four",
        "Five",
        "Six",
        "Seven",
        "Eight",
        "Nine",
        "Ten",
        "Eleven",
        "Twelve",
        "Thirteen",
        "Fourteen",
        "Fifteen",
        "Sixteen",
        "Seventeen",
        "Eighteen",
        "Nineteen",
    ]

    tens = [
        "",
        "",
        "Twenty",
        "Thirty",
        "Forty",
        "Fifty",
        "Sixty",
        "Seventy",
        "Eighty",
        "Ninety",
    ]

    parts = []

    if number >= 100:
        parts.append(
            ones[number // 100]
            + " Hundred"
        )
        number %= 100

    if number >= 20:
        parts.append(
            tens[number // 10]
        )

        if number % 10:
            parts.append(
                ones[number % 10]
            )

    elif number > 0:
        parts.append(
            ones[number]
        )

    return " ".join(parts)


def _integer_to_words(number):
    if number == 0:
        return "Zero"

    groups = [
        (1000000000, "Billion"),
        (1000000, "Million"),
        (1000, "Thousand"),
        (1, ""),
    ]

    words = []

    for value, label in groups:
        if number >= value:
            part = number // value
            number %= value

            if value >= 1000:
                words.append(
                    _number_to_words_under_1000(
                        part
                    )
                )
            else:
                words.append(
                    _number_to_words_under_1000(
                        part
                    )
                )

            if label:
                words.append(label)

    return " ".join(
        word
        for word in words
        if word
    )


def _money_to_words(amount):
    amount = Decimal(amount).quantize(
        Decimal("0.01")
    )

    shillings = int(amount)
    cents = int(
        (
            amount
            - Decimal(shillings)
        )
        * 100
    )

    words = (
        "Kenya Shillings "
        + _integer_to_words(
            shillings
        )
    )

    if cents:
        words += (
            " and "
            + _integer_to_words(
                cents
            )
            + " Cents"
        )

    return words + " Only"


@operations_required
def sales_dashboard(request):
    customers = (
        Customer.objects
        .filter(active=True)
        .order_by("name")
    )

    sales_orders = (
        SalesOrder.objects
        .select_related(
            "customer",
            "company",
            "branch",
        )
        .order_by(
            "-order_date",
            "-id",
        )[:10]
    )

    delivery_notes = (
        DeliveryNote.objects
        .select_related(
            "customer",
            "sales_order",
            "warehouse",
        )
        .order_by(
            "-delivery_date",
            "-id",
        )[:10]
    )

    sales_invoices = (
        SalesInvoice.objects
        .select_related(
            "customer",
            "sales_order",
            "delivery_note",
        )
        .order_by(
            "-invoice_date",
            "-id",
        )[:10]
    )

    sales_receipts = (
        SalesReceipt.objects
        .select_related(
            "customer",
            "sales_invoice",
            "bank_account",
        )
        .order_by(
            "-receipt_date",
            "-id",
        )[:10]
    )

    context = {
        "customer_count": Customer.objects.count(),
        "active_customer_count": (
            Customer.objects
            .filter(active=True)
            .count()
        ),
        "sales_order_count": SalesOrder.objects.count(),
        "delivery_note_count": DeliveryNote.objects.count(),
        "sales_invoice_count": SalesInvoice.objects.count(),
        "sales_receipt_count": SalesReceipt.objects.count(),
        "customers": customers,
        "sales_orders": sales_orders,
        "delivery_notes": delivery_notes,
        "sales_invoices": sales_invoices,
        "sales_receipts": sales_receipts,
    }

    return render(
        request,
        "sales/dashboard.html",
        context,
    )


@operations_required
def fas_customer_create(request):
    fas = _fas_company()

    if request.method == "POST":
        try:
            name = (
                request.POST.get(
                    "name",
                    ""
                )
                .strip()
            )

            if not name:
                raise ValueError(
                    "Customer name is required."
                )

            customer_code = (
                request.POST.get(
                    "customer_code",
                    ""
                )
                .strip()
            )

            if not customer_code:
                existing = (
                    Customer.objects
                    .filter(
                        company=fas
                    )
                    .count()
                )

                customer_code = (
                    f"FAS-CUST-"
                    f"{existing + 1:04d}"
                )

            if Customer.objects.filter(
                company=fas,
                customer_code=customer_code,
            ).exists():
                raise ValueError(
                    "Customer code already exists."
                )

            customer = Customer.objects.create(
                company=fas,
                customer_code=customer_code,
                customer_type=(
                    request.POST.get(
                        "customer_type",
                        "BUSINESS",
                    )
                ),
                name=name,
                phone=(
                    request.POST.get(
                        "phone",
                        ""
                    )
                    .strip()
                ),
                email=(
                    request.POST.get(
                        "email",
                        ""
                    )
                    .strip()
                ),
                kra_pin=(
                    request.POST.get(
                        "kra_pin",
                        ""
                    )
                    .strip()
                ),
                address=(
                    request.POST.get(
                        "address",
                        ""
                    )
                    .strip()
                ),
                active=True,
            )

            messages.success(
                request,
                (
                    f"Customer {customer.name} "
                    "created successfully."
                ),
            )

            return redirect(
                "new_sale"
            )

        except Exception as exc:
            messages.error(
                request,
                str(exc),
            )

    return render(
        request,
        "sales/customer_form.html",
        {
            "fas": fas,
        },
    )


@operations_required
def new_sale(request):
    fas = _fas_company()
    branch = _fas_branch(fas)

    customers = (
        Customer.objects
        .filter(
            company=fas,
            active=True,
        )
        .order_by("name")
    )

    products = (
        Product.objects
        .filter(
            company=fas,
            category__code="FINISHED",
            active=True,
        )
        .select_related(
            "unit",
            "currency",
            "category",
        )
        .order_by("name")
    )

    if request.method == "POST":
        try:
            customer_id = request.POST.get(
                "customer"
            )

            if not customer_id:
                raise ValueError(
                    "Select a customer."
                )

            customer = Customer.objects.get(
                id=customer_id,
                company=fas,
                active=True,
            )

            customer_reference = (
                request.POST.get(
                    "customer_reference",
                    ""
                )
                .strip()
            )

            delivery_address = (
                request.POST.get(
                    "delivery_address",
                    ""
                )
                .strip()
            )

            notes = (
                request.POST.get(
                    "notes",
                    ""
                )
                .strip()
            )

            terms = (
                request.POST.get(
                    "terms",
                    "30 DAYS"
                )
                .strip()
            )

            order_date_text = request.POST.get(
                "order_date"
            )

            order_date = (
                timezone.datetime.strptime(
                    order_date_text,
                    "%Y-%m-%d",
                ).date()
                if order_date_text
                else timezone.localdate()
            )

            expected_text = request.POST.get(
                "expected_delivery_date"
            )

            expected_delivery_date = (
                timezone.datetime.strptime(
                    expected_text,
                    "%Y-%m-%d",
                ).date()
                if expected_text
                else None
            )

            product_ids = (
                request.POST.getlist(
                    "product"
                )
            )

            quantities = (
                request.POST.getlist(
                    "quantity"
                )
            )

            rates = (
                request.POST.getlist(
                    "unit_price"
                )
            )

            tax_rates = (
                request.POST.getlist(
                    "tax_rate"
                )
            )

            if not (
                len(product_ids)
                == len(quantities)
                == len(rates)
                == len(tax_rates)
            ):
                raise ValueError(
                    "Sales line data is incomplete."
                )

            lines = []

            subtotal = Decimal("0.00")
            tax_total = Decimal("0.00")
            total = Decimal("0.00")

            currency = None

            for index, product_id in enumerate(
                product_ids
            ):
                if not str(
                    product_id
                ).strip():
                    continue

                product = Product.objects.get(
                    id=product_id,
                    company=fas,
                    category__code="FINISHED",
                    active=True,
                )

                quantity = _decimal_value(
                    quantities[index],
                    "Quantity",
                )

                rate = _decimal_value(
                    rates[index],
                    "Rate",
                )

                tax_rate = _decimal_value(
                    tax_rates[index],
                    "Tax rate",
                )

                if quantity <= 0:
                    raise ValueError(
                        "Quantity must be "
                        "greater than zero."
                    )

                if rate <= 0:
                    raise ValueError(
                        "Rate must be "
                        "greater than zero."
                    )

                if tax_rate < 0:
                    raise ValueError(
                        "Tax rate cannot "
                        "be negative."
                    )

                if currency is None:
                    currency = product.currency

                if (
                    product.currency_id
                    != currency.id
                ):
                    raise ValueError(
                        "All order items must "
                        "use one currency."
                    )

                line_subtotal = (
                    quantity * rate
                )

                line_tax = (
                    line_subtotal
                    * tax_rate
                    / Decimal("100")
                )

                subtotal += line_subtotal
                tax_total += line_tax
                total += (
                    line_subtotal
                    + line_tax
                )

                lines.append(
                    {
                        "product": product,
                        "quantity": quantity,
                        "unit_price": rate,
                        "tax_rate": tax_rate,
                    }
                )

            if not lines:
                raise ValueError(
                    "Add at least one item."
                )

            with transaction.atomic():
                order = SalesOrder.objects.create(
                    order_number=(
                        _next_sales_order_number()
                    ),
                    company=fas,
                    branch=branch,
                    customer=customer,
                    order_date=order_date,
                    expected_delivery_date=(
                        expected_delivery_date
                    ),
                    currency=currency,
                    status="DRAFT",
                    customer_reference=(
                        customer_reference
                    ),
                    delivery_address=(
                        delivery_address
                    ),
                    notes=notes,
                    terms=terms,
                    subtotal=subtotal,
                    discount_amount=(
                        Decimal("0.00")
                    ),
                    tax_amount=tax_total,
                    total_amount=total,
                    created_by=request.user,
                )

                for row in lines:
                    SalesOrderLine.objects.create(
                        sales_order=order,
                        product=row["product"],
                        description=(
                            row["product"].name
                        ),
                        quantity=row["quantity"],
                        quantity_delivered=(
                            Decimal("0.000")
                        ),
                        unit_price=(
                            row["unit_price"]
                        ),
                        discount_rate=(
                            Decimal("0.00")
                        ),
                        tax_rate=row["tax_rate"],
                    )

            messages.success(
                request,
                (
                    f"Sales Order "
                    f"{order.order_number} "
                    "created successfully."
                ),
            )

            return redirect(
                "sales_order_detail",
                pk=order.pk,
            )

        except Exception as exc:
            messages.error(
                request,
                str(exc),
            )

    return render(
        request,
        "sales/new_sale.html",
        {
            "fas": fas,
            "branch": branch,
            "customers": customers,
            "products": products,
            "today": timezone.localdate(),
        },
    )


@operations_required
def sales_order_detail(request, pk):
    fas = _fas_company()

    order = get_object_or_404(
        SalesOrder.objects.select_related(
            "company",
            "branch",
            "customer",
            "currency",
        ),
        pk=pk,
        company=fas,
    )

    order_lines = (
        SalesOrderLine.objects
        .filter(
            sales_order=order
        )
        .select_related(
            "product",
            "product__unit",
        )
        .order_by("id")
    )

    delivery = (
        DeliveryNote.objects
        .filter(
            sales_order=order
        )
        .order_by("id")
        .first()
    )

    invoice = (
        SalesInvoice.objects
        .filter(
            sales_order=order
        )
        .order_by("id")
        .first()
    )

    return render(
        request,
        "sales/order_detail.html",
        {
            "order": order,
            "order_lines": order_lines,
            "delivery": delivery,
            "invoice": invoice,
        },
    )


@operations_required
@require_POST
def create_sales_documents(request, pk):
    fas = _fas_company()

    try:
        with transaction.atomic():
            order = (
                SalesOrder.objects
                .select_for_update()
                .select_related(
                    "customer",
                    "company",
                    "branch",
                    "currency",
                )
                .get(
                    pk=pk,
                    company=fas,
                )
            )

            order_lines = list(
                SalesOrderLine.objects
                .filter(
                    sales_order=order
                )
                .select_related(
                    "product"
                )
                .order_by("id")
            )

            if not order_lines:
                raise ValueError(
                    "Sales Order has no items."
                )

            branch = order.branch

            if branch is None:
                branch = _fas_branch(fas)

                order.branch = branch
                order.save(
                    update_fields=[
                        "branch"
                    ]
                )

            warehouse = _fas_warehouse(
                fas
            )

            finished_location = (
                _fas_finished_location(
                    warehouse
                )
            )

            delivery = (
                DeliveryNote.objects
                .filter(
                    sales_order=order
                )
                .first()
            )

            if delivery is None:
                delivery_number = (
                    get_delivery_reference(
                        company_name=fas.name,
                        branch_code=branch.code,
                    )
                )

                delivery = (
                    DeliveryNote.objects.create(
                        delivery_number=(
                            delivery_number
                        ),
                        sales_order=order,
                        customer=order.customer,
                        warehouse=warehouse,
                        delivery_date=(
                            order.expected_delivery_date
                            or timezone.localdate()
                        ),
                        delivery_address=(
                            order.delivery_address
                        ),
                        vehicle_number="",
                        driver_name="",
                        received_by_name="",
                        status="DRAFT",
                        notes=order.notes,
                    )
                )

                for line in order_lines:
                    DeliveryNoteLine.objects.create(
                        delivery_note=delivery,
                        sales_order_line=line,
                        product=line.product,
                        location=(
                            finished_location
                        ),
                        quantity=line.quantity,
                        batch_number="",
                    )

            invoice = (
                SalesInvoice.objects
                .filter(
                    sales_order=order
                )
                .first()
            )

            if invoice is None:
                invoice_number = (
                    get_invoice_reference(
                        company_name=fas.name,
                        branch_code=branch.code,
                    )
                )

                due_date = (
                    timezone.localdate()
                    + timedelta(days=30)
                )

                invoice = (
                    SalesInvoice.objects.create(
                        invoice_number=(
                            invoice_number
                        ),
                        company=fas,
                        branch=branch,
                        customer=order.customer,
                        sales_order=order,
                        delivery_note=delivery,
                        currency=order.currency,
                        invoice_date=(
                            timezone.localdate()
                        ),
                        due_date=due_date,
                        customer_reference=(
                            order.customer_reference
                        ),
                        status="DRAFT",
                        notes=order.notes,
                        terms=(
                            order.terms
                            or "30 DAYS"
                        ),
                        subtotal=order.subtotal,
                        discount_amount=(
                            order.discount_amount
                        ),
                        tax_amount=(
                            order.tax_amount
                        ),
                        total_amount=(
                            order.total_amount
                        ),
                        amount_paid=(
                            Decimal("0.00")
                        ),
                        created_by=request.user,
                    )
                )

                for line in order_lines:
                    SalesInvoiceLine.objects.create(
                        sales_invoice=invoice,
                        sales_order_line=line,
                        product=line.product,
                        description=(
                            line.description
                        ),
                        quantity=line.quantity,
                        unit_price=line.unit_price,
                        discount_rate=(
                            line.discount_rate
                        ),
                        tax_rate=line.tax_rate,
                    )

            if order.status == "DRAFT":
                order.status = "CONFIRMED"

                order.save(
                    update_fields=[
                        "status"
                    ]
                )

        messages.success(
            request,
            (
                "Invoice and Delivery "
                "created successfully."
            ),
        )

    except Exception as exc:
        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "sales_order_detail",
        pk=pk,
    )


@operations_required
def invoice_print(request, pk):
    fas = _fas_company()

    invoice = get_object_or_404(
        SalesInvoice.objects.select_related(
            "company",
            "branch",
            "customer",
            "sales_order",
            "delivery_note",
            "currency",
        ),
        pk=pk,
        company=fas,
    )

    lines = (
        SalesInvoiceLine.objects
        .filter(
            sales_invoice=invoice
        )
        .select_related(
            "product",
            "product__unit",
        )
        .order_by("id")
    )

    return render(
        request,
        "sales/invoice_print.html",
        {
            "invoice": invoice,
            "lines": lines,
            "amount_words": (
                _money_to_words(
                    invoice.total_amount
                )
            ),
        },
    )


@operations_required
def delivery_print(request, pk):
    fas = _fas_company()

    delivery = get_object_or_404(
        DeliveryNote.objects.select_related(
            "sales_order",
            "customer",
            "warehouse",
        ),
        pk=pk,
        sales_order__company=fas,
    )

    lines = (
        DeliveryNoteLine.objects
        .filter(
            delivery_note=delivery
        )
        .select_related(
            "product",
            "product__unit",
            "location",
        )
        .order_by("id")
    )

    return render(
        request,
        "sales/delivery_print.html",
        {
            "delivery": delivery,
            "lines": lines,
        },
    )


@operations_required
@require_POST
def invoice_post(request, pk):
    fas = _fas_company()

    invoice = get_object_or_404(
        SalesInvoice,
        pk=pk,
        company=fas,
    )

    try:
        post_sales_invoice(
            invoice,
            user=request.user,
        )

        invoice.refresh_from_db()

        messages.success(
            request,
            (
                f"Invoice "
                f"{invoice.invoice_number} "
                f"posted successfully."
            ),
        )

    except Exception as exc:
        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "sales_order_detail",
        pk=invoice.sales_order_id,
    )


@operations_required
@require_POST
def delivery_post(request, pk):
    fas = _fas_company()

    delivery = get_object_or_404(
        DeliveryNote,
        pk=pk,
        sales_order__company=fas,
    )

    try:
        post_delivery_note(
            delivery,
            user=request.user,
        )

        delivery.refresh_from_db()

        messages.success(
            request,
            (
                f"Delivery "
                f"{delivery.delivery_number} "
                "posted successfully."
            ),
        )

    except Exception as exc:
        messages.error(
            request,
            (
                "Delivery was NOT posted: "
                + str(exc)
            ),
        )

    return redirect(
        "sales_order_detail",
        pk=delivery.sales_order_id,
    )
