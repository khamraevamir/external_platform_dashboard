from datetime import datetime
import calendar

from django.core.management.base import BaseCommand

from integrations.google.sheets_service import GoogleSheetsService
from integrations.smartup.services import SmartupService


def parse_number(value):
    if value in (None, "", "-"):
        return 0.0

    value = str(value).strip()
    value = value.replace("\xa0", "")
    value = value.replace(" ", "")
    value = value.replace(",", ".")

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class Command(BaseCommand):
    help = "Update current month Google Sheet with Smartup sales summary"

    def handle(self, *args, **options):
        service = SmartupService()

        today = datetime.today()
        first_day = today.replace(day=1)
        last_day_num = calendar.monthrange(today.year, today.month)[1]
        last_day = today.replace(day=last_day_num)

        date_from = first_day.strftime("%d.%m.%Y")
        date_to = last_day.strftime("%d.%m.%Y")

        data = service.get_sales_summary_report_data(
            date_from=date_from,
            date_to=date_to,
        )

        rates = service.get_trustbank_usd_rate()
        sell_rate = parse_number(rates.get("sell"))

        if sell_rate <= 0:
            self.stderr.write("Invalid Trustbank sell rate")
            return

        rows = []

        for row in data.get("rows", []):
            usd = parse_number(row.get("usd"))
            uzs = parse_number(row.get("uzs"))

            converted_total_usd = usd + (uzs / sell_rate)

            rows.append({
                "sales_manager": row.get("sales_manager", ""),
                "usd": usd,
                "uzs": uzs,
                "converted_total_usd": round(converted_total_usd, 2),
            })

        sheets_service = GoogleSheetsService()

        result = sheets_service.update_sales_summary(rows)
        self.stdout.write(self.style.SUCCESS(str(result)))