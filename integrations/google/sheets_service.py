import calendar
import gspread
from datetime import datetime
from django.core.cache import cache
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
    COL_PLAN = 3      # D

    HEADER_ROW = 2  # строка с заголовками "План" / "Факт" (1-based)
    SHEET_VALUES_CACHE_TIMEOUT = 900
    _client = None
    _spreadsheet = None

    def __init__(self):
        if self.__class__._client is None:
            credentials = Credentials.from_service_account_file(
                settings.GOOGLE_SERVICE_ACCOUNT_FILE,
                scopes=self.SCOPES,
            )
            self.__class__._client = gspread.authorize(credentials)

        self.client = self.__class__._client

    def get_spreadsheet(self):
        if self.__class__._spreadsheet is None:
            self.__class__._spreadsheet = self.client.open_by_key(settings.GOOGLE_SHEET_ID)

        return self.__class__._spreadsheet

    def normalize(self, value):
        return str(value or "").strip().lower()


    def normalize_short_name(self, value):
        parts = self.normalize(value).split()

        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"

        return " ".join(parts)

    def normalize_short_name_reversed(self, value):
        parts = self.normalize(value).split()

        if len(parts) >= 2:
            return f"{parts[1]} {parts[0]}"

        return " ".join(parts)

    def build_person_aliases(self, value=""):
        normalized = self.normalize(value)
        aliases = set()

        if not normalized:
            return aliases

        aliases.add(normalized)
        aliases.add(self.normalize_short_name(normalized))
        aliases.add(self.normalize_short_name_reversed(normalized))

        for token in normalized.split():
            if token:
                aliases.add(token)

        return {alias for alias in aliases if alias}

    def build_attendance_aliases(self, fio="", position=""):
        aliases = set()
        ignored_tokens = {"тп", "supervisor", "супервайзер", "менеджер"}

        normalized_position = self.normalize(position)
        normalized_fio = self.normalize(fio)

        if normalized_position:
            aliases.add(normalized_position)

            cleaned_position = normalized_position
            for prefix in ("тп ",):
                if cleaned_position.startswith(prefix):
                    cleaned_position = cleaned_position[len(prefix):].strip()

            if cleaned_position:
                aliases.add(cleaned_position)

            for token in cleaned_position.split():
                if token and token not in ignored_tokens:
                    aliases.add(token)

        if normalized_fio:
            aliases.add(self.normalize_short_name(normalized_fio))
            aliases.add(self.normalize_short_name_reversed(normalized_fio))

            for token in normalized_fio.split():
                if token and token not in ignored_tokens:
                    aliases.add(token)

        return {alias for alias in aliases if alias}


    def get_month_sheet_name(self, date_obj=None):
        date_obj = date_obj or datetime.today()
        return f"{self.MONTHS_RU[date_obj.month - 1]}_{date_obj.year}"

    def get_current_month_sheet(self):
        return self.get_month_sheet()

    def get_month_sheet(self, date_obj=None):
        spreadsheet = self.get_spreadsheet()
        sheet_name = self.get_month_sheet_name(date_obj)
        return spreadsheet.worksheet(sheet_name)

    def get_current_month_values(self):
        return self.get_month_values()

    def get_month_values(self, date_obj=None):
        sheet_name = self.get_month_sheet_name(date_obj)
        cache_key = f"google-sheets:values:{settings.GOOGLE_SHEET_ID}:{sheet_name}"
        cached_values = cache.get(cache_key)

        if cached_values is not None:
            return cached_values

        values = self.get_month_sheet(date_obj).get_all_values()
        cache.set(cache_key, values, timeout=self.SHEET_VALUES_CACHE_TIMEOUT)
        return values

    def invalidate_current_month_cache(self):
        sheet_name = self.get_month_sheet_name()
        cache_key = f"google-sheets:values:{settings.GOOGLE_SHEET_ID}:{sheet_name}"
        cache.delete(cache_key)

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

    def update_attendance_summary(self, payload):
        sheet = self.get_current_month_sheet()
        values = self.get_current_month_values()

        results = {
            "status": "ok",
            "sheet": sheet.title,
            "criteria_name": "Плановый визит",
            "updated": [],
            "skipped": [],
        }

        target_criteria = self.normalize("Плановый визит")
        batch_updates = []
        candidates = self._get_attendance_update_candidates(values, target_criteria)

        for item in payload:
            source_name = self.normalize(
                item.get("staff")
                or item.get("work_area")
                or item.get("name")
                or ""
            )
            raw_value = item.get("fact") or item.get("total") or item.get("value") or 0
            total_value = parse_number(raw_value)

            if not source_name:
                results["skipped"].append({
                    "name": source_name,
                    "reason": "empty_name",
                })
                continue

            matches = [candidate for candidate in candidates if source_name in candidate["aliases"]]

            if len(matches) > 1:
                exact_matches = [
                    candidate for candidate in matches
                    if source_name in candidate["exact_aliases"]
                ]
                if len(exact_matches) == 1:
                    matches = exact_matches

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

            row_1_based = matches[0]["row_index"] + 1
            col_1_based = self.COL_FACT + 1
            cell_a1 = self.to_a1(col_1_based, row_1_based)

            batch_updates.append({
                "range": cell_a1,
                "values": [[total_value]],
            })

            results["updated"].append({
                "name": item.get("staff") or item.get("work_area") or item.get("name") or "",
                "cell": cell_a1,
                "value": total_value,
            })

        if batch_updates:
            sheet.batch_update(batch_updates)
            self.invalidate_current_month_cache()

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
            self.invalidate_current_month_cache()

    def update_metric_summary(self, payload, criteria_name):
        sheet = self.get_current_month_sheet()
        values = self.get_current_month_values()

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
            source_aliases = self.build_person_aliases(source_name)
            raw_value = (
                item.get("value")
                or item.get("converted_total_usd")
                or item.get("total_usd")
                or 0
            )
            total_value = parse_number(raw_value)

            if not source_aliases:
                results["skipped"].append({
                    "name": source_name,
                    "reason": "empty_name",
                })
                continue

            matches = []
            for row_index, row_values in enumerate(values):
                fio = row_values[self.COL_FIO] if len(row_values) > self.COL_FIO else ""
                row_aliases = self.build_person_aliases(fio)

                if source_aliases & row_aliases:
                    matches.append(row_index)

            if len(matches) > 1:
                exact_matches = []
                normalized_source = self.normalize(source_name)
                short_source = self.normalize_short_name(source_name)
                reversed_short_source = self.normalize_short_name_reversed(source_name)

                for row_index in matches:
                    fio = values[row_index][self.COL_FIO] if len(values[row_index]) > self.COL_FIO else ""
                    row_normalized = self.normalize(fio)
                    row_short = self.normalize_short_name(fio)
                    row_reversed_short = self.normalize_short_name_reversed(fio)

                    if normalized_source in {row_normalized, row_short, row_reversed_short}:
                        exact_matches.append(row_index)
                    elif short_source in {row_normalized, row_short, row_reversed_short}:
                        exact_matches.append(row_index)
                    elif reversed_short_source in {row_normalized, row_short, row_reversed_short}:
                        exact_matches.append(row_index)

                if len(exact_matches) == 1:
                    matches = exact_matches

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
            self.invalidate_current_month_cache()

        return results



    def get_metric_plan_map(self, criteria_name, date_obj=None):
        values = self.get_month_values(date_obj)

        target_criteria = self.normalize(criteria_name)
        result = {}

        current_employee_short_name = None

        for row_values in values:
            fio = row_values[self.COL_FIO] if len(row_values) > self.COL_FIO else ""
            criteria = row_values[self.COL_CRITERIA] if len(row_values) > self.COL_CRITERIA else ""
            plan_value = row_values[self.COL_PLAN] if len(row_values) > self.COL_PLAN else ""

            if self.normalize(fio):
                current_employee_short_name = self.normalize_short_name(fio)

            if not current_employee_short_name:
                continue

            if self.normalize(criteria) == target_criteria:
                result[current_employee_short_name] = parse_number(plan_value)

        return result

    def get_sales_plan_map(self, date_obj=None):
        return self.get_metric_plan_map("Савдо", date_obj=date_obj)

    def get_revenue_plan_map(self, date_obj=None):
        return self.get_metric_plan_map("Выручка", date_obj=date_obj)

    def get_metric_plan_map_by_position(self, criteria_name, date_obj=None):
        values = self.get_month_values(date_obj)

        target_criteria = self.normalize(criteria_name)
        result = {}

        current_position = None
        current_fio = None

        for row_values in values:
            fio = row_values[self.COL_FIO] if len(row_values) > self.COL_FIO else ""
            position = row_values[self.COL_POSITION] if len(row_values) > self.COL_POSITION else ""
            criteria = row_values[self.COL_CRITERIA] if len(row_values) > self.COL_CRITERIA else ""
            plan_value = row_values[self.COL_PLAN] if len(row_values) > self.COL_PLAN else ""

            if self.normalize(fio):
                current_fio = fio

            if self.normalize(position):
                current_position = self.normalize(position)

            if not current_position:
                continue

            if self.normalize(criteria) == target_criteria:
                parsed_plan = parse_number(plan_value)
                aliases = self.build_attendance_aliases(
                    fio=current_fio or "",
                    position=current_position,
                )
                for alias in aliases:
                    result[alias] = parsed_plan

        return result

    def get_attendance_plan_map(self, date_obj=None):
        return self.get_metric_plan_map_by_position("Плановый визит", date_obj=date_obj)

    def _get_attendance_update_candidates(self, values, target_criteria):
        candidates = []
        current_fio = None
        current_position = None

        for row_index, row_values in enumerate(values):
            fio = row_values[self.COL_FIO] if len(row_values) > self.COL_FIO else ""
            position = row_values[self.COL_POSITION] if len(row_values) > self.COL_POSITION else ""
            criteria = row_values[self.COL_CRITERIA] if len(row_values) > self.COL_CRITERIA else ""

            if self.normalize(fio):
                current_fio = fio

            if self.normalize(position):
                current_position = position

            if not current_position:
                continue

            if self.normalize(criteria) != target_criteria:
                continue

            normalized_position = self.normalize(current_position)
            cleaned_position = normalized_position.removeprefix("тп ").strip()
            fio_tokens = [
                token for token in self.normalize(current_fio or "").split()
                if token
            ]
            exact_aliases = {
                alias for alias in (
                    normalized_position,
                    cleaned_position,
                    self.normalize(current_fio or ""),
                    self.normalize_short_name(current_fio or ""),
                    self.normalize_short_name_reversed(current_fio or ""),
                ) if alias
            }
            exact_aliases.update(fio_tokens)

            candidates.append({
                "row_index": row_index,
                "aliases": self.build_attendance_aliases(
                    fio=current_fio or "",
                    position=current_position,
                ),
                "exact_aliases": exact_aliases,
            })

        return candidates

    def get_position_map(self):
        values = self.get_current_month_values()

        position_map = {}

        for row in values:
            fio = row[self.COL_FIO] if len(row) > self.COL_FIO else ""
            position = row[self.COL_POSITION] if len(row) > self.COL_POSITION else ""

            short_name = self.normalize_short_name(fio)

            if short_name:
                position_map[short_name] = position

        return position_map
