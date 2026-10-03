from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from checkouts.models import (
    Asset,
    AssetCategory,
    AssetStatus,
    CheckOut,
    Employee,
    OverdueNotice,
)


class Command(BaseCommand):
    help = "Seeds database with demo assets, employees, and checkouts (idempotent)."

    def handle(self, *args, **options):
        self.stdout.write("Starting idempotent database seeding...")
        now = timezone.now()
        today = now.date()

        with transaction.atomic():
            # 1. Seed 8 Assets across all 4 categories
            asset_specs = [
                ("AST-CAM-01", "Sony FX3 Cinema Camera", AssetCategory.CAMERA, AssetStatus.AVAILABLE, 120),
                ("AST-CAM-02", "Canon EOS R5 C", AssetCategory.CAMERA, AssetStatus.CHECKED_OUT, 90),
                ("AST-LAP-01", "MacBook Pro 16 M3 Max", AssetCategory.LAPTOP, AssetStatus.CHECKED_OUT, 180),
                ("AST-LAP-02", "Dell Precision 5680 Workstation", AssetCategory.LAPTOP, AssetStatus.AVAILABLE, 60),
                ("AST-SEN-01", "Velodyne LiDAR Puck", AssetCategory.SENSOR, AssetStatus.CHECKED_OUT, 200),
                ("AST-SEN-02", "FLIR A65 Thermal Core", AssetCategory.SENSOR, AssetStatus.MAINTENANCE, 300),
                ("AST-VEH-01", "Toyota Hilux Logistics Truck", AssetCategory.VEHICLE, AssetStatus.CHECKED_OUT, 400),
                ("AST-VEH-02", "Polaris Ranger Crew XP", AssetCategory.VEHICLE, AssetStatus.AVAILABLE, 150),
            ]
            assets = {}
            for tag, name, cat, stat, days_ago in asset_specs:
                asset, _ = Asset.objects.update_or_create(
                    asset_tag=tag,
                    defaults={
                        "name": name,
                        "category": cat,
                        "status": stat,
                        "purchase_date": today - timedelta(days=days_ago),
                    },
                )
                assets[tag] = asset

            # 2. Seed 4 Employees (1 Inactive)
            emp_specs = [
                ("EMP001", "Alice Vance", "alice.vance@artikate.internal", True),
                ("EMP002", "Gordon Freeman", "gordon.freeman@artikate.internal", True),
                ("EMP003", "Eli Vance", "eli.vance@artikate.internal", True),
                ("EMP004", "Wallace Breen", "wallace.breen@artikate.internal", False),  # Inactive
            ]
            employees = {}
            for code, name, email, active in emp_specs:
                emp, _ = Employee.objects.update_or_create(
                    employee_code=code,
                    defaults={
                        "full_name": name,
                        "email": email,
                        "is_active": active,
                    },
                )
                employees[code] = emp

            # 3. Clean checkout history for deterministic re-runs
            OverdueNotice.objects.all().delete()
            CheckOut.objects.all().delete()

            # 4. Create check-outs meeting all required criteria:
            # - Overdue 1: Due 10 days ago (Open)
            c_od1 = CheckOut.objects.create(
                asset=assets["AST-CAM-02"],
                employee=employees["EMP001"],
                checked_out_at=now - timedelta(days=20),
                due_at=now - timedelta(days=10),
                returned_at=None,
            )

            # - Overdue 2: Due 3 days ago (Open)
            c_od2 = CheckOut.objects.create(
                asset=assets["AST-SEN-01"],
                employee=employees["EMP002"],
                checked_out_at=now - timedelta(days=15),
                due_at=now - timedelta(days=3),
                returned_at=None,
            )

            # - Open (Not Overdue): Due in 5 days
            CheckOut.objects.create(
                asset=assets["AST-LAP-01"],
                employee=employees["EMP001"],
                checked_out_at=now - timedelta(days=2),
                due_at=now + timedelta(days=5),
                returned_at=None,
            )

            # - Open (Not Overdue): Due in 12 days
            CheckOut.objects.create(
                asset=assets["AST-VEH-01"],
                employee=employees["EMP002"],
                checked_out_at=now - timedelta(days=1),
                due_at=now + timedelta(days=12),
                returned_at=None,
            )

            # - Returned On Time 1: Returned 1 day before due_at
            CheckOut.objects.create(
                asset=assets["AST-LAP-02"],
                employee=employees["EMP003"],
                checked_out_at=now - timedelta(days=40),
                due_at=now - timedelta(days=25),
                returned_at=now - timedelta(days=26),
                condition_note="Returned in mint condition.",
            )

            # - Returned On Time 2: Returned 1 day before due_at
            CheckOut.objects.create(
                asset=assets["AST-VEH-02"],
                employee=employees["EMP002"],
                checked_out_at=now - timedelta(days=30),
                due_at=now - timedelta(days=10),
                returned_at=now - timedelta(days=11),
                condition_note="Clean and refueled.",
            )

            # - Returned Late 1: Due 14 days ago, returned 4 days ago
            CheckOut.objects.create(
                asset=assets["AST-SEN-02"],
                employee=employees["EMP001"],
                checked_out_at=now - timedelta(days=25),
                due_at=now - timedelta(days=14),
                returned_at=now - timedelta(days=4),
                condition_note="Housing cracked. Flagged for maintenance.",
            )

            # 5. Overdue notices for existing overdue items
            OverdueNotice.objects.get_or_create(checkout=c_od1, notice_date=today)
            OverdueNotice.objects.get_or_create(checkout=c_od2, notice_date=today)

        self.stdout.write(self.style.SUCCESS("Successfully seeded demo data."))