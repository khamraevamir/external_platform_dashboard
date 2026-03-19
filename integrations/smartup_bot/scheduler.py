from __future__ import annotations

import calendar
import logging
import threading
from datetime import datetime, timedelta

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from integrations.models import SmartupAttendanceSync
from integrations.services.revenue_sync_service import RevenueSyncService
from integrations.services.sales_summary_sync_service import SalesSummarySyncService
from integrations.smartup_bot.service import SmartupAttendanceSyncService


logger = logging.getLogger(__name__)

_scheduler_thread: threading.Thread | None = None
_sheets_scheduler_thread: threading.Thread | None = None
_scheduler_lock = threading.Lock()


def get_current_month_range() -> tuple[str, str]:
    today = datetime.today()
    first_day = today.replace(day=1)
    last_day_num = calendar.monthrange(today.year, today.month)[1]
    last_day = today.replace(day=last_day_num)
    return (
        first_day.strftime("%d.%m.%Y"),
        last_day.strftime("%d.%m.%Y"),
    )


class AttendanceAutoSyncScheduler:
    def __init__(self) -> None:
        self.interval_seconds = int(
            getattr(settings, "SMARTUP_ATTENDANCE_SYNC_INTERVAL_SECONDS", 21600)
        )
        self._stop_event = threading.Event()

    def _recent_sync_exists(self, date_from: str, date_to: str) -> bool:
        threshold = timezone.now() - timedelta(seconds=self.interval_seconds)
        return SmartupAttendanceSync.objects.filter(
            date_from=date_from,
            date_to=date_to,
            status=SmartupAttendanceSync.STATUS_SUCCESS,
            finished_at__gte=threshold,
        ).exists()

    def _sync_is_running(self, date_from: str, date_to: str) -> bool:
        threshold = timezone.now() - timedelta(hours=1)
        return SmartupAttendanceSync.objects.filter(
            date_from=date_from,
            date_to=date_to,
            status=SmartupAttendanceSync.STATUS_RUNNING,
            started_at__gte=threshold,
        ).exists()

    def run_once(self) -> None:
        close_old_connections()
        date_from, date_to = get_current_month_range()

        if self._sync_is_running(date_from, date_to):
            logger.info(
                "Skipping attendance autosync because a sync is already running for %s - %s",
                date_from,
                date_to,
            )
            return

        if self._recent_sync_exists(date_from, date_to):
            logger.info(
                "Skipping attendance autosync because a recent successful sync already exists for %s - %s",
                date_from,
                date_to,
            )
            return

        logger.info(
            "Starting scheduled attendance sync for %s - %s",
            date_from,
            date_to,
        )
        SmartupAttendanceSyncService().sync(date_from=date_from, date_to=date_to)

    def run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception:
                logger.exception("Scheduled attendance sync failed")

            if self._stop_event.wait(self.interval_seconds):
                break


class GoogleSheetsAutoSyncScheduler:
    def __init__(self) -> None:
        self.interval_seconds = int(
            getattr(settings, "SMARTUP_GOOGLE_SHEETS_SYNC_INTERVAL_SECONDS", 3600)
        )
        self._stop_event = threading.Event()

    def run_once(self) -> None:
        close_old_connections()
        logger.info("Starting scheduled Google Sheets sync for sales and revenue")

        sales_result = SalesSummarySyncService().sync_current_month()
        logger.info("Scheduled sales Google Sheets sync finished: %s", sales_result)

        revenue_result = RevenueSyncService().sync_current_month()
        logger.info("Scheduled revenue Google Sheets sync finished: %s", revenue_result)

    def run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception:
                logger.exception("Scheduled Google Sheets sync failed")

            if self._stop_event.wait(self.interval_seconds):
                break


def start_attendance_scheduler() -> None:
    global _scheduler_thread

    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return

        scheduler = AttendanceAutoSyncScheduler()
        _scheduler_thread = threading.Thread(
            target=scheduler.run_forever,
            name="smartup-attendance-autosync",
            daemon=True,
        )
        _scheduler_thread.start()
        logger.info(
            "Attendance autosync scheduler started with interval %s seconds",
            scheduler.interval_seconds,
        )


def start_google_sheets_scheduler() -> None:
    global _sheets_scheduler_thread

    with _scheduler_lock:
        if _sheets_scheduler_thread and _sheets_scheduler_thread.is_alive():
            return

        scheduler = GoogleSheetsAutoSyncScheduler()
        _sheets_scheduler_thread = threading.Thread(
            target=scheduler.run_forever,
            name="smartup-google-sheets-autosync",
            daemon=True,
        )
        _sheets_scheduler_thread.start()
        logger.info(
            "Google Sheets autosync scheduler started with interval %s seconds",
            scheduler.interval_seconds,
        )
