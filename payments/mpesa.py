import base64
import requests
from datetime import datetime
from django.conf import settings


class MpesaClient:
    def __init__(self):
        self.base_url = settings.MPESA_BASE_URL
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.shortcode = settings.MPESA_SHORTCODE
        self.passkey = settings.MPESA_PASSKEY
        self.callback_url = settings.MPESA_CALLBACK_URL

    def get_access_token(self):
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        raw = f"{self.consumer_key}:{self.consumer_secret}"
        auth = base64.b64encode(raw.encode()).decode()

        response = requests.get(
            url,
            headers={"Authorization": f"Basic {auth}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def stk_push(self, phone_number, amount, account_reference, transaction_desc):
        token = self.get_access_token()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        password_raw = f"{self.shortcode}{self.passkey}{timestamp}"
        password = base64.b64encode(password_raw.encode()).decode()

        url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"

        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone_number,
            "PartyB": self.shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": self.callback_url,
            "AccountReference": account_reference,
            "TransactionDesc": transaction_desc,
        }

        response = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
