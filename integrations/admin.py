from django.contrib import admin

from config.admin import admin_site
from integrations.models import SmartupAttendanceRow, SmartupAttendanceSync


class SmartupAttendanceRowInline(admin.TabularInline):
    model = SmartupAttendanceRow
    extra = 0
    can_delete = False
    fields = ("staff", "p", "pd", "total", "created_at")
    readonly_fields = fields
    show_change_link = False


@admin.register(SmartupAttendanceSync, site=admin_site)
class SmartupAttendanceSyncAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "date_from",
        "date_to",
        "status",
        "report_title",
        "finished_at",
        "created_at",
    )
    list_filter = ("status", "created_at", "finished_at")
    search_fields = ("date_from", "date_to", "report_title", "error_message")
    readonly_fields = (
        "date_from",
        "date_to",
        "status",
        "report_title",
        "html_report_path",
        "run_url",
        "metadata",
        "error_message",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    )
    inlines = [SmartupAttendanceRowInline]


@admin.register(SmartupAttendanceRow, site=admin_site)
class SmartupAttendanceRowAdmin(admin.ModelAdmin):
    list_display = ("id", "sync", "staff", "p", "pd", "total", "created_at")
    list_filter = ("sync__date_from", "sync__date_to", "created_at")
    search_fields = ("staff",)
    readonly_fields = ("sync", "staff", "p", "pd", "total", "created_at")
