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
            data = service.get_raw_session_data()
            return Response({
                "company_name": data.get("company_name"),
                "company_code": data.get("company_code"),
                "lang_code": data.get("lang_code"),
                "country_code": data.get("country_code"),
            })
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
            data = service.get_session_summary()
            return Response({
                "project_code": data.get("project_code"),
                "filials": data.get("filials", []),
            })
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


class GreenwhiteSalesSummaryDataAPIView(APIView):
    def get(self, request):
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if not date_from or not date_to:
            return Response(
                {
                    "status": "error",
                    "message": "date_from and date_to are required. Example: 01.12.2025",
                },
                status=400,
            )

        try:
            service = GreenwhiteService()
            result = service.get_sales_summary_report_data(
                date_from=date_from,
                date_to=date_to,
            )
            return Response(result)
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "error_type": e.__class__.__name__,
                    "message": str(e),
                },
                status=500,
            )