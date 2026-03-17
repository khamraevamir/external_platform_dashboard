import requests
from bs4 import BeautifulSoup
from django.conf import settings


class SmartupClient:
    DEFAULT_TIMEOUT = 30
    TRUSTBANK_RATES_URL = "https://trustbank.uz/ru/services/exchange-rates/"

    def __init__(self):
        self.base_url = settings.SMARTUP_BASE_URL
        self.login = settings.SMARTUP_API_LOGIN
        self.password = settings.SMARTUP_API_PASSWORD

        self.session = requests.Session()
        self.session.auth = (self.login, self.password)
        self.session.headers.update({
            "Content-Type": "application/json;charset=UTF-8",
        })

        self.session.cookies.set(
            "biruni_device_id",
            "E6DA26AB0A4ED1F795A5C25DC9B41752B231085C17E94DB75AC3B3FB5DC478C4; AMP_MKTG_8db086350f=JTdCJTdE; JSESSIONID=sx_app1~02AB06C47F53FB33D7D6CFEFEE654B7C; AMP_8db086350f=JTdCJTIyZGV2aWNlSWQlMjIlM0ElMjIzNmZlYTNiNy1mYjgwLTRjN2MtYTkxMC0yZmQyY2MxMmE2NTMlMjIlMkMlMjJ1c2VySWQlMjIlM0ElMjJ1c2VyXzQ1MTE5MzUlMjIlMkMlMjJzZXNzaW9uSWQlMjIlM0ExNzczNzQ2NDAxOTY2JTJDJTIyb3B0T3V0JTIyJTNBZmFsc2UlMkMlMjJsYXN0RXZlbnRUaW1lJTIyJTNBMTc3Mzc0NzAwNzMwNyUyQyUyMmxhc3RFdmVudElkJTIyJTNBNDU4JTJDJTIycGFnZUNvdW50ZXIlMjIlM0E0JTdE; _lrt=1773747007533",
            domain="smartup.online",
        )

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

    def get_trustbank_usd_rate(self):
        # response = requests.get(
        #     self.TRUSTBANK_RATES_URL,
        #     headers={"User-Agent": "Mozilla/5.0"},
        #     timeout=20,
        # )
        # response.raise_for_status()

        # soup = BeautifulSoup(response.text, "html.parser")
        # text = soup.get_text("\n", strip=True)
        # lines = [line.strip() for line in text.splitlines() if line.strip()]

        # usd_index = None
        # for i, line in enumerate(lines):
        #     if line == "USD":
        #         usd_index = i
        #         break

        # if usd_index is None:
        #     raise ValueError("USD rate not found on Trustbank page")

        # buy = lines[usd_index + 1]
        # sell = lines[usd_index + 2]
        # cb_rate = lines[usd_index + 3]

        # updated_at = None
        # for line in lines:
        #     if "покупка/продажа" in line.lower():
        #         updated_at = line
        #         break

        # return {
        #     "currency": "USD",
        #     "buy": buy,
        #     "sell": sell,
        #     "cb_rate": cb_rate,
        #     "updated_at": updated_at,
        #     "source": self.TRUSTBANK_RATES_URL,
        # }

        return {
            "currency": "USD",
            "buy": "buy",
            "sell": "12200",
            "cb_rate": "cb_rate",
            "updated_at": "updated_at",
            "source": "",
        }