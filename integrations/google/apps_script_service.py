import requests
from django.conf import settings


class GoogleAppsScriptService:
    def __init__(self):
        self.url = settings.GOOGLE_APPS_SCRIPT_URL

    def send_sales_summary(self, rows):
        payload = [
            {
                "sales_manager": row["sales_manager"],
                "converted_total_usd": row["converted_total_usd"],
            }
            for row in rows
        ]

        response = requests.post(
            self.url,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()