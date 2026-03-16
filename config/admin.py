from django.urls import path
from unfold.sites import UnfoldAdminSite

from integrations.admin_views import sales_summary_view, revenue_view, attendance_view

class CustomAdminSite(UnfoldAdminSite):
    site_header = "Admin"
    site_title = "Admin"
    index_title = "Dashboard"

    def sales_summary(self, request):
        return sales_summary_view(request, self)

    def revenue(self, request):
        return revenue_view(request, self)

    def attendance(self, request):
        return attendance_view(request, self)

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                "sales-summary/",
                self.admin_view(self.sales_summary),
                name="sales-summary",
            ),
            path(
                "revenue/",
                self.admin_view(self.revenue),
                name="revenue",
            ),
            # path(
            #     "attendance/",
            #     self.admin_view(self.attendance),
            #     name="attendance",
            # ),
        ]

        return custom_urls + urls


admin_site = CustomAdminSite(name="admin")