from datetime import timedelta
from django.db import connection, transaction
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Asset, AssetStatus, CheckOut, Employee
from .serializers import (
    AssetSerializer,
    CheckOutCreateSerializer,
    CheckOutResponseSerializer,
    CheckOutReturnSerializer,
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return Response({"status": "healthy", "database": "connected"}, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response(
                {"status": "unhealthy", "database": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class AssetListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AssetSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Asset.objects.all().prefetch_related("checkouts__employee")
        category = self.request.query_params.get("category")
        status_param = self.request.query_params.get("status")
        search = self.request.query_params.get("search")

        if category:
            queryset = queryset.filter(category=category.upper())
        if status_param:
            queryset = queryset.filter(status=status_param.upper())
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(asset_tag__icontains=search)
            )
        return queryset


class AssetDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AssetSerializer
    queryset = Asset.objects.all().prefetch_related("checkouts__employee")
    lookup_field = "id"


class CheckOutCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckOutCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Rule 8: 404 for unknown asset_tag or employee_code
        asset_target = get_object_or_404(Asset, asset_tag=data["asset_tag"])
        employee_target = get_object_or_404(Employee, employee_code=data["employee_code"])

        # Rule 2: Inactive employee cannot check out -> 400 Bad Request
        if not employee_target.is_active:
            return Response(
                {"detail": "Inactive employee cannot check out assets."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Atomic transaction + Row locking (Rule 7 concurrency requirement)
        with transaction.atomic():
            asset = Asset.objects.select_for_update().get(id=asset_target.id)

            # Rule 1: Non-AVAILABLE asset -> 409 Conflict
            if asset.status != AssetStatus.AVAILABLE:
                return Response(
                    {"detail": f"Asset is not AVAILABLE (currently {asset.status})."},
                    status=status.HTTP_409_CONFLICT,
                )

            # Lock employee row to serialize open count check
            Employee.objects.select_for_update().get(id=employee_target.id)

            # Rule 3: Max 3 open check-outs -> 409 Conflict on 4th attempt
            open_count = CheckOut.objects.filter(
                employee=employee_target, returned_at__isnull=True
            ).count()
            if open_count >= 3:
                return Response(
                    {"detail": "Employee has reached the limit of 3 open check-outs."},
                    status=status.HTTP_409_CONFLICT,
                )

            # Rule 5: Atomic state transition
            asset.status = AssetStatus.CHECKED_OUT
            asset.save(update_fields=["status", "updated_at"])

            checkout = CheckOut.objects.create(
                asset=asset,
                employee=employee_target,
                due_at=data["due_at"],
            )

        return Response(
            CheckOutResponseSerializer(checkout).data,
            status=status.HTTP_201_CREATED,
        )


class CheckOutReturnView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        serializer = CheckOutReturnSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        condition_note = serializer.validated_data.get("condition_note", "")
        needs_maintenance = serializer.validated_data.get("needs_maintenance", False)

        with transaction.atomic():
            checkout = CheckOut.objects.select_for_update().filter(id=id).first()
            if not checkout:
                return Response({"detail": "CheckOut not found."}, status=status.HTTP_404_NOT_FOUND)

            # Rule 6: Returning an already-returned check-out -> 409 Conflict
            if checkout.returned_at is not None:
                return Response(
                    {"detail": "Check-out has already been returned."},
                    status=status.HTTP_409_CONFLICT,
                )

            now = timezone.now()
            checkout.returned_at = now
            if condition_note:
                checkout.condition_note = condition_note
            checkout.save(update_fields=["returned_at", "condition_note"])

            asset = Asset.objects.select_for_update().get(id=checkout.asset_id)
            asset.status = (
                AssetStatus.MAINTENANCE if needs_maintenance else AssetStatus.AVAILABLE
            )
            asset.save(update_fields=["status", "updated_at"])

        return Response(CheckOutResponseSerializer(checkout).data, status=status.HTTP_200_OK)


class EmployeeSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_code):
        employee = get_object_or_404(Employee, employee_code=employee_code)
        now = timezone.now()

        # Single DB query ORM aggregation computing all 4 numbers
        hold_duration_expr = ExpressionWrapper(
            F("returned_at") - F("checked_out_at"),
            output_field=DurationField(),
        )

        agg = employee.checkouts.aggregate(
            lifetime_checkout_count=Count("id"),
            count_currently_held=Count("id", filter=Q(returned_at__isnull=True)),
            count_currently_overdue=Count("id", filter=Q(returned_at__isnull=True, due_at__lt=now)),
            mean_hold_duration=Avg(hold_duration_expr, filter=Q(It looks like your code snippet got cut off right at the end of `EmployeeSummaryView` around `agg["count_`.

Here is the completed response dictionary and the rest of `EmployeeSummaryView` to finish the file:

```python
        return Response(
            {
                "employee_code": employee.employee_code,
                "lifetime_checkout_count": agg["lifetime_checkout_count"],
                "count_currently_held": agg["count_currently_held"],
                "count_currently_overdue": agg["count_currently_overdue"],
                "mean_hold_duration_days": mean_hold_days,
            },
            status=status.HTTP_200_OK,
        )