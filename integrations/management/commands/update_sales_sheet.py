from django.core.management.base import BaseCommand

from integrations.services.sales_summary_sync_service import SalesSummarySyncService


class Command(BaseCommand):
    help = "Update current month Google Sheet with Smartup sales summary"

    def handle(self, *args, **options):
        service = SalesSummarySyncService()
        result = service.sync_current_month()
        self.stdout.write(self.style.SUCCESS(str(result)))