import logging

logger = logging.getLogger(__name__)

class ConsoleSMSBackend:
    """SMS бэкенд для разработки - выводит в консоль"""
    
    def send(self, phone_number, message):
        logger.info(f"[SMS] To: {phone_number}, Message: {message}")
        return True

class TwilioSMSBackend:
    """SMS бэкенд для Twilio"""
    
    def __init__(self, account_sid, auth_token, from_number):
        from twilio.rest import Client
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number
    
    def send(self, phone_number, message):
        try:
            self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=phone_number
            )
            return True
        except Exception as e:
            logger.error(f"Twilio SMS error: {str(e)}")
            return False

class SmsRuBackend:
    """SMS бэкенд для SMS.ru"""
    
    def __init__(self, api_id, from_number=None):
        self.api_id = api_id
        self.from_number = from_number
    
    def send(self, phone_number, message):
        import requests
        url = "https://sms.ru/sms/send"
        params = {
            "api_id": self.api_id,
            "to": phone_number,
            "msg": message,
            "json": 1
        }
        if self.from_number:
            params["from"] = self.from_number
        
        try:
            response = requests.post(url, data=params)
            result = response.json()
            return result.get("status") == "OK"
        except Exception as e:
            logger.error(f"SMS.ru error: {str(e)}")
            return False
