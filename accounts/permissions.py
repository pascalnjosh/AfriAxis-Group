from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


# AfriAxis ERP role codes
MD = "MD"
GM = "GM"
ACCOUNTS = "ACCOUNTS"


def get_user_role(user):
    """
    Return the AfriAxis role assigned to a user.
    Superusers are treated as MD-level administrators.
    """
    if not user or not user.is_authenticated:
        return None

    if user.is_superuser:
        return MD

    try:
        return user.userprofile.role
    except Exception:
        return None


def role_required(*allowed_roles):
    """
    Require authentication and one of the supplied AfriAxis roles.

    Superusers always pass.
    Authenticated users without an allowed role receive HTTP 403.
    """

    def decorator(view_func):

        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):

            user = request.user

            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())

            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            role = get_user_role(user)

            if role not in allowed_roles:
                raise PermissionDenied(
                    "You do not have permission to access this AfriAxis module."
                )

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


def md_required(view_func):
    return role_required(MD)(view_func)


def management_required(view_func):
    return role_required(MD, GM)(view_func)


def finance_required(view_func):
    return role_required(MD, GM, ACCOUNTS)(view_func)


def operations_required(view_func):
    return role_required(MD, GM)(view_func)
