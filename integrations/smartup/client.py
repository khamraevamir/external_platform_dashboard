from http.cookies import SimpleCookie

import requests
from bs4 import BeautifulSoup
from django.conf import settings


class SmartupClient:
    DEFAULT_TIMEOUT = 30
    BOOTSTRAP_PATHS = ("", "/trade")
    TRUSTBANK_RATES_URL = "https://trustbank.uz/ru/services/exchange-rates/"

    def __init__(self):
        self.base_url = str(settings.SMARTUP_BASE_URL or "").strip().rstrip("/")
        self.login = settings.SMARTUP_API_LOGIN
        self.password = settings.SMARTUP_API_PASSWORD

        self.session = requests.Session()
        self.session.auth = (self.login, self.password)
        self.session.headers.update({
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
        })
        self._session_bootstrapped = False
        self._apply_configured_session_cookie()

    def get_session_debug_data(self):
        data = self.get_session_data()

        return {
            "session_data": data,
            "cookies": self.session.cookies.get_dict(),
        }

    def post(self, endpoint: str, json_data=None):
        self._bootstrap_session()
        url = f"{self.base_url}{endpoint}"
        response = self.session.post(
            url,
            json=json_data,
            timeout=self.DEFAULT_TIMEOUT,
        )
        self._raise_for_status_with_details(response)
        return response.json()

    def get(self, endpoint: str, params=None):
        self._bootstrap_session()
        url = f"{self.base_url}{endpoint}"
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        self._raise_for_status_with_details(response)
        return response.text

    def _bootstrap_session(self):
        if self._session_bootstrapped:
            return

        for path in self.BOOTSTRAP_PATHS:
            url = f"{self.base_url}{path}"
            try:
                self.session.get(url, timeout=self.DEFAULT_TIMEOUT, allow_redirects=True)
            except requests.RequestException:
                continue

        self._session_bootstrapped = True

    def _apply_configured_session_cookie(self):
        raw_cookie = str(getattr(settings, "SMARTUP_SESSION_COOKIE", "") or "").strip()
        if not raw_cookie:
            return

        cookie = SimpleCookie()
        cookie.load(raw_cookie)

        for morsel in cookie.values():
            self.session.cookies.set(
                morsel.key,
                morsel.value,
                domain="smartup.online",
            )

    def _raise_for_status_with_details(self, response):
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            body = (response.text or "").strip()
            if len(body) > 600:
                body = body[:600] + "..."

            message = (
                f"{exc}. Response body: {body or '<empty>'}"
            )
            raise requests.HTTPError(message, response=response) from exc

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
            "sell": "12190",
            "cb_rate": "cb_rate",
            "updated_at": "updated_at",
            "source": "",
        }
