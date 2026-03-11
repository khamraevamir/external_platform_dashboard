import json

from bs4 import BeautifulSoup

from integrations.client import GreenwhiteClient


SALES_SUMMARY_TEMPLATE_ID = "151426"


class GreenwhiteService:
    def __init__(self):
        self.client = GreenwhiteClient()

    def get_raw_session_data(self):
        return self.client.get_session_data()

    def get_session_summary(self):
        data = self.get_raw_session_data()

        project_code = None
        filials = []

        projects = data.get("projects", [])
        if projects:
            first_project = projects[0]
            project_code = first_project.get("code")

            raw_filials = first_project.get("filials", [])
            for item in raw_filials:
                if len(item) >= 2:
                    filials.append({
                        "id": item[0],
                        "name": item[1],
                    })

        return {
            "user": data.get("user", {}),
            "company_name": data.get("company_name"),
            "company_code": data.get("company_code"),
            "init_project": data.get("settings", {}).get("init_project"),
            "init_filial": data.get("settings", {}).get("init_filial"),
            "project_code": project_code,
            "filials": filials,
        }

    def get_info(self):
        data = self.get_raw_session_data()

        return {
            "company_name": data.get("company_name"),
            "company_code": data.get("company_code"),
            "lang_code": data.get("lang_code"),
            "country_code": data.get("country_code"),
        }

    def get_sections(self):
        data = self.get_session_summary()

        return {
            "project_code": data.get("project_code"),
            "filials": data.get("filials", []),
        }

    def get_sales_summary_report(
        self,
        date_from: str,
        date_to: str,
        status_ids=None,
        inventory_kind_ids=None,
    ):
        session_data = self.get_raw_session_data()

        settings_data = session_data.get("settings", {})
        user_data = session_data.get("user", {})
        projects = session_data.get("projects", [])

        project_code = settings_data.get("init_project", "trade")
        filial_id = settings_data.get("init_filial")
        user_id = user_data.get("user_id")
        lang_code = session_data.get("lang_code", "ru")

        project_hash = "01"
        if projects:
            project_hash = projects[0].get("hash", "01")

        fields = {
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
                    "ids": status_ids or ["A", "B#V", "B#S", "B#W", "B#E", "B#N"],
                    "filter_names": ["selected"],
                    "values": "name##",
                },
                {
                    "level_code": "inventory_kind",
                    "name": "Тип ТМЦ",
                    "mark_code": "",
                    "ids": inventory_kind_ids or ["G"],
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

        params = {
            "template_id": SALES_SUMMARY_TEMPLATE_ID,
            "subtotal_row_count": "1",
            "subtotal_col_count": "1",
            "region_level": "-1",
            "rt": "html",
            "is_debug": "N",
            "fields": json.dumps(fields, ensure_ascii=False, separators=(",", ":")),
            "-project_code": project_code,
            "-project_hash": project_hash,
            "-filial_id": filial_id,
            "-user_id": user_id,
            "-lang_code": lang_code,
        }

        html = self.client.run_order_report(params)

        return {
            "template_id": SALES_SUMMARY_TEMPLATE_ID,
            "project_code": project_code,
            "filial_id": filial_id,
            "user_id": user_id,
            "lang_code": lang_code,
            "date_from": date_from,
            "date_to": date_to,
            "html": html,
        }

    def parse_sales_summary_html(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", class_="bsr-table")

        if not table:
            return {
                "meta": {},
                "columns": [],
                "rows": [],
                "totals": {},
            }

        rows = table.find_all("tr")
        text_rows = []

        for row in rows:
            cells = row.find_all(["td", "th"])
            values = [cell.get_text(" ", strip=True) for cell in cells]
            if values:
                text_rows.append(values)

        # Первые три строки — мета
        meta = {}
        if len(text_rows) >= 1 and text_rows[0]:
            meta["status"] = text_rows[0][0].replace("Статус:", "").strip()
        if len(text_rows) >= 2 and text_rows[1]:
            meta["inventory_kind"] = text_rows[1][0].replace("Тип ТМЦ:", "").strip()
        if len(text_rows) >= 3 and text_rows[2]:
            meta["date_range"] = text_rows[2][0].replace("Дата заказа:", "").strip()

        # После мета идут 2 строки заголовков
        columns = []
        if len(text_rows) >= 5:
            top_header = text_rows[3]
            second_header = text_rows[4]

            # Делаем понятные колонки под твой отчет
            # В этом шаблоне первая колонка — sales_manager
            # далее валюты
            if len(top_header) >= 4 and len(second_header) >= 4:
                columns = [
                    second_header[0],
                    top_header[1],
                    top_header[2],
                    top_header[3],
                ]

        data_rows = []
        totals = {}

        # Данные начинаются с 6-й строки
        for row in text_rows[5:]:
            if len(row) < 4:
                continue

            item = {
                "sales_manager": row[0],
                "usd": row[1],
                "uzs": row[2],
                "total": row[3],
            }

            if row[0].strip().upper() == "ИТОГО":
                totals = item
            else:
                data_rows.append(item)

        return {
            "meta": meta,
            "columns": columns,
            "rows": data_rows,
            "totals": totals,
        }

    def get_sales_summary_report_data(
        self,
        date_from: str,
        date_to: str,
        status_ids=None,
        inventory_kind_ids=None,
    ):
        report = self.get_sales_summary_report(
            date_from=date_from,
            date_to=date_to,
            status_ids=status_ids,
            inventory_kind_ids=inventory_kind_ids,
        )

        parsed = self.parse_sales_summary_html(report["html"])

        return {
            "template_id": report["template_id"],
            "project_code": report["project_code"],
            "filial_id": report["filial_id"],
            "user_id": report["user_id"],
            "lang_code": report["lang_code"],
            "date_from": report["date_from"],
            "date_to": report["date_to"],
            "meta": parsed["meta"],
            "columns": parsed["columns"],
            "rows": parsed["rows"],
            "totals": parsed["totals"],
        }