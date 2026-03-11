from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.services import GreenwhiteService


class HealthCheckAPIView(APIView):
    def get(self, request):
        return Response({
            "status": "ok",
            "message": "API is working",
        })


class GreenwhiteInfoAPIView(APIView):
    def get(self, request):
        try:
            service = GreenwhiteService()
            return Response(service.get_info())
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "error_type": e.__class__.__name__,
                    "message": str(e),
                },
                status=500,
            )


class GreenwhiteSectionsAPIView(APIView):
    def get(self, request):
        try:
            service = GreenwhiteService()
            return Response(service.get_sections())
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "error_type": e.__class__.__name__,
                    "message": str(e),
                },
                status=500,
            )


class GreenwhiteSessionAPIView(APIView):
    def get(self, request):
        try:
            service = GreenwhiteService()
            return Response(service.get_session_summary())
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "error_type": e.__class__.__name__,
                    "message": str(e),
                },
                status=500,
            )