from django.urls import path
from .views import HealthCheckAPIView, GreenwhiteInfoAPIView

urlpatterns = [
    path("health/", HealthCheckAPIView.as_view(), name="health-check"),
    path("greenwhite/info/", GreenwhiteInfoAPIView.as_view(), name="greenwhite-info"),
]