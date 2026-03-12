from django.contrib import admin
from django.urls import path

from integrations.admin_views import sales_summary_view


class CustomAdminSite(admin.AdminSite):

    site_header = "Admin"
    site_title = "Admin"
    index_title = "Dashboard"

    def get_urls(self):
        urls = super().get_urls()

        custom = [
            path(
                "sales-summary/",
                self.admin_view(
                    lambda request: sales_summary_view(
                        request,
                        self,
                    )
                ),
                name="sales-summary",
            ),
        ]

        return custom + urls


admin_site = CustomAdminSite(name="admin")