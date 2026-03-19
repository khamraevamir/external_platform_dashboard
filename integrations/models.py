from django.db import models


class SmartupAttendanceSync(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_ERROR = "error"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_ERROR, "Error"),
    ]

    date_from = models.CharField(max_length=10)
    date_to = models.CharField(max_length=10)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    report_title = models.CharField(max_length=255, blank=True)
    html_report_path = models.CharField(max_length=500, blank=True)
    run_url = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Attendance sync {self.date_from} - {self.date_to} ({self.status})"


class SmartupAttendanceRow(models.Model):
    sync = models.ForeignKey(
        SmartupAttendanceSync,
        on_delete=models.CASCADE,
        related_name="rows",
    )
    staff = models.CharField(max_length=255)
    p = models.PositiveIntegerField(default=0)
    pd = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("staff",)

    def __str__(self) -> str:
        return f"{self.staff}: P={self.p}, PD={self.pd}"
