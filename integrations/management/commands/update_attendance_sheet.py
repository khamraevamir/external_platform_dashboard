from django.core.management.base import BaseCommand

from integrations.services.attendance_sync_service import AttendanceSheetSyncService


class Command(BaseCommand):
    help = "Update current month Google Sheet with Smartup attendance summary"

    def handle(self, *args, **options):
        service = AttendanceSheetSyncService()
        result = service.sync_current_month()
        self.stdout.write(self.style.SUCCESS(str(result)))
