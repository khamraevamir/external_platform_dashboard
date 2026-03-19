from integrations.google.sheets_service import GoogleSheetsService
from integrations.smartup_bot.service import SmartupAttendanceSyncService
from integrations.utils.date_ranges import format_date_range_for_smartup


class AttendanceSheetSyncService:
    def __init__(self):
        self.attendance = SmartupAttendanceSyncService()
        self.sheets = GoogleSheetsService()

    def sync_current_month(self):
        date_from, date_to = format_date_range_for_smartup()

        self.attendance.sync(
            date_from=date_from,
            date_to=date_to,
        )

        summary = self.attendance.get_latest_summary(
            date_from=date_from,
            date_to=date_to,
        )

        if not summary:
            raise ValueError("No synced attendance data found after Smartup sync")

        payload = []
        for row in summary.get("rows", []):
            payload.append({
                "staff": row.get("staff", ""),
                "fact": row.get("total", 0),
            })

        return self.sheets.update_attendance_summary(payload)
