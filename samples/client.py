import requests
import logging

class AvitoClient:
    AUTH_URL = "https://api.avito.ru/token"
    API_BASE_URL = "https://api.avito.ru"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.user_id = None

    def authenticate(self):
        response = requests.post(
            self.AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
        )
        response.raise_for_status()
        self.access_token = response.json()['access_token']
        logging.info("Authenticated with Avito API")

    def get_headers(self):
        if not self.access_token:
            self.authenticate()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def get_self_user_id(self):
        if self.user_id:
            return self.user_id
        url = f"{self.API_BASE_URL}/core/v1/accounts/self"
        response = requests.get(url, headers=self.get_headers())
        response.raise_for_status()
        self.user_id = response.json()['id']
        logging.info(f"Retrieved Avito user_id: {self.user_id}")
        return self.user_id

    def fetch_new_messages(self):
        user_id = self.get_self_user_id()
        url = f"{self.API_BASE_URL}/messenger/v2/accounts/{user_id}/chats"
        params = {"unread_only": "true"}
        response = requests.get(url, headers=self.get_headers(), params=params)
        response.raise_for_status()
        return response.json()['chats']

    def send_message(self, chat_id: str, text: str):
        user_id = self.get_self_user_id()
        url = f"{self.API_BASE_URL}/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages"
        payload = {"message": {"text": text}, "type": "text"}
        response = requests.post(url, json=payload, headers=self.get_headers())
        response.raise_for_status()
        return response.json()

    def mark_chat_as_read(self, chat_id: str):
        user_id = self.get_self_user_id()
        url = f"{self.API_BASE_URL}/messenger/v1/accounts/{user_id}/chats/{chat_id}/read"
        response = requests.post(url, headers=self.get_headers())
        response.raise_for_status()
        return response.json()