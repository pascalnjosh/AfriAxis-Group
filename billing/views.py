from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse

from billing.forms import CommercialInvoiceForm, CommercialInvoiceLineFormSet
from billing.models import Invoice, InvoicePayment
from billing.services import create_commercial_invoice
from billing.utils import apply_mpesa_to_invoice
from rentals.models import Tenant


@login_required
def commercial_invoice_create(request):
    if request.method == "POST":
        form = CommercialInvoiceForm(request.POST)
        line_formset = CommercialInvoiceLineFormSet(
            request.POST,
            prefix="items",
        )

        if form.is_valid() and line_formset.is_valid():
            items = []

            for line_form in line_formset:
                if not line_form.cleaned_data:
                    continue

                if line_form.cleaned_data.get("DELETE"):
                    continue

                items.append(
                    {
                        "item_code": line_form.cleaned_data.get(
                            "item_code",
                            "",
                        ),
                        "description": line_form.cleaned_data[
                            "description"
                        ],
                        "quantity": line_form.cleaned_data[
                            "quantity"
                        ],
                        "unit": line_form.cleaned_data[
                            "unit"
                        ],
                        "unit_price": line_form.cleaned_data[
                            "unit_price"
                        ],
                        "discount_rate": line_form.cleaned_data[
                            "discount_rate"
                        ],
                        "tax_rate": line_form.cleaned_data[
                            "tax_rate"
                        ],
                    }
                )

            try:
                invoice = create_commercial_invoice(
                    customer_name=form.cleaned_data[
                        "customer_name"
                    ],
                    customer_phone=form.cleaned_data[
                        "customer_phone"
                    ],
                    customer_email=form.cleaned_data[
                        "customer_email"
                    ],
                    customer_address=form.cleaned_data[
                        "customer_address"
                    ],
                    customer_kra_pin=form.cleaned_data[
                        "customer_kra_pin"
                    ],
                    invoice_type=form.cleaned_data[
                        "invoice_type"
                    ],
                    due_date=form.cleaned_data[
                        "due_date"
                    ],
                    currency=form.cleaned_data[
                        "currency"
                    ],
                    notes=form.cleaned_data[
                        "notes"
                    ],
                    terms=form.cleaned_data[
                        "terms"
                    ],
                    items=items,
                )

            except ValueError as exc:
                form.add_error(None, str(exc))

            else:
                messages.success(
                    request,
                    (
                        f"Invoice {invoice.invoice_number} "
                        "created successfully."
                    ),
                )

                return redirect(
                    "invoice_detail",
                    invoice_id=invoice.id,
                )

    else:
        form = CommercialInvoiceForm()
        line_formset = CommercialInvoiceLineFormSet(
            prefix="items",
        )

    return render(
        request,
        "billing/commercial_invoice_form.html",
        {
            "form": form,
            "line_formset": line_formset,
        },
    )

def invoice_list(request):

    invoices = Invoice.objects.select_related(
        "tenant",
        "apartment"
    ).order_by("-created_at")

    return render(
        request,
        "billing/invoice_list.html",
        {
            "invoices": invoices,
        }
    )


def invoice_detail(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    return render(
        request,
        "billing/invoice_detail.html",
        {
            "invoice": invoice,
        }
    )


def tenant_status(request, tenant_id):

    tenant = get_object_or_404(
        Tenant,
        id=tenant_id
    )

    invoices = tenant.invoice_set.all().order_by(
        "-created_at"
    )

    return render(
        request,
        "tenant_status.html",
        {
            "tenant": tenant,
            "invoices": invoices,
        }
    )


def pay_invoice(request, invoice_id):

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id
    )

    if request.method == "POST":

        amount = request.POST.get("amount")
        phone = request.POST.get("phone")

        apply_mpesa_to_invoice(
            phone_number=phone,
            amount=amount,
            receipt=f"MANUAL-{invoice.invoice_number}",
            invoice=invoice,
        )

        return redirect(
            "tenant_status",
            tenant_id=invoice.tenant.id
        )

    return render(
        request,
        "pay_invoice.html",
        {
            "invoice": invoice,
        }
    )


def invoice_pdf(request, invoice_id):
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        KeepTogether,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    invoice = get_object_or_404(
        Invoice.objects.select_related(
            "tenant",
            "apartment",
        ).prefetch_related(
            "lines",
            "invoicepayment_set",
        ),
        id=invoice_id,
    )

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"Invoice {invoice.invoice_number}",
        author="AfriAxis Group",
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="Brand",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#111827"),
            spaceAfter=4,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SmallMuted",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#6B7280"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="InvoiceTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#111827"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#2563EB"),
            spaceBefore=6,
            spaceAfter=6,
        )
    )

    styles.add(
        ParagraphStyle(
            name="RightText",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            alignment=TA_RIGHT,
        )
    )

    styles.add(
        ParagraphStyle(
            name="CenterSmall",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#6B7280"),
        )
    )

    story = []

    customer_name = (
        invoice.customer_name
        or (invoice.tenant.name if invoice.tenant else "Customer")
    )

    customer_phone = (
        invoice.customer_phone
        or (invoice.tenant.phone if invoice.tenant else "")
        or "-"
    )

    header = Table(
        [
            [
                [
                    Paragraph("AfriAxis Group", styles["Brand"]),
                    Paragraph(
                        "Integrated Business &amp; Property Management",
                        styles["SmallMuted"],
                    ),
                    Spacer(1, 4),
                    Paragraph("Nyahururu, Kenya", styles["SmallMuted"]),
                    Paragraph("M-PESA Paybill: 880100", styles["SmallMuted"]),
                ],
                [
                    Paragraph("INVOICE", styles["InvoiceTitle"]),
                    Paragraph(
                        invoice.invoice_number,
                        styles["RightText"],
                    ),
                ],
            ]
        ],
        colWidths=[110 * mm, 52 * mm],
    )

    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    story.append(header)
    story.append(Spacer(1, 10))

    bill_to_rows = [
        ["Customer", customer_name],
        ["Phone", customer_phone],
        ["Email", invoice.customer_email or "-"],
        ["KRA PIN", invoice.customer_kra_pin or "-"],
    ]

    if invoice.apartment:
        bill_to_rows.append(["Apartment", invoice.apartment.name])

    invoice_detail_rows = [
        ["Invoice Type", invoice.get_invoice_type_display()],
        ["Invoice Date", invoice.invoice_date.strftime("%d %b %Y")],
        [
            "Due Date",
            invoice.due_date.strftime("%d %b %Y")
            if invoice.due_date
            else "-",
        ],
        ["Currency", invoice.currency],
        ["Status", invoice.get_status_display()],
    ]

    def info_box(title, rows):
        data = [[Paragraph(title, styles["SectionHeading"])]]
        data.extend(
            [
                [
                    Paragraph(
                        str(label),
                        styles["SmallMuted"],
                    ),
                    Paragraph(
                        str(value),
                        styles["RightText"],
                    ),
                ]
                for label, value in rows
            ]
        )

        table = Table(
            data,
            colWidths=[37 * mm, 43 * mm],
        )

        table.setStyle(
            TableStyle(
                [
                    ("SPAN", (0, 0), (1, 0)),
                    ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#D1D5DB")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LINEBELOW", (0, 1), (-1, -2), 0.25, colors.HexColor("#E5E7EB")),
                ]
            )
        )

        return table

    information = Table(
        [
            [
                info_box("BILL TO", bill_to_rows),
                info_box("INVOICE DETAILS", invoice_detail_rows),
            ]
        ],
        colWidths=[82 * mm, 82 * mm],
        hAlign="LEFT",
    )

    information.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 4),
                ("LEFTPADDING", (1, 0), (1, 0), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    story.append(information)
    story.append(Spacer(1, 14))
    story.append(Paragraph("Invoice Items", styles["SectionHeading"]))

    item_rows = [
        [
            "Description",
            "Qty",
            "Unit",
            "Unit Price",
            "Discount",
            "Tax",
            "Total",
        ]
    ]

    lines = list(invoice.lines.all())

    if lines:
        for line in lines:
            description = line.description

            if line.item_code:
                description += f"<br/><font size='7'>Code: {line.item_code}</font>"

            item_rows.append(
                [
                    Paragraph(description, styles["Normal"]),
                    f"{line.quantity:.2f}",
                    line.unit,
                    f"{line.unit_price:,.2f}",
                    f"{line.discount_amount:,.2f}",
                    f"{line.tax_amount:,.2f}",
                    f"{line.line_total:,.2f}",
                ]
            )
    else:
        legacy_items = (
            ("Rent", invoice.rent_amount, "MONTH"),
            ("Water", invoice.water_amount, "BILL"),
            ("Wi-Fi", invoice.wifi_amount, "MONTH"),
        )

        for description, amount, unit in legacy_items:
            if amount > 0:
                item_rows.append(
                    [
                        description,
                        "1.00",
                        unit,
                        f"{amount:,.2f}",
                        "0.00",
                        "0.00",
                        f"{amount:,.2f}",
                    ]
                )

    item_table = Table(
        item_rows,
        repeatRows=1,
        colWidths=[
            55 * mm,
            14 * mm,
            16 * mm,
            24 * mm,
            21 * mm,
            18 * mm,
            24 * mm,
        ],
    )

    item_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ALIGN", (1, 0), (-1, 0), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                    colors.white,
                    colors.HexColor("#F9FAFB"),
                ]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    story.append(item_table)
    story.append(Spacer(1, 12))

    summary_rows = [
        ["Subtotal", f"{invoice.currency} {invoice.subtotal:,.2f}"],
        ["Discount", f"{invoice.currency} {invoice.discount_amount:,.2f}"],
        ["Tax / VAT", f"{invoice.currency} {invoice.tax_amount:,.2f}"],
        ["Grand Total", f"{invoice.currency} {invoice.total_amount:,.2f}"],
        ["Amount Paid", f"{invoice.currency} {invoice.amount_paid:,.2f}"],
        ["Balance Due", f"{invoice.currency} {invoice.balance():,.2f}"],
    ]

    summary = Table(
        summary_rows,
        colWidths=[43 * mm, 45 * mm],
        hAlign="RIGHT",
    )

    summary.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
                ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 3), (-1, 3), colors.white),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#B91C1C")),
                ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    story.append(summary)
    story.append(Spacer(1, 14))

    payments = list(
        invoice.invoicepayment_set.all().order_by("paid_at", "id")
    )

    story.append(Paragraph("Payment History", styles["SectionHeading"]))

    payment_rows = [["Date", "Phone", "Receipt", "Amount"]]

    if payments:
        for payment in payments:
            payment_rows.append(
                [
                    payment.paid_at.strftime("%d %b %Y %H:%M"),
                    payment.phone_number,
                    payment.mpesa_receipt or "-",
                    f"{invoice.currency} {payment.amount:,.2f}",
                ]
            )
    else:
        payment_rows.append(
            [
                Paragraph(
                    "No payments recorded for this invoice.",
                    styles["CenterSmall"],
                ),
                "",
                "",
                "",
            ]
        )

    payment_table = Table(
        payment_rows,
        colWidths=[42 * mm, 42 * mm, 45 * mm, 35 * mm],
        repeatRows=1,
    )

    payment_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]

    if not payments:
        payment_style.append(("SPAN", (0, 1), (-1, 1)))

    payment_table.setStyle(TableStyle(payment_style))
    story.append(payment_table)
    story.append(Spacer(1, 14))

    etims_rows = [
        ["Submission Status", invoice.get_etims_status_display()],
        ["Receipt Number", invoice.etims_receipt_number or "-"],
        ["Control Unit", invoice.etims_control_unit_number or "-"],
    ]

    etims_table = info_box("eTIMS INFORMATION", etims_rows)

    qr_text = (
        invoice.etims_qr_code_url
        if invoice.etims_qr_code_url
        else "eTIMS QR Code\nNot available"
    )

    qr_box = Table(
        [[Paragraph(qr_text.replace("\n", "<br/>"), styles["CenterSmall"])]],
        colWidths=[45 * mm],
        rowHeights=[32 * mm],
    )

    qr_box.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#9CA3AF")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )

    etims_section = Table(
        [[etims_table, qr_box]],
        colWidths=[115 * mm, 49 * mm],
    )

    etims_section.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 4),
                ("LEFTPADDING", (1, 0), (1, 0), 4),
            ]
        )
    )

    story.append(KeepTogether(etims_section))

    if invoice.notes:
        story.append(Spacer(1, 12))
        story.append(Paragraph("Notes", styles["SectionHeading"]))
        story.append(
            Table(
                [[Paragraph(invoice.notes, styles["Normal"])]],
                colWidths=[164 * mm],
                style=TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                ),
            )
        )

    story.append(Spacer(1, 16))
    story.append(
        Paragraph(
            "Thank you for doing business with AfriAxis Group.",
            styles["CenterSmall"],
        )
    )

    document.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(
        pdf,
        content_type="application/pdf",
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{invoice.invoice_number}.pdf"'
    )

    return response

def tenant_portal(request, tenant_id):

    tenant = get_object_or_404(
        Tenant,
        id=tenant_id
    )

    invoices = Invoice.objects.filter(
        tenant=tenant
    ).order_by(
        "-created_at"
    )

    total_billed = 0
    total_paid = 0
    total_balance = 0

    for invoice in invoices:
        total_billed += invoice.total_amount
        total_paid += invoice.amount_paid
        total_balance += invoice.balance()

    return render(
        request,
        "billing/tenant_portal.html",
        {
            "tenant": tenant,
            "invoices": invoices,
            "total_billed": total_billed,
            "total_paid": total_paid,
            "total_balance": total_balance,
        }
    )


def receipt_detail(request, payment_id):
    payment = get_object_or_404(
        InvoicePayment,
        id=payment_id,
    )

    return render(
        request,
        "billing/receipt_detail.html",
        {
            "payment": payment,
            "invoice": payment.invoice,
        },
    )
