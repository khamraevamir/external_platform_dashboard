import os
import sys

from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'integrations'

    def ready(self):
        scheduler_enabled = os.getenv("SMARTUP_ATTENDANCE_AUTOSYNC_ENABLED", "True") == "True"
        if not scheduler_enabled:
            return

        if len(sys.argv) > 1 and sys.argv[0].endswith("manage.py"):
            management_command = sys.argv[1]
            if management_command != "runserver":
                return

            if os.environ.get("RUN_MAIN") != "true":
                return

        from integrations.smartup_bot.scheduler import (
            start_attendance_scheduler,
            start_google_sheets_scheduler,
        )

        start_attendance_scheduler()
        start_google_sheets_scheduler()
