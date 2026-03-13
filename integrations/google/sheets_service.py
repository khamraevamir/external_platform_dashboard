from datetime import datetime
import calendar

from django.conf import settings

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound


class GoogleSheetsService:
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    MONTHS_RU = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ]

    COL_FIO = 0       # A
    COL_POSITION = 1  # B
    COL_CRITERIA = 2  # C
    COL_FACT = 4      # E

    HEADER_ROW = 2  # строка с заголовками "План" / "Факт" (1-based)

    def __init__(self):
        credentials = Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=self.SCOPES,
        )
        self.client = gspread.authorize(credentials)

    def get_spreadsheet(self):
        return self.client.open_by_key(settings.GOOGLE_SHEET_ID)

    def normalize(self, value):
        return str(value or "").strip().lower()

    def parse_number(self, value):
        cleaned = (
            str(value or "0")
            .replace("\xa0", "")
            .replace(" ", "")
            .replace(",", ".")
        )

        try:
            return float(cleaned)
        except (TypeError, ValueError):
            return 0.0

    def get_month_sheet_name(self, date_obj=None):
        date_obj = date_obj or datetime.today()
        return f"{self.MONTHS_RU[date_obj.month - 1]}_{date_obj.year}"

    def get_current_month_sheet(self):
        spreadsheet = self.get_spreadsheet()
        sheet_name = self.get_month_sheet_name()
        return spreadsheet.worksheet(sheet_name)

    def to_a1(self, col, row):
        column = ""
        while col > 0:
            rem = (col - 1) % 26
            column = chr(65 + rem) + column
            col = (col - 1) // 26
        return f"{column}{row}"

    def update_sales_summary(self, payload):
        sheet = self.get_current_month_sheet()
        values = sheet.get_all_values()

        results = {
            "status": "ok",
            "sheet": sheet.title,
            "updated": [],
            "skipped": [],
        }

        batch_updates = []

        for item in payload:
            full_name = self.normalize(item.get("sales_manager"))
            total_usd = self.parse_number(item.get("converted_total_usd"))

            if not full_name:
                results["skipped"].append({
                    "sales_manager": item.get("sales_manager"),
                    "reason": "empty_name",
                })
                continue

            matches = []
            for row_index, row_values in enumerate(values):
                fio = self.normalize(
                    row_values[self.COL_FIO] if len(row_values) > self.COL_FIO else ""
                )
                if fio == full_name:
                    matches.append(row_index)

            if len(matches) == 0:
                results["skipped"].append({
                    "sales_manager": item.get("sales_manager"),
                    "reason": "employee_not_found",
                })
                continue

            if len(matches) > 1:
                results["skipped"].append({
                    "sales_manager": item.get("sales_manager"),
                    "reason": "multiple_matches",
                })
                continue

            employee_row = matches[0]

            position_value = self.normalize(
                values[employee_row][self.COL_POSITION]
                if len(values[employee_row]) > self.COL_POSITION else ""
            )

            if "супервайзер" in position_value:
                results["skipped"].append({
                    "sales_manager": item.get("sales_manager"),
                    "reason": "supervisor_ignored",
                })
                continue

            savdo_row = None

            for row_index in range(employee_row, len(values)):
                if row_index > employee_row:
                    next_employee = self.normalize(
                        values[row_index][self.COL_FIO]
                        if len(values[row_index]) > self.COL_FIO else ""
                    )
                    if next_employee:
                        break

                criteria = self.normalize(
                    values[row_index][self.COL_CRITERIA]
                    if len(values[row_index]) > self.COL_CRITERIA else ""
                )

                if criteria == "савдо":
                    savdo_row = row_index
                    break

            if savdo_row is None:
                results["skipped"].append({
                    "sales_manager": item.get("sales_manager"),
                    "reason": "savdo_row_not_found",
                })
                continue

            row_1_based = savdo_row + 1
            col_1_based = self.COL_FACT + 1
            cell_a1 = self.to_a1(col_1_based, row_1_based)

            batch_updates.append({
                "range": cell_a1,
                "values": [[total_usd]],
            })

            results["updated"].append({
                "sales_manager": item.get("sales_manager"),
                "cell": cell_a1,
                "value": total_usd,
            })

        if batch_updates:
            sheet.batch_update(batch_updates)

        return results

    def run_monthly_sheet_creation_if_needed(self):
        today = datetime.today()
        last_day_of_month = calendar.monthrange(today.year, today.month)[1]

        if today.day == last_day_of_month:
            return self.create_next_month_sheet()

        return {
            "status": "skipped",
            "message": "Сегодня не последний день месяца",
        }

    def create_next_month_sheet(self):
        spreadsheet = self.get_spreadsheet()
        today = datetime.today()

        current_month_index = today.month - 1
        current_year = today.year

        next_month_index = current_month_index + 1
        next_year = current_year

        if next_month_index > 11:
            next_month_index = 0
            next_year += 1

        current_sheet_name = f"{self.MONTHS_RU[current_month_index]}_{current_year}"
        next_sheet_name = f"{self.MONTHS_RU[next_month_index]}_{next_year}"

        try:
            current_sheet = spreadsheet.worksheet(current_sheet_name)
        except WorksheetNotFound:
            raise ValueError(f'Лист "{current_sheet_name}" не найден')

        try:
            spreadsheet.worksheet(next_sheet_name)
            return {
                "status": "skipped",
                "message": f'Лист "{next_sheet_name}" уже существует',
            }
        except WorksheetNotFound:
            pass

        new_sheet = current_sheet.duplicate(new_sheet_name=next_sheet_name)
        self.clear_plan_and_fact_values(new_sheet)

        return {
            "status": "ok",
            "message": f'Создан лист "{next_sheet_name}"',
        }

    def clear_plan_and_fact_values(self, sheet):
        values = sheet.get_all_values()

        if len(values) < self.HEADER_ROW:
            return

        headers = values[self.HEADER_ROW - 1]

        plan_columns = []
        fact_columns = []

        for index, header in enumerate(headers):
            normalized = self.normalize(header)

            if normalized == "план":
                plan_columns.append(index + 1)

            if normalized == "факт":
                fact_columns.append(index + 1)

        target_columns = plan_columns + fact_columns

        last_row = len(values)

        if last_row <= self.HEADER_ROW:
            return

        clear_requests = []
        for col in target_columns:
            start_a1 = self.to_a1(col, self.HEADER_ROW + 1)
            end_a1 = self.to_a1(col, last_row)
            clear_requests.append(f"{start_a1}:{end_a1}")

        if clear_requests:
            sheet.batch_clear(clear_requests)