from django.urls import path
from .views import (
    HealthCheckAPIView,
    GreenwhiteSessionAPIView,
    GreenwhiteSalesSummaryDataAPIView,
    TrustbankUsdRateAPIView
)

urlpatterns = [
    path("health/", HealthCheckAPIView.as_view(), name="health-check"),
    path("greenwhite/session/", GreenwhiteSessionAPIView.as_view(), name="greenwhite-session"),
    path(
        "greenwhite/reports/sales-summary/",
        GreenwhiteSalesSummaryDataAPIView.as_view(),
        name="greenwhite-sales-summary",
    ),
    path(
        "currency/trustbank/usd/",
        TrustbankUsdRateAPIView.as_view(),
        name="trustbank-usd-rate",
    ),
]