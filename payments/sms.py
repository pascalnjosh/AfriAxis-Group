import requests

def send_sms(phone, message):
    print(f"Sending SMS to {phone}: {message}")

    # Later we plug in a real SMS API like Africa's Talking or Twilio
