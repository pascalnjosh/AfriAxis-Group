from enterprise.models import Branch, Company, DocumentSequence


def get_document_reference(
    document_type,
    company_name="AfriAxis Group",
    branch_code="HQ",
):
    company = Company.objects.get(
        name=company_name,
        active=True,
    )

    branch = Branch.objects.get(
        company=company,
        code=branch_code,
        active=True,
    )

    sequence = DocumentSequence.objects.get(
        company=company,
        branch=branch,
        document_type=document_type,
        active=True,
    )

    return sequence.next_reference()


def get_invoice_reference(
    company_name="AfriAxis Group",
    branch_code="HQ",
):
    return get_document_reference(
        document_type="INVOICE",
        company_name=company_name,
        branch_code=branch_code,
    )
