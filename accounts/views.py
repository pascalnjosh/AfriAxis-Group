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


@login_required
def profile(request):
    user = request.user

    profile_obj = getattr(
        user,
        "userprofile",
        None,
    )

    role_name = (
        profile_obj.get_role_display()
        if profile_obj
        else (
            "System Administrator"
            if user.is_superuser
            else "Staff"
        )
    )

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
