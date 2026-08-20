from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def get_user_role(user):
    """
    Return the AfriAxis business role for a user.

    Superusers are treated as MD so that the system administrator
    always retains full ERP access.
    """
    if not user.is_authenticated:
        return None

    if user.is_superuser:
        return "MD"

    try:
        return user.userprofile.role
    except Exception:
        return None


def roles_required(*allowed_roles):
    """
    Allow access only to users whose UserProfile role is listed.

    Example:
        @roles_required("MD", "GM")
        def some_view(request):
            ...
    """
    def decorator(view_func):

        @login_required
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):

            role = get_user_role(request.user)

            if role not in allowed_roles:
                raise PermissionDenied(
                    "You do not have permission to access this AfriAxis module."
                )

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


def md_required(view_func):
    return roles_required("MD")(view_func)


def management_required(view_func):
    return roles_required("MD", "GM")(view_func)


def finance_required(view_func):
    return roles_required("MD", "GM", "ACCOUNTS")(view_func)


def operations_required(view_func):
    return roles_required("MD", "GM")(view_func)
