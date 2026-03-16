from integrations.google.sheets_service import GoogleSheetsService
from integrations.smartup.services import SmartupService
from integrations.utils.date_ranges import format_date_range_for_smartup
from integrations.utils.numbers import parse_number


class RevenueSyncService:
    def __init__(self):
        self.smartup = SmartupService()
        self.sheets = GoogleSheetsService()

    def sync_current_month(self):
        date_from, date_to = format_date_range_for_smartup()

        data = self.smartup.get_payment_report_data(
            date_from=date_from,
            date_to=date_to,
        )

        grouped = self._group_by_collector(data.get("rows", []))

        payload = []
        for collector, total_usd in grouped.items():
            payload.append({
                "collector": collector,
                "total_usd": total_usd,
            })

        return self.sheets.update_revenue_summary(payload)

    def _group_by_collector(self, rows):
        rates = self.smartup.get_trustbank_usd_rate()
        sell_rate = parse_number(rates.get("sell"))

        if sell_rate <= 0:
            raise ValueError("Invalid Trustbank sell rate")

        grouped = {}

        for row in rows:
            collector = (row.get("collector") or "").strip()
            currency = (row.get("currency") or "").strip().lower()
            amount = parse_number(row.get("amount"))

            if not collector:
                continue

            amount_usd = 0

            if "доллар" in currency:
                amount_usd = amount
            elif "сум" in currency:
                amount_usd = amount / sell_rate
            else:
                continue

            grouped.setdefault(collector, 0)
            grouped[collector] += amount_usd

        return grouped