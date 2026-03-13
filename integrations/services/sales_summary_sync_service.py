from integrations.google.sheets_service import GoogleSheetsService
from integrations.smartup.services import SmartupService
from integrations.utils.currency import calculate_converted_total_usd
from integrations.utils.date_ranges import format_date_range_for_smartup
from integrations.utils.numbers import parse_number


class SalesSummarySyncService:
    def __init__(self) -> None:
        self.smartup = SmartupService()
        self.sheets = GoogleSheetsService()

    def sync_current_month(self) -> dict:
        date_from, date_to = format_date_range_for_smartup()

        data = self.smartup.get_sales_summary_report_data(
            date_from=date_from,
            date_to=date_to,
        )

        rates = self.smartup.get_trustbank_usd_rate()
        sell_rate = parse_number(rates.get("sell"))

        if sell_rate <= 0:
            raise ValueError("Invalid Trustbank sell rate")

        rows = self._build_rows(data=data, sell_rate=sell_rate)

        return self.sheets.update_sales_summary(rows)

    def _build_rows(self, data: dict, sell_rate: float) -> list[dict]:
        rows = []

        for row in data.get("rows", []):
            usd = parse_number(row.get("usd"))
            uzs = parse_number(row.get("uzs"))

            converted_total_usd = calculate_converted_total_usd(
                usd=usd,
                uzs=uzs,
                sell_rate=sell_rate,
            )

            rows.append({
                "sales_manager": row.get("sales_manager", ""),
                "usd": usd,
                "uzs": uzs,
                "converted_total_usd": converted_total_usd,
            })

        return rows