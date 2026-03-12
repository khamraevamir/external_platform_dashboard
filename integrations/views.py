from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from integrations.smartup.services import SmartupService


class HealthCheckAPIView(APIView):
    def get(self, request):
        return Response({
            "status": "ok",
            "message": "API is working",
        })


class GreenwhiteSessionAPIView(APIView):
    def get(self, request):
        try:
            service = SmartupService()
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

    @extend_schema(
        summary="Smartup Sales Summary Report",
        description="""
    Returns aggregated sales data from **Smartup ERP** based on the predefined report template.
    The report includes:
    - Sales grouped by **sales managers**
    - Values converted to **multiple currencies**
    - Aggregated **total sales values**

    This endpoint internally executes the Smartup report with template:

    `template_id = 151426`

    Required parameters:

    - **date_from**
    - **date_to**

    Date format must be:

    `DD.MM.YYYY`
    """,
        parameters=[
            OpenApiParameter(
                name="date_from",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Start date of the report period. Example: **01.12.2025**",
            ),
            OpenApiParameter(
                name="date_to",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
                description="End date of the report period. Example: **31.12.2025**",
            ),
        ],
        examples=[
            OpenApiExample(
                "Successful Response",
                value={
                    "template_id": "151426",
                    "project_code": "trade",
                    "filial_id": "4511443",
                    "user_id": "17825477",
                    "lang_code": "ru",
                    "date_from": "01.12.2025",
                    "date_to": "31.12.2025",
                    "meta": {
                        "status": "selected",
                        "inventory_kind": "Товар",
                        "date_range": "01.12.2025-31.12.2025"
                    },
                    "columns": [
                        "Торговый представитель",
                        "Доллар США",
                        "Узбекский сум",
                        "ИТОГО"
                    ],
                    "rows": [
                        {
                            "sales_manager": "Ахмедов Бекзод",
                            "usd": "74539.632",
                            "uzs": "191332180",
                            "total": "191406719.632"
                        }
                    ],
                    "totals": {
                        "sales_manager": "ИТОГО",
                        "usd": "257718.087",
                        "uzs": "854123011.671",
                        "total": "854380729.758"
                    }
                },
            ),
            OpenApiExample(
                "Missing Parameters",
                value={
                    "status": "error",
                    "message": "date_from and date_to are required. Example: 01.12.2025"
                },
            ),
        ],
    )
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
            service = SmartupService()

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
   

class TrustbankUsdRateAPIView(APIView):
    def get(self, request):
        try:
            service = SmartupService()
            data = service.get_trustbank_usd_rate()
            return Response(data)
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "error_type": e.__class__.__name__,
                    "message": str(e),
                },
                status=500,
            )  