from datetime import datetime
import calendar
from decimal import Decimal, InvalidOperation

from django.template.response import TemplateResponse

from integrations.smartup.services import SmartupService
from integrations.smartup.parsers.route_analysis_parser import RouteAnalysisParser
from integrations.google.sheets_service import GoogleSheetsService


def to_decimal(value):
    if value in (None, "", "—"):
        return Decimal("0")

    cleaned = str(value).replace(" ", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def format_decimal(value, places=2):
    quant = Decimal("1") if places == 0 else Decimal("1." + ("0" * places))
    return f"{value.quantize(quant):,}".replace(",", " ")


def format_percent(value, places=0):
    value = Decimal(value)
    quant = Decimal("1") if places == 0 else Decimal("1." + ("0" * places))
    return f"{value.quantize(quant)}"


def progress_color_from_percent(percent_int: int) -> str:
    if percent_int >= 81:
        return "green"
    if percent_int >= 71:
        return "orange"
    return "red"


def build_revenue_summary(rows, sell_rate):
    summary = {}

    for row in rows:
        collector = (row.get("collector") or "").strip()
        currency = (row.get("currency") or "").strip().lower()
        amount = to_decimal(row.get("amount"))

        if not collector:
            collector = "Не указан"

        amount_usd = Decimal("0")

        if "доллар" in currency:
            amount_usd = amount
        elif "сум" in currency:
            if sell_rate > 0:
                amount_usd = amount / sell_rate

        if collector not in summary:
            summary[collector] = Decimal("0")

        summary[collector] += amount_usd

    result_rows = [
        {
            "collector": collector,
            "total_usd": format_decimal(total, 2),
            "_sort_total": total,
        }
        for collector, total in summary.items()
    ]

    result_rows.sort(key=lambda item: item["_sort_total"], reverse=True)

    grand_total = sum((item["_sort_total"] for item in result_rows), Decimal("0"))

    for item in result_rows:
        item.pop("_sort_total", None)

    return {
        "rows": result_rows,
        "totals": {
            "collector": "ИТОГО",
            "total_usd": format_decimal(grand_total, 2),
        },
    }


def sales_summary_view(request, admin_site):
    date_from_input = request.GET.get("date_from", "")
    date_to_input = request.GET.get("date_to", "")

    data = None
    rates = None
    error = None

    service = SmartupService()

    try:
        if date_from_input and date_to_input:
            date_from = datetime.strptime(
                date_from_input,
                "%Y-%m-%d"
            ).strftime("%d.%m.%Y")

            date_to = datetime.strptime(
                date_to_input,
                "%Y-%m-%d"
            ).strftime("%d.%m.%Y")
        else:
            today = datetime.today()
            first_day = today.replace(day=1)

            last_day_num = calendar.monthrange(
                today.year,
                today.month
            )[1]
            last_day = today.replace(day=last_day_num)

            date_from_input = first_day.strftime("%Y-%m-%d")
            date_to_input = last_day.strftime("%Y-%m-%d")

            date_from = first_day.strftime("%d.%m.%Y")
            date_to = last_day.strftime("%d.%m.%Y")

        data = service.get_sales_summary_report_data(
            date_from=date_from,
            date_to=date_to,
        )
        sheets_service = GoogleSheetsService()
        sales_plan_map = sheets_service.get_sales_plan_map()

        try:
            rates = service.get_trustbank_usd_rate()
        except Exception:
            rates = None

        if rates and rates.get("sell"):
            sell_rate = to_decimal(rates["sell"])

            if sell_rate > 0:
                for row in data.get("rows", []):
                    usd = to_decimal(row.get("usd"))
                    uzs = to_decimal(row.get("uzs"))
                    converted_total_usd = usd + (uzs / sell_rate)

                    row["converted_total_usd"] = format_decimal(converted_total_usd, 2)

                    short_name = GoogleSheetsService().normalize_short_name(
                        row.get("sales_manager")
                    )
                    plan_value = sales_plan_map.get(short_name, 0)
                    plan_decimal = to_decimal(plan_value)
                    row["plan"] = format_decimal(plan_decimal, 0)

                    if plan_decimal > 0:
                        progress_percent = (converted_total_usd / plan_decimal) * Decimal("100")
                        row["progress_percent"] = format_percent(progress_percent, 0)
                        clamped = max(0, min(100, int(progress_percent)))
                        row["progress_percent_clamped"] = clamped
                        row["progress_color"] = progress_color_from_percent(clamped)
                        row["percent"] = int(progress_percent)
                    else:
                        row["progress_percent"] = "—"
                        row["progress_percent_clamped"] = 0
                        row["progress_color"] = "red"
                        row["percent"] = 0

                total_plan = sum(sales_plan_map.get(
                    sheets_service.normalize_short_name(row.get("sales_manager")), 0
                ) for row in data.get("rows", []))

                total_plan_decimal = to_decimal(total_plan)
                data["totals"]["plan"] = format_decimal(total_plan_decimal, 0)

                total_usd = to_decimal(data.get("totals", {}).get("usd"))
                total_uzs = to_decimal(data.get("totals", {}).get("uzs"))
                converted_grand_total = total_usd + (total_uzs / sell_rate)

                data["totals"]["converted_total_usd"] = format_decimal(converted_grand_total, 2)

                if total_plan_decimal > 0:
                    totals_progress_percent = (converted_grand_total / total_plan_decimal) * Decimal("100")
                    data["totals"]["progress_percent"] = format_percent(totals_progress_percent, 0)
                    totals_clamped = max(0, min(100, int(totals_progress_percent)))
                    data["totals"]["progress_percent_clamped"] = totals_clamped
                    data["totals"]["progress_color"] = progress_color_from_percent(totals_clamped)
                else:
                    data["totals"]["progress_percent"] = "—"
                    data["totals"]["progress_percent_clamped"] = 0
                    data["totals"]["progress_color"] = "red"
            else:
                for row in data.get("rows", []):
                    row["converted_total_usd"] = "—"
                    row["progress_percent"] = "—"
                    row["progress_percent_clamped"] = 0
                    row["progress_color"] = "red"
                    row["percent"] = 0
                if data and "totals" in data:
                    data["totals"]["converted_total_usd"] = "—"
                    data["totals"]["progress_percent"] = "—"
                    data["totals"]["progress_percent_clamped"] = 0
                    data["totals"]["progress_color"] = "red"
        else:
            for row in data.get("rows", []):
                row["converted_total_usd"] = "—"
                row["progress_percent"] = "—"
                row["progress_percent_clamped"] = 0
                row["progress_color"] = "red"
                row["percent"] = 0
            if data and "totals" in data:
                data["totals"]["converted_total_usd"] = "—"
                data["totals"]["progress_percent"] = "—"
                data["totals"]["progress_percent_clamped"] = 0
                data["totals"]["progress_color"] = "red"

    except Exception as e:
        error = str(e)

    context = {
        **admin_site.each_context(request),
        "title": "Продажа",
        "data": data,
        "rates": rates,
        "error": error,
        "date_from_input": date_from_input,
        "date_to_input": date_to_input,
    }

    return TemplateResponse(
        request,
        "admin/sales_summary.html",
        context,
    )


def revenue_view(request, admin_site):
    date_from_input = request.GET.get("date_from", "")
    date_to_input = request.GET.get("date_to", "")

    data = None
    rates = None
    error = None

    service = SmartupService()

    try:
        if date_from_input and date_to_input:
            date_from = datetime.strptime(
                date_from_input,
                "%Y-%m-%d"
            ).strftime("%d.%m.%Y")

            date_to = datetime.strptime(
                date_to_input,
                "%Y-%m-%d"
            ).strftime("%d.%m.%Y")
        else:
            today = datetime.today()
            first_day = today.replace(day=1)

            last_day_num = calendar.monthrange(
                today.year,
                today.month
            )[1]
            last_day = today.replace(day=last_day_num)

            date_from_input = first_day.strftime("%Y-%m-%d")
            date_to_input = last_day.strftime("%Y-%m-%d")

            date_from = first_day.strftime("%d.%m.%Y")
            date_to = last_day.strftime("%d.%m.%Y")

        raw_data = service.get_payment_report_data(
            date_from=date_from,
            date_to=date_to,
        )

        rates = service.get_trustbank_usd_rate()
        sell_rate = to_decimal(rates.get("sell"))

        if sell_rate <= 0:
            raise ValueError("Некорректный курс продажи Trustbank")

        summary = build_revenue_summary(
            rows=raw_data.get("rows", []),
            sell_rate=sell_rate,
        )

        data = {
            "title": raw_data.get("title"),
            "columns": ["Инкассатор", "Итог в USD"],
            "rows": summary["rows"],
            "totals": summary["totals"],
        }

    except Exception as e:
        error = str(e)

    context = {
        **admin_site.each_context(request),
        "title": "Выручка",
        "data": data,
        "rates": rates,
        "error": error,
        "date_from_input": date_from_input,
        "date_to_input": date_to_input,
    }

    return TemplateResponse(
        request,
        "admin/revenue.html",
        context,
    )


def get_route_analysis_report(self, date_from: str, date_to: str) -> dict:
        context = self._get_session_context()

        params = {
            "rt": "html",
            "url": "/trade/rep/route_analysis:run_redirect",
            "begin_date": date_from,
            "end_date": date_to,
            "person_group_id": "",
            "person_kind": "",
            "report_state": "A",
            "show_mml": "Y",
            "mml_type": "P",
            "show_mml_to_sku": "N",
            "-project_code": context["project_code"],
            "-project_hash": context["project_hash"],
            "-filial_id": context["filial_id"],
            "-user_id": context["user_id"],
            "-lang_code": context["lang_code"],
        }
        print("ROUTE ANALYSIS PARAMS:", params)
        html = self.client.get(ROUTE_ANALYSIS_REPORT_PATH, params=params)

        return {
            "date_from": date_from,
            "date_to": date_to,
            "html": html,
        }

def get_route_analysis_report_data(self, date_from: str, date_to: str) -> dict:
    report = self.get_route_analysis_report(
        date_from=date_from,
        date_to=date_to,
    )

    parsed = RouteAnalysisParser.parse(report["html"])

    return {
        "date_from": report["date_from"],
        "date_to": report["date_to"],
        "title": parsed["title"],
        "rows": parsed["rows"],
    }    


def attendance_view(request, admin_site):
    date_from_input = request.GET.get("date_from", "")
    date_to_input = request.GET.get("date_to", "")

    data = None
    error = None

    service = SmartupService()

    try:
        if date_from_input and date_to_input:
            date_from = datetime.strptime(
                date_from_input,
                "%Y-%m-%d"
            ).strftime("%d.%m.%Y")

            date_to = datetime.strptime(
                date_to_input,
                "%Y-%m-%d"
            ).strftime("%d.%m.%Y")
        else:
            today = datetime.today()
            first_day = today.replace(day=1)

            last_day_num = calendar.monthrange(
                today.year,
                today.month
            )[1]
            last_day = today.replace(day=last_day_num)

            date_from_input = first_day.strftime("%Y-%m-%d")
            date_to_input = last_day.strftime("%Y-%m-%d")

            date_from = first_day.strftime("%d.%m.%Y")
            date_to = last_day.strftime("%d.%m.%Y")

        raw_data = service.get_route_analysis_report_data(
            date_from=date_from,
            date_to=date_to,
        )

        summary = build_visit_summary(raw_data.get("rows", []))

        data = {
            "title": raw_data.get("title") or "Посещаемость",
            "columns": ["Штат", "P", "PD", "Итого"],
            "rows": summary["rows"],
            "totals": summary["totals"],
        }

    except Exception as e:
        error = str(e)

    context = {
        **admin_site.each_context(request),
        "title": "Посещаемость",
        "data": data,
        "error": error,
        "date_from_input": date_from_input,
        "date_to_input": date_to_input,
    }

    return TemplateResponse(
        request,
        "admin/attendance.html",
        context,
    )