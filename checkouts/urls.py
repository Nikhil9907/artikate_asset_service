from django.urls import path
from .views import (
    HealthCheckView,
    AssetListCreateView,
    AssetDetailView,
    CheckOutCreateView,
    CheckOutReturnView,
    EmployeeSummaryView,
    OverdueReportView,
)

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health_check"),
    path("assets/", AssetListCreateView.as_view(), name="asset_list_create"),
    path("assets/<int:id>/", AssetDetailView.as_view(), name="asset_detail"),
    path("checkouts/", CheckOutCreateView.as_view(), name="checkout_create"),
    path("checkouts/<int:id>/return/", CheckOutReturnView.as_view(), name="checkout_return"),
    path(
        "employees/<str:employee_code>/summary/",
        EmployeeSummaryView.as_view(),
        name="employee_summary",
    ),
    path("reports/overdue/", OverdueReportView.as_view(), name="overdue_report"),
]
