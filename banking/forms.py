from django import forms

from .models import BankStatementUpload


class BankStatementUploadForm(forms.ModelForm):

    class Meta:
        model = BankStatementUpload
        fields = [
            "bank_account",
            "template",
            "file",
        ]

        labels = {
            "bank_account": "Bank / Purpose / Account Number",
            "template": "Statement Format",
            "file": "Bank Statement File",
        }

        help_texts = {
            "bank_account": (
                "Confirm the bank, purpose and full account "
                "number before uploading."
            ),
        }

        widgets = {
            "file": forms.ClearableFileInput(
                attrs={
                    "accept": ".csv,.xlsx,.xls",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields[
            "bank_account"
        ].label_from_instance = self.bank_account_label

    @staticmethod
    def bank_account_label(account):
        purpose = (
            account.get_purpose_display()
            if hasattr(account, "get_purpose_display")
            else account.purpose
        )

        return (
            f"{account.bank_name} — "
            f"{str(purpose).upper()} — "
            f"{account.account_number}"
        )
