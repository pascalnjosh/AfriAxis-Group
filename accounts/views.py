from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def erp_home(request):
    return render(
        request,
        "accounts/home.html",
    )


@login_required
def role_home(request):

    if request.user.is_superuser:
        return redirect("/dashboard/")

    profile = getattr(
        request.user,
        "userprofile",
        None,
    )

    if not profile:
        return redirect("/auth/login/")

    if profile.role in ("MD", "GM"):
        return redirect("/dashboard/")

    if profile.role == "ACCOUNTS":
        return redirect("/dashboard/finance/")

    return redirect("/auth/login/")
