from django.core.management.base import BaseCommand

from integrations.google.sheets_service import GoogleSheetsService


class Command(BaseCommand):
    help = "Create next month sales sheet if today is the last day of month"

    def handle(self, *args, **options):
        sheets_service = GoogleSheetsService()
        result = sheets_service.run_monthly_sheet_creation_if_needed()
        self.stdout.write(str(result))