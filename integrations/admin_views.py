from datetime import datetime
import calendar
from decimal import Decimal, InvalidOperation

from django.template.response import TemplateResponse

from integrations.smartup.services import SmartupService


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

                total_usd = to_decimal(data.get("totals", {}).get("usd"))
                total_uzs = to_decimal(data.get("totals", {}).get("uzs"))
                converted_grand_total = total_usd + (total_uzs / sell_rate)

                data["totals"]["converted_total_usd"] = format_decimal(converted_grand_total, 2)
            else:
                for row in data.get("rows", []):
                    row["converted_total_usd"] = "—"
                if data and "totals" in data:
                    data["totals"]["converted_total_usd"] = "—"
        else:
            for row in data.get("rows", []):
                row["converted_total_usd"] = "—"
            if data and "totals" in data:
                data["totals"]["converted_total_usd"] = "—"

    except Exception as e:
        error = str(e)

    context = {
        **admin_site.each_context(request),
        "title": "Сводка продаж",
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
    context = {
        **admin_site.each_context(request),
        "title": "Выручка",
    }

    return TemplateResponse(
        request,
        "admin/revenue.html",
        context,
    )