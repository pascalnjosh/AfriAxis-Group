from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.db.models import Sum

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from rentals.models import Apartment
from billing.models import Invoice


def apartment_statement_pdf(request, apartment_id):

    apartment = get_object_or_404(Apartment, id=apartment_id)

    invoices = Invoice.objects.filter(
        apartment=apartment
    ).select_related(
        "tenant"
    ).order_by(
        "tenant__name"
    )

    total_billed = invoices.aggregate(total=Sum("total_amount"))["total"] or 0
    total_paid = invoices.aggregate(total=Sum("amount_paid"))["total"] or 0
    total_balance = total_billed - total_paid

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{apartment.name}_statement.pdf"'

    pdf = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    y = height - 50

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(40, y, "AFRIAXIS ERP - APARTMENT STATEMENT")

    y -= 35
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, y, f"Apartment: {apartment.name}")

    y -= 25
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, y, f"Total Billed: KES {total_billed}")
    y -= 18
    pdf.drawString(40, y, f"Total Paid: KES {total_paid}")
    y -= 18
    pdf.drawString(40, y, f"Total Balance: KES {total_balance}")

    y -= 35
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(40, y, "Invoice")
    pdf.drawString(130, y, "Tenant")
    pdf.drawString(330, y, "Total")
    pdf.drawString(400, y, "Paid")
    pdf.drawString(470, y, "Balance")

    y -= 15
    pdf.setFont("Helvetica", 8)

    for invoice in invoices:

        if y < 60:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 8)

        pdf.drawString(40, y, invoice.invoice_number[:18])
        pdf.drawString(130, y, invoice.tenant.name[:30])
        pdf.drawString(330, y, f"{invoice.total_amount}")
        pdf.drawString(400, y, f"{invoice.amount_paid}")
        pdf.drawString(470, y, f"{invoice.balance()}")

        y -= 15

    pdf.save()

    return response
