from django.core.management.base import BaseCommand

from integrations.services.revenue_sync_service import RevenueSyncService


class Command(BaseCommand):
    help = "Update current month Google Sheet with revenue summary"

    def handle(self, *args, **options):
        service = RevenueSyncService()
        result = service.sync_current_month()
        self.stdout.write(self.style.SUCCESS(str(result)))