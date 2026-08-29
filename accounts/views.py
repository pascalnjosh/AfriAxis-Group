from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.decorators import get_user_roles


def erp_home(request):
    if request.user.is_authenticated:
        return redirect("role_home")

    return redirect("/auth/login/")


@login_required
def role_home(request):
    user = request.user

    if user.is_superuser:
        return redirect("/dashboard/")

    roles = set(get_user_roles(user))

    # Management
    if roles.intersection(
        {
            "MD",
            "CEO",
            "GM",
        }
    ):
        return redirect("/dashboard/")

    # Finance / Accounts
    if roles.intersection(
        {
            "FINANCE",
            "ACCOUNTS",
            "AUDITOR",
        }
    ):
        return redirect("/dashboard/finance/")

    # Wi-Fi technician has a deliberately restricted landing page.
    if "WIFI_TECHNICIAN" in roles:
        return redirect("/services/")

    return redirect("/auth/login/")


@login_required
def profile(request):
    user = request.user

    profile_obj = getattr(
        user,
        "userprofile",
        None,
    )

    roles = list(get_user_roles(user))

    if roles:
        role_name = " / ".join(
            role.replace("_", " ").title()
            for role in roles
        )
    elif user.is_superuser:
        role_name = "System Administrator"
    elif profile_obj:
        role_name = profile_obj.get_role_display()
    else:
        role_name = "Staff"

    full_name = user.get_full_name().strip()

    if not full_name:
        full_name = user.username

    initials = "".join(
        part[0].upper()
        for part in full_name.split()
        if part
    )[:2]

    if not initials:
        initials = "A"

    context = {
        "profile_user": user,
        "profile_obj": profile_obj,
        "role_name": role_name,
        "full_name": full_name,
        "initials": initials,
    }

    return render(
        request,
        "accounts/profile.html",
        context,
    )
