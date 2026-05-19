from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect

from rentals.models import Tenant
from billing.models import Invoice


def tenant_login(request):

    error = None

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            login(request, user)

            return redirect("tenant_dashboard")

        error = "Invalid credentials"

    return render(
        request,
        "accounts/tenant_login.html",
        {
            "error": error
        }
    )


def tenant_dashboard(request):

    if not request.user.is_authenticated:
        return redirect("tenant_login")

    tenant = Tenant.objects.filter(
        name=request.user.username
    ).first()

    invoices = []

    if tenant:
        invoices = Invoice.objects.filter(
            tenant=tenant
        ).order_by("-created_at")

    return render(
        request,
        "accounts/tenant_dashboard.html",
        {
            "tenant": tenant,
            "invoices": invoices,
        }
    )


def tenant_logout(request):

    logout(request)

    return redirect("tenant_login")
