from django.db import models


class AssetCategory(models.TextChoices):
    CAMERA = "CAMERA", "Camera"
    LAPTOP = "LAPTOP", "Laptop"
    SENSOR = "SENSOR", "Sensor"
    VEHICLE = "VEHICLE", "Vehicle"


class AssetStatus(models.TextChoices):
    AVAILABLE = "AVAILABLE", "Available"
    CHECKED_OUT = "CHECKED_OUT", "Checked Out"
    MAINTENANCE = "MAINTENANCE", "Maintenance"


class Asset(models.Model):
    asset_tag = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=16, choices=AssetCategory.choices)
    status = models.CharField(
        max_length=16,
        choices=AssetStatus.choices,
        default=AssetStatus.AVAILABLE,
    )
    purchase_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"{self.name} ({self.asset_tag})"


class Employee(models.Model):
    employee_code = models.CharField(max_length=16, unique=True, db_index=True)
    full_name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.full_name} ({self.employee_code})"


class CheckOut(models.Model):
    asset = models.ForeignKey(
        Asset, on_delete=models.PROTECT, related_name="checkouts"
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="checkouts"
    )
    checked_out_at = models.DateTimeField(auto_now_add=True)
    due_at = models.DateTimeField()
    returned_at = models.DateTimeField(null=True, blank=True)
    condition_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-checked_out_at"]

    def __str__(self):
        return f"CheckOut #{self.id} - {self.asset.asset_tag} to {self.employee.employee_code}"


class OverdueNotice(models.Model):
    checkout = models.ForeignKey(
        CheckOut, on_delete=models.CASCADE, related_name="notices"
    )
    notice_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["checkout", "notice_date"],
                name="unique_checkout_notice_per_date",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notice for Checkout #{self.checkout_id} on {self.notice_date}"