from django.urls import path
from .views import (
    HealthCheckAPIView,
    GreenwhiteSessionAPIView,
    GreenwhiteSalesSummaryDataAPIView,
    GreenwhitePaymentReportDataAPIView,
    TrustbankUsdRateAPIView,
    GreenwhiteRouteAnalysisDataAPIView,
    GreenwhiteSessionDebugAPIView,
)

urlpatterns = [
    path("health/", HealthCheckAPIView.as_view(), name="health-check"),
    path("greenwhite/session/", GreenwhiteSessionAPIView.as_view(), name="greenwhite-session"),
    path(
        "greenwhite/reports/sales-summary/",
        GreenwhiteSalesSummaryDataAPIView.as_view(),
        name="greenwhite-sales-summary",
    ),
    path("greenwhite/payment-report/", GreenwhitePaymentReportDataAPIView.as_view(), name="greenwhite-payment-report"),
    path("greenwhite/route-analysis/", GreenwhiteRouteAnalysisDataAPIView.as_view(), name="greenwhite-route-analysis"),

    path(
        "currency/trustbank/usd/",
        TrustbankUsdRateAPIView.as_view(),
        name="trustbank-usd-rate",
    ),
    path(
        "greenwhite/session-debug/",
        GreenwhiteSessionDebugAPIView.as_view(),
        name="greenwhite-session-debug",
    ),
]
