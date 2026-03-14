import json

from .client import SmartupClient
from .parsers.sales_summary_parser import SalesSummaryParser
from .parsers.payment_report_parser import PaymentReportParser

SALES_SUMMARY_TEMPLATE_ID = "151426"
PAYMENT_REPORT_PATH = "/anor/rep/mkcs/payment:run"

DEFAULT_STATUS_IDS = ["A", "B#V", "B#S", "B#W", "B#E", "B#N"]
DEFAULT_INVENTORY_KIND_IDS = ["G"]


class SmartupService:
    def __init__(self) -> None:
        self.client = SmartupClient()
        self._session_context = None

    def get_raw_session_data(self) -> dict:
        return self.client.get_session_data()

    def _build_session_context(self, data: dict) -> dict:
        settings_data = data.get("settings", {})
        user_data = data.get("user", {})
        projects = data.get("projects", [])

        if not projects:
            raise ValueError("No projects found in Smartup session data")

        first_project = projects[0]
        raw_filials = first_project.get("filials", [])

        filials = [
            {"id": item[0], "name": item[1]}
            for item in raw_filials
            if len(item) >= 2
        ]

        project_code = settings_data.get("init_project") or first_project.get("code")
        filial_id = settings_data.get("init_filial")
        user_id = user_data.get("user_id")
        lang_code = data.get("lang_code", "ru")
        project_hash = first_project.get("hash")

        if not project_code:
            raise ValueError("Project code not found in Smartup session data")
        if not project_hash:
            raise ValueError("Project hash not found in Smartup session data")
        if not filial_id:
            raise ValueError("Filial id not found in Smartup session data")
        if not user_id:
            raise ValueError("User id not found in Smartup session data")

        return {
            "raw": data,
            "user": user_data,
            "project_code": project_code,
            "filial_id": filial_id,
            "user_id": user_id,
            "lang_code": lang_code,
            "project_hash": project_hash,
            "filials": filials,
        }

    def _get_session_context(self) -> dict:
        if self._session_context is None:
            data = self.get_raw_session_data()
            self._session_context = self._build_session_context(data)

        return self._session_context

    def get_session_summary(self) -> dict:
        context = self._get_session_context()
        data = context["raw"]

        return {
            "user": context["user"],
            "company_name": data.get("company_name"),
            "company_code": data.get("company_code"),
            "init_project": data.get("settings", {}).get("init_project"),
            "init_filial": data.get("settings", {}).get("init_filial"),
            "project_code": context["project_code"],
            "filials": context["filials"],
        }

    def _build_sales_summary_fields(
        self,
        date_from: str,
        date_to: str,
        status_ids: list[str] | None = None,
        inventory_kind_ids: list[str] | None = None,
    ) -> dict:
        return {
            "levels": [
                {
                    "level_code": "sales_manager",
                    "mark_code": "",
                    "is_row": "Y",
                    "labels": ["name"],
                },
                {
                    "level_code": "currency",
                    "mark_code": "",
                    "is_row": "N",
                    "labels": ["name"],
                },
            ],
            "filters": [
                {
                    "level_code": "status",
                    "name": "Статус",
                    "mark_code": "",
                    "ids": status_ids or DEFAULT_STATUS_IDS,
                    "filter_names": ["selected"],
                    "values": "name##",
                },
                {
                    "level_code": "inventory_kind",
                    "name": "Тип ТМЦ",
                    "mark_code": "",
                    "ids": inventory_kind_ids or DEFAULT_INVENTORY_KIND_IDS,
                    "filter_names": ["Товар"],
                    "values": "name##",
                },
                {
                    "level_code": "deal_date",
                    "name": "Дата заказа",
                    "mark_code": "",
                    "ids": [],
                    "filter_names": [],
                    "values": f"deal_date#{date_from}#{date_to}",
                },
            ],
            "values": [
                {
                    "level_code": "sold_amount",
                    "mark_code": "",
                    "group_kind": "S",
                }
            ],
        }

    def _build_sales_summary_params(
        self,
        date_from: str,
        date_to: str,
        status_ids: list[str] | None = None,
        inventory_kind_ids: list[str] | None = None,
    ) -> dict:
        context = self._get_session_context()
        fields = self._build_sales_summary_fields(
            date_from=date_from,
            date_to=date_to,
            status_ids=status_ids,
            inventory_kind_ids=inventory_kind_ids,
        )

        return {
            "template_id": SALES_SUMMARY_TEMPLATE_ID,
            "subtotal_row_count": "1",
            "subtotal_col_count": "1",
            "region_level": "-1",
            "rt": "html",
            "is_debug": "N",
            "fields": json.dumps(fields, ensure_ascii=False, separators=(",", ":")),
            "-project_code": context["project_code"],
            "-project_hash": context["project_hash"],
            "-filial_id": context["filial_id"],
            "-user_id": context["user_id"],
            "-lang_code": context["lang_code"],
        }

    def get_sales_summary_report(
        self,
        date_from: str,
        date_to: str,
        status_ids: list[str] | None = None,
        inventory_kind_ids: list[str] | None = None,
    ) -> dict:
        context = self._get_session_context()
        params = self._build_sales_summary_params(
            date_from=date_from,
            date_to=date_to,
            status_ids=status_ids,
            inventory_kind_ids=inventory_kind_ids,
        )

        return {
            "template_id": SALES_SUMMARY_TEMPLATE_ID,
            "project_code": context["project_code"],
            "filial_id": context["filial_id"],
            "user_id": context["user_id"],
            "lang_code": context["lang_code"],
            "date_from": date_from,
            "date_to": date_to,
            "html": self.client.run_report(params),
        }

    def get_sales_summary_report_data(
        self,
        date_from: str,
        date_to: str,
        status_ids: list[str] | None = None,
        inventory_kind_ids: list[str] | None = None,
    ) -> dict:
        report = self.get_sales_summary_report(
            date_from=date_from,
            date_to=date_to,
            status_ids=status_ids,
            inventory_kind_ids=inventory_kind_ids,
        )
        parsed = SalesSummaryParser.parse(report["html"])

        return {
            **{key: report[key] for key in (
                "template_id",
                "project_code",
                "filial_id",
                "user_id",
                "lang_code",
                "date_from",
                "date_to",
            )},
            "meta": parsed["meta"],
            "columns": parsed["columns"],
            "rows": parsed["rows"],
            "totals": parsed["totals"],
        }

    def get_trustbank_usd_rate(self) -> dict:
        return self.client.get_trustbank_usd_rate()


    def get_payment_report(self, date_from: str, date_to: str) -> dict:
        context = self._get_session_context()

        params = {
            "rt": "html",
            "begin_date": date_from,
            "end_date": date_to,
            "posted": "Y",
            "person_group_id": "",
            "-project_code": context["project_code"],
            "-project_hash": context["project_hash"],
            "-filial_id": context["filial_id"],
            "-user_id": context["user_id"],
            "-lang_code": context["lang_code"],
        }

        html = self.client.get(PAYMENT_REPORT_PATH, params=params)

        return {
            "date_from": date_from,
            "date_to": date_to,
            "html": html,
        }
    def get_payment_report_data(self, date_from: str, date_to: str) -> dict:
        report = self.get_payment_report(
            date_from=date_from,
            date_to=date_to,
        )

        parsed = PaymentReportParser.parse(report["html"])

        return {
            "date_from": report["date_from"],
            "date_to": report["date_to"],
            "title": parsed["title"],
            "columns": parsed["columns"],
            "rows": parsed["rows"],
            "totals": parsed["totals"],
        }