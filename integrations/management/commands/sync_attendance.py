from __future__ import annotations

import calendar
from datetime import datetime

from django.core.management.base import BaseCommand

from integrations.smartup_bot.service import SmartupAttendanceSyncService


class Command(BaseCommand):
    help = "Run Smartup attendance sync via Playwright and store parsed rows in the database."

    def add_arguments(self, parser):
        parser.add_argument("--date-from", dest="date_from", default="")
        parser.add_argument("--date-to", dest="date_to", default="")

    def handle(self, *args, **options):
        date_from = str(options.get("date_from") or "").strip()
        date_to = str(options.get("date_to") or "").strip()

        if not date_from or not date_to:
            today = datetime.today()
            first_day = today.replace(day=1)
            last_day_num = calendar.monthrange(today.year, today.month)[1]
            last_day = today.replace(day=last_day_num)
            date_from = first_day.strftime("%d.%m.%Y")
            date_to = last_day.strftime("%d.%m.%Y")

        service = SmartupAttendanceSyncService()
        result = service.sync(date_from=date_from, date_to=date_to)
        self.stdout.write(self.style.SUCCESS(str(result)))
