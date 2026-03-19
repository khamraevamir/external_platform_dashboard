from decimal import Decimal, InvalidOperation

from django.urls import path
from unfold.sites import UnfoldAdminSite

from integrations.admin_views import (
    get_attendance_context_data,
    attendance_view,
    get_month_sheet_name,
    get_position_map_cached,
    get_revenue_context_data,
    get_sales_summary_context_data,
    normalize_short_name,
    revenue_view,
    sales_summary_view,
)


def _to_decimal_safe(value) -> Decimal:
    if value in (None, "", "—"):
        return Decimal("0")

    cleaned = str(value).replace(" ", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _format_decimal(value: Decimal, places: int = 0) -> str:
    quant = Decimal("1") if places == 0 else Decimal("1." + ("0" * places))
    return f"{value.quantize(quant):,}".replace(",", " ")


class CustomAdminSite(UnfoldAdminSite):
    site_header = "Admin"
    site_title = "Admin"
    index_title = "Главная"
    index_template = "dashboard.html"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        dashboard_month_label = get_month_sheet_name().replace("_", " ")

        dashboard_errors = []

        try:
            sales_ctx = get_sales_summary_context_data(
                date_from_input=request.GET.get("date_from", ""),
                date_to_input=request.GET.get("date_to", ""),
            )
        except Exception as e:
            sales_ctx = {}
            dashboard_errors.append(f"Продажа: {e}")

        try:
            revenue_ctx = get_revenue_context_data(
                date_from_input=request.GET.get("date_from", ""),
                date_to_input=request.GET.get("date_to", ""),
            )
        except Exception as e:
            revenue_ctx = {}
            dashboard_errors.append(f"Выручка: {e}")

        try:
            attendance_ctx = get_attendance_context_data(
                date_from_input=request.GET.get("date_from", ""),
                date_to_input=request.GET.get("date_to", ""),
            )
        except Exception as e:
            attendance_ctx = {}
            dashboard_errors.append(f"Посещаемость: {e}")

        sales_data = sales_ctx.get("data") or {}
        revenue_data = revenue_ctx.get("data") or {}
        attendance_data = attendance_ctx.get("data") or {}

        sales_rows = sales_data.get("rows") or []
        revenue_rows = revenue_data.get("rows") or []
        sales_totals = sales_data.get("totals") or {}
        revenue_totals = revenue_data.get("totals") or {}
        attendance_rows = attendance_data.get("rows") or []
        attendance_totals = attendance_data.get("totals") or {}

        position_map = {}

        try:
            position_map = get_position_map_cached()
        except Exception as e:
            dashboard_errors.append(f"Google Sheet (должности): {e}")

        def is_tp(name) -> bool:
            short_name = normalize_short_name(name)
            position = str(position_map.get(short_name, "")).lower().strip()

            return "тп" in position or "торгов" in position

        # Только ТП для dashboard
        sales_rows_tp = [
            row for row in sales_rows
            if is_tp(row.get("sales_manager"))
        ]

        revenue_rows_tp = [
            row for row in revenue_rows
            if is_tp(row.get("collector"))
        ]

        sales_plan = sum(
            (_to_decimal_safe(row.get("plan")) for row in sales_rows_tp),
            Decimal("0"),
        )
        sales_fact = sum(
            (_to_decimal_safe(row.get("converted_total_usd")) for row in sales_rows_tp),
            Decimal("0"),
        )

        revenue_plan = sum(
            (_to_decimal_safe(row.get("plan")) for row in revenue_rows_tp),
            Decimal("0"),
        )
        revenue_fact = sum(
            (_to_decimal_safe(row.get("total_usd")) for row in revenue_rows_tp),
            Decimal("0"),
        )

        sales_top = sales_rows_tp[:5]
        revenue_top = revenue_rows_tp[:5]

        extra_context.update(
            {
                "dashboard_sales": {
                    "overall_totals": {
                        "plan": sales_totals.get("plan", "0"),
                        "converted_total_usd": sales_totals.get("converted_total_usd", "0"),
                    },
                    "rows": sales_rows_tp,
                    "tp_totals": {
                        "plan": _format_decimal(sales_plan, 0),
                        "converted_total_usd": _format_decimal(sales_fact, 2),
                    },
                },
                "dashboard_revenue": {
                    "overall_totals": {
                        "plan": revenue_totals.get("plan", "0"),
                        "total_usd": revenue_totals.get("total_usd", "0"),
                    },
                    "rows": revenue_rows_tp,
                    "tp_totals": {
                        "plan": _format_decimal(revenue_plan, 0),
                        "total_usd": _format_decimal(revenue_fact, 2),
                    },
                },
                "dashboard_attendance": {
                    "overall_totals": {
                        "plan": attendance_totals.get("plan", "0"),
                        "fact": attendance_totals.get("fact", "0"),
                        "p": attendance_totals.get("p", "0"),
                        "pd": attendance_totals.get("pd", "0"),
                        "total": attendance_totals.get("total", "0"),
                    },
                    "rows": attendance_rows,
                },
                "dashboard_month_label": dashboard_month_label,
                "dashboard_date_from_input": (
                    sales_ctx.get("date_from_input")
                    or revenue_ctx.get("date_from_input")
                    or attendance_ctx.get("date_from_input")
                    or ""
                ),
                "dashboard_date_to_input": (
                    sales_ctx.get("date_to_input")
                    or revenue_ctx.get("date_to_input")
                    or attendance_ctx.get("date_to_input")
                    or ""
                ),
                "dashboard_errors": dashboard_errors,
                "dashboard_sales_chart": {
                    "plan": float(sales_plan),
                    "fact": float(sales_fact),
                    "labels": [r.get("sales_manager") for r in sales_top],
                    "fact_values": [
                        float(_to_decimal_safe(r.get("converted_total_usd")))
                        for r in sales_top
                    ],
                    "plan_values": [
                        float(_to_decimal_safe(r.get("plan")))
                        for r in sales_top
                    ],
                },
                "dashboard_revenue_chart": {
                    "plan": float(revenue_plan),
                    "fact": float(revenue_fact),
                    "labels": [r.get("collector") for r in revenue_top],
                    "fact_values": [
                        float(_to_decimal_safe(r.get("total_usd")))
                        for r in revenue_top
                    ],
                    "plan_values": [
                        float(_to_decimal_safe(r.get("plan")))
                        for r in revenue_top
                    ],
                },
                "dashboard_attendance_chart": {
                    "plan": float(_to_decimal_safe(attendance_totals.get("plan"))),
                    "fact": float(_to_decimal_safe(attendance_totals.get("fact"))),
                    "labels": [r.get("staff") for r in attendance_rows[:5]],
                    "fact_values": [
                        float(_to_decimal_safe(r.get("fact")))
                        for r in attendance_rows[:5]
                    ],
                    "plan_values": [
                        float(_to_decimal_safe(r.get("plan")))
                        for r in attendance_rows[:5]
                    ],
                },
            }
        )

        return super().index(request, extra_context=extra_context)

    def sales_summary(self, request):
        return sales_summary_view(request, self)

    def revenue(self, request):
        return revenue_view(request, self)

    def attendance(self, request):
        return attendance_view(request, self)

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                "sales-summary/",
                self.admin_view(self.sales_summary),
                name="sales-summary",
            ),
            path(
                "revenue/",
                self.admin_view(self.revenue),
                name="revenue",
            ),
            path(
                "attendance/",
                self.admin_view(self.attendance),
                name="attendance",
            ),
            path(
                "",
                self.admin_view(self.index),
                name="index",
            ),
        ]

        return custom_urls + urls


admin_site = CustomAdminSite(name="admin")
