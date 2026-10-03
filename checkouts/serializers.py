from datetime import timedelta
from django.utils import timezone
from rest_framework import serializers
from .models import Asset, Employee, CheckOut, OverdueNotice


class AssetSerializer(serializers.ModelSerializer):
    current_holder = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
            "id",
            "asset_tag",
            "name",
            "category",
            "status",
            "purchase_date",
            "created_at",
            "updated_at",
            "current_holder",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "current_holder"]

    def get_current_holder(self, obj):
        # Null when available, otherwise the holding employee's code and name
        if obj.status == "AVAILABLE":
            return None
        active_checkout = (
            obj.checkouts.filter(returned_at__isnull=True)
            .select_related("employee")
            .first()
        )
        if active_checkout and active_checkout.employee:
            return {
                "employee_code": active_checkout.employee.employee_code,
                "name": active_checkout.employee.full_name,
            }
        return None


class CheckOutCreateSerializer(serializers.Serializer):
    asset_tag = serializers.CharField(max_length=32)
    employee_code = serializers.CharField(max_length=16)
    due_at = serializers.DateTimeField()

    def validate_due_at(self, value):
        now = timezone.now()
        # Rule 4: due_at must be in the future and <= 30 days ahead of now
        if value <= now:
            raise serializers.ValidationError("due_at must be in the future.")
        if value > now + timedelta(days=30):
            raise serializers.ValidationError("due_at cannot exceed 30 days from now.")
        return value


class CheckOutReturnSerializer(serializers.Serializer):
    condition_note = serializers.CharField(required=False, allow_blank=True, default="")
    needs_maintenance = serializers.BooleanField(required=False, default=False)


class CheckOutResponseSerializer(serializers.ModelSerializer):
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)

    class Meta:
        model = CheckOut
        fields = [
            "id",
            "asset",
            "asset_tag",
            "employee",
            "employee_code",
            "checked_out_at",
            "due_at",
            "returned_at",
            "condition_note",
        ]