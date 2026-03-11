from django.urls import path
from .views import (
    HealthCheckAPIView,
    GreenwhiteInfoAPIView,
    GreenwhiteSectionsAPIView,
    GreenwhiteSessionAPIView,
    GreenwhiteSalesSummaryDataAPIView,
)

urlpatterns = [
    path("health/", HealthCheckAPIView.as_view(), name="health-check"),
    path("greenwhite/info/", GreenwhiteInfoAPIView.as_view(), name="greenwhite-info"),
    path("greenwhite/sections/", GreenwhiteSectionsAPIView.as_view(), name="greenwhite-sections"),
    path("greenwhite/session/", GreenwhiteSessionAPIView.as_view(), name="greenwhite-session"),
    path(
        "greenwhite/reports/sales-summary/",
        GreenwhiteSalesSummaryDataAPIView.as_view(),
        name="greenwhite-sales-summary",
    ),
]