from django.core.management.base import BaseCommand
from integrations.client import SmartupClient


class Command(BaseCommand):
    help = "Test connection to Greenwhite API"

    def handle(self, *args, **options):
        client = SmartupClient()

        try:
            response = client.get("/")
            self.stdout.write(self.style.SUCCESS("Connection successful"))
            self.stdout.write(str(response))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Connection failed: {e}"))