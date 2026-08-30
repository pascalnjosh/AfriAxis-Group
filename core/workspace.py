"""
AfriAxis V7 professional workspace identity.

Presentation only.
Does not alter company permissions, accounting, inventory,
rent, manufacturing, banking or transactional data.
"""

from accounts.models import CompanyAssignment


GROUP_NAME = "AFRIAXIS GROUP"
GROUP_SUBTITLE = "Group Executive Workspace"

AFRICORE_NAME = "AFRICORE HEIGHTS"
AFRICORE_SUBTITLE = "Property & Rental Management Workspace"

FAIRLANE_NAME = "FAIRLANE AGRISERVICE AND SUPPLIERS (FAS)"
FAIRLANE_SUBTITLE = "Agriculture & Manufacturing Workspace"


def _company_identity(name):
    value = (name or "").strip().upper()

    if "FAIRLANE" in value:
        return {
            "workspace_code": "FAS",
            "workspace_name": FAIRLANE_NAME,
            "workspace_short_name": "FAIRLANE",
            "workspace_subtitle": FAIRLANE_SUBTITLE,
            "workspace_type": "fairlane",
            "workspace_department": "Agriculture · Manufacturing · Sales",
        }

    if "AFRICORE" in value:
        return {
            "workspace_code": "AFRICORE",
            "workspace_name": AFRICORE_NAME,
            "workspace_short_name": "AFRICORE HEIGHTS",
            "workspace_subtitle": AFRICORE_SUBTITLE,
            "workspace_type": "africore",
            "workspace_department": "Property · Rent · Water · Wi-Fi",
        }

    return {
        "workspace_code": "AFRIAXIS",
        "workspace_name": GROUP_NAME,
        "workspace_short_name": "AFRIAXIS GROUP",
        "workspace_subtitle": GROUP_SUBTITLE,
        "workspace_type": "group",
        "workspace_department": "Executive Intelligence · Finance · Governance",
    }


def _path_identity(path):
    path = (path or "").lower()

    # Fairlane operating modules
    fairlane_prefixes = (
        "/manufacturing/",
        "/inventory/",
        "/sales/",
        "/purchasing/",
        "/procurement/",
    )

    # Africore operating modules
    africore_prefixes = (
        "/rentals/",
        "/billing/",
        "/payments/",
        "/services/",
        "/communications/",
        "/water/",
    )

    if path.startswith(fairlane_prefixes):
        return _company_identity("FAIRLANE")

    if path.startswith(africore_prefixes):
        return _company_identity("AFRICORE")

    return _company_identity("AFRIAXIS")


def workspace_context(request):
    """
    Resolve the clearest workspace identity for the logged-in user.

    Priority:
    1. User with exactly one active company assignment -> that company.
    2. Multi-company / superuser -> module-aware workspace.
    3. Anonymous -> AfriAxis Group.
    """

    user = getattr(request, "user", None)

    context = _path_identity(
        getattr(request, "path", "")
    )

    context.update(
        {
            "workspace_role": "",
            "workspace_job_title": "",
            "workspace_company_count": 0,
        }
    )

    if not user or not user.is_authenticated:
        return context

    assignments = (
        CompanyAssignment.objects
        .filter(
            user=user,
            active=True,
        )
        .select_related(
            "company",
        )
        .order_by(
            "company__name",
        )
    )

    assignment_count = assignments.count()

    context["workspace_company_count"] = assignment_count

    # A staff member assigned to one company should always see
    # that company's identity, regardless of the URL module.
    if assignment_count == 1:
        assignment = assignments.first()

        context.update(
            _company_identity(
                assignment.company.name
            )
        )

        try:
            context["workspace_role"] = (
                assignment.get_role_display()
            )
        except Exception:
            context["workspace_role"] = (
                assignment.role or ""
            )

        context["workspace_job_title"] = (
            assignment.job_title or ""
        )

        return context

    # Multi-company executives retain module-aware workspace identity.
    if assignment_count:
        roles = []

        for assignment in assignments:
            try:
                role = assignment.get_role_display()
            except Exception:
                role = assignment.role

            if role and role not in roles:
                roles.append(role)

        context["workspace_role"] = " · ".join(
            roles[:3]
        )

    elif getattr(user, "is_superuser", False):
        context["workspace_role"] = (
            "System & Group Administration"
        )

    return context
