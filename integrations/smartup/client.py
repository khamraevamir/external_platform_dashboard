import requests
from django.conf import settings


class SmartupClient:

    DEFAULT_TIMEOUT = 30
    
    def __init__(self):
        self.base_url = settings.SMARTUP_BASE_URL
        self.login = settings.SMARTUP_API_LOGIN
        self.password = settings.SMARTUP_API_PASSWORD

        self.session = requests.Session()
        self.session.auth = (self.login, self.password)
        self.session.headers.update({
            "Content-Type": "application/json;charset=UTF-8",
        })

    def post(self, endpoint: str, json_data=None):
        url = f"{self.base_url}{endpoint}"
        response = self.session.post(url, json=json_data, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def get(self, endpoint: str, params=None):
        url = f"{self.base_url}{endpoint}"
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.text

    def get_session_data(self):
        return self.post("/biruni/m:session", {})

    def run_report(self, params: dict):
        return self.get("/trade/rep/mbi/tdeal/order:run", params=params)