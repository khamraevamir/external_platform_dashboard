import calendar
import gspread
from datetime import datetime
from gspread.exceptions import WorksheetNotFound
from django.conf import settings
from google.oauth2.service_account import Credentials
from integrations.utils.numbers import parse_number


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


    def normalize_short_name(self, value):
        parts = self.normalize(value).split()

        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"

        return " ".join(parts)


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
        return self.update_metric_summary(payload, criteria_name="Савдо")

    def update_revenue_summary(self, payload):
        return self.update_metric_summary(payload, criteria_name="Выручка")

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

    def update_metric_summary(self, payload, criteria_name):
        sheet = self.get_current_month_sheet()
        values = sheet.get_all_values()

        results = {
            "status": "ok",
            "sheet": sheet.title,
            "criteria_name": criteria_name,
            "updated": [],
            "skipped": [],
        }

        batch_updates = []
        target_criteria = self.normalize(criteria_name)

        for item in payload:
            source_name = item.get("name") or item.get("sales_manager") or item.get("collector") or ""
            short_name = self.normalize_short_name(source_name)
            raw_value = (
                item.get("value")
                or item.get("converted_total_usd")
                or item.get("total_usd")
                or 0
            )
            total_value = parse_number(raw_value)

            if not short_name:
                results["skipped"].append({
                    "name": source_name,
                    "reason": "empty_name",
                })
                continue

            matches = []
            for row_index, row_values in enumerate(values):
                fio = row_values[self.COL_FIO] if len(row_values) > self.COL_FIO else ""
                fio_short = self.normalize_short_name(fio)

                if fio_short == short_name:
                    matches.append(row_index)

            if len(matches) == 0:
                results["skipped"].append({
                    "name": source_name,
                    "reason": "employee_not_found",
                })
                continue

            if len(matches) > 1:
                results["skipped"].append({
                    "name": source_name,
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
                    "name": source_name,
                    "reason": "supervisor_ignored",
                })
                continue

            target_row = None

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

                if criteria == target_criteria:
                    target_row = row_index
                    break

            if target_row is None:
                results["skipped"].append({
                    "name": source_name,
                    "reason": "criteria_row_not_found",
                })
                continue

            row_1_based = target_row + 1
            col_1_based = self.COL_FACT + 1
            cell_a1 = self.to_a1(col_1_based, row_1_based)

            batch_updates.append({
                "range": cell_a1,
                "values": [[total_value]],
            })

            results["updated"].append({
                "name": source_name,
                "cell": cell_a1,
                "value": total_value,
            })

        if batch_updates:
            sheet.batch_update(batch_updates)

        return results