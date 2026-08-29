from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from accounts.models import CompanyAssignment


# ---------------------------------------------------------------------
# ROLE HELPERS
# ---------------------------------------------------------------------

def get_user_roles(user):
    """
    Return active AfriAxis business roles assigned to a user.

    CompanyAssignment is the authoritative role source.

    UserProfile.role remains only as a legacy fallback when the user
    has no active CompanyAssignment records.

    Superusers retain unrestricted ERP administration access.
    """

    if not user.is_authenticated:
        return set()

    if user.is_superuser:
        return {"MD", "CEO"}

    all_assignments = CompanyAssignment.objects.filter(
        user=user,
    )

    active_assignments = all_assignments.filter(
        active=True,
    )

    roles = set(
        active_assignments
        .exclude(role__isnull=True)
        .exclude(role="")
        .values_list("role", flat=True)
    )

    # CompanyAssignment becomes authoritative as soon as a user
    # has at least one assignment record.
    #
    # This is security-critical: if every assignment is disabled,
    # the legacy UserProfile role must NOT silently restore access.
    if all_assignments.exists():
        return roles

    # Legacy fallback is only for users that have never been
    # migrated to CompanyAssignment.
    try:
        profile_role = user.userprofile.role

        if profile_role:
            roles.add(profile_role)

    except Exception:
        pass

    return roles


def get_user_role(user):
    """
    Backward-compatible helper for code expecting one role.
    """

    roles = get_user_roles(user)

    role_priority = (
        "MD",
        "CEO",
        "GM",
        "MANAGER",
        "SUPERVISOR",
        "FINANCE",
        "ACCOUNTS",
        "AUDITOR",
        "WIFI_TECHNICIAN",
    )

    for role in role_priority:
        if role in roles:
            return role

    return next(iter(roles), None)


# ---------------------------------------------------------------------
# COMPANY ACCESS HELPERS
# ---------------------------------------------------------------------

def get_user_company_ids(user):
    """
    Return company IDs the user may access.

    Superusers return None, meaning unrestricted company access.
    """

    if not user.is_authenticated:
        return set()

    if user.is_superuser:
        return None

    return set(
        CompanyAssignment.objects.filter(
            user=user,
            active=True,
        ).values_list(
            "company_id",
            flat=True,
        )
    )


def get_user_companies(user):
    """
    Return active CompanyAssignment rows for the user.

    Superusers receive all active assignments. Company-level query
    helpers should normally use get_user_company_ids().
    """

    qs = CompanyAssignment.objects.select_related(
        "company",
        "branch",
        "department",
    ).filter(
        active=True,
    )

    if user.is_superuser:
        return qs

    return qs.filter(
        user=user,
    )


def user_has_company_access(user, company):
    """
    Return True when user may access the supplied company.
    """

    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    company_id = getattr(
        company,
        "pk",
        company,
    )

    if not company_id:
        return False

    return CompanyAssignment.objects.filter(
        user=user,
        company_id=company_id,
        active=True,
    ).exists()


def require_company_access(user, company):
    """
    Raise PermissionDenied when the user has no active assignment
    for the supplied company.
    """

    if not user_has_company_access(
        user,
        company,
    ):
        raise PermissionDenied(
            "You do not have access to this company."
        )

    return True


def scope_queryset_by_company(
    queryset,
    user,
    company_field="company",
):
    """
    Restrict a queryset to companies assigned to the user.

    company_field may traverse relations, for example:

        warehouse__company
        sales_order__company
        purchase_order__company
        apartment__company

    Superusers receive the original queryset.
    """

    if not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    company_ids = get_user_company_ids(user)

    if not company_ids:
        return queryset.none()

    lookup = (
        f"{company_field}__in"
    )

    return queryset.filter(
        **{
            lookup: company_ids,
        }
    )


# ---------------------------------------------------------------------
# ROLE DECORATORS
# ---------------------------------------------------------------------

def roles_required(*allowed_roles):
    """
    Allow access when the user has at least one permitted active
    AfriAxis business role.
    """

    allowed_roles = set(
        allowed_roles
    )

    def decorator(view_func):

        @login_required
        @wraps(view_func)
        def wrapped_view(
            request,
            *args,
            **kwargs,
        ):

            user_roles = get_user_roles(
                request.user
            )

            if not user_roles.intersection(
                allowed_roles
            ):
                raise PermissionDenied(
                    "You do not have permission to access "
                    "this AfriAxis module."
                )

            return view_func(
                request,
                *args,
                **kwargs,
            )

        return wrapped_view

    return decorator


def md_required(view_func):
    return roles_required(
        "MD",
    )(view_func)


def management_required(view_func):
    return roles_required(
        "MD",
        "CEO",
        "GM",
    )(view_func)


def finance_required(view_func):
    return roles_required(
        "MD",
        "CEO",
        "GM",
        "FINANCE",
        "ACCOUNTS",
    )(view_func)


def operations_required(view_func):
    return roles_required(
        "MD",
        "CEO",
        "GM",
    )(view_func)


def audit_required(view_func):
    return roles_required(
        "MD",
        "CEO",
        "GM",
        "FINANCE",
        "ACCOUNTS",
        "AUDITOR",
    )(view_func)

