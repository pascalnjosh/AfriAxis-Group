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
