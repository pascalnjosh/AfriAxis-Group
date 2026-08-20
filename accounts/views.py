from django.shortcuts import render, redirect


def role_home(request):

    if not request.user.is_authenticated:
        return redirect("/admin/login/")

    profile = getattr(request.user, "userprofile", None)

    if not profile:
        return redirect("/admin/")

    if profile.role == "MD":
        return redirect("/dashboard/")

    if profile.role == "GM":
        return redirect("/dashboard/tenants/")

    if profile.role == "ACCOUNTS":
        return redirect("/payments/")

    return redirect("/admin/")


def erp_home(request):

    return render(
        request,
        "accounts/home.html"
    )

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@login_required
def role_home(request):
    if request.user.is_superuser:
        return redirect("/dashboard/")

    role = getattr(
        getattr(request.user, "userprofile", None),
        "role",
        None
    )

    if role in ("MD", "GM"):
        return redirect("/dashboard/")

    if role == "ACCOUNTS":
        return redirect("/dashboard/finance/")

    return redirect("/auth/login/")
