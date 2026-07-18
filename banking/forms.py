from django import forms
from .models import BankStatementUpload


class BankStatementUploadForm(forms.ModelForm):
    class Meta:
        model = BankStatementUpload
        fields = ["bank_account", "template", "file"]