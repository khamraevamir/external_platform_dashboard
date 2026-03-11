from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.client import GreenwhiteClient


class HealthCheckAPIView(APIView):
    def get(self, request):
        return Response({
            "status": "ok",
            "message": "API is working",
        })


class GreenwhiteInfoAPIView(APIView):
    def get(self, request):
        client = GreenwhiteClient()

        try:
            data = client.get("/")
            return Response(data)
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": str(e),
                },
                status=500
            )