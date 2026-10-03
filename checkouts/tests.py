from datetime import timedelta
import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from checkouts.models import (
    Asset,
    AssetCategory,
    AssetStatus,
    CheckOut,
    Employee,
    OverdueNotice,
)
from checkouts.tasks import check_overdue_checkouts


@pytest.fixture
def api_client():
    user = User.objects.create_user(username="testuser", password="secretpassword")
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.fixture
def base_data(db):
    active_emp = Employee.objects.create(
        employee_code="EMP_ACT",
        full_name="Active Tech",
        email="active@artikate.io",
        is_active=True,
    )
    inactive_emp = Employee.objects.create(
        employee_code="EMP_INA",
        full_name="Inactive Tech",
        email="inactive@artikate.io",
        is_active=False,
    )
    available_asset = Asset.objects.create(
        asset_tag="TAG_AVAIL",
        name="Field Camera",
        category=AssetCategory.CAMERA,
        status=AssetStatus.AVAILABLE,
        purchase_date=timezone.now().date() - timedelta(days=30),
    )
    checked_out_asset = Asset.objects.create(
        asset_tag="TAG_CHECKED",
        name="Field Laptop",
        category=AssetCategory.LAPTOP,
        status=AssetStatus.CHECKED_OUT,
        purchase_date=timezone.now().date() - timedelta(days=60),
    )
    return {
        "active_emp": active_emp,
        "inactive_emp": inactive_emp,
        "available_asset": available_asset,
        "checked_out_asset": checked_out_asset,
    }


# Rule 1: Cannot checkout an asset that is not AVAILABLE -> 409
@pytest.mark.django_db
def test_checkout_rule_1_non_available_conflict(api_client, base_data):
    payload = {
        "asset_tag": base_data["checked_out_asset"].asset_tag,
        "employee_code": base_data["active_emp"].employee_code,
        "due_at": (timezone.now() + timedelta(days=5)).isoformat(),
    }
    response = api_client.post("/api/v1/checkouts/", payload, format="json")
    assert response.status_code == status.HTTP_409_CONFLICT


# Rule 2: Inactive employee cannot checkout -> 400
@pytest.mark.django_db
def test_checkout_rule_2_inactive_employee(api_client, base_data):
    payload = {
        "asset_tag": base_data["available_asset"].asset_tag,
        "employee_code": base_data["inactive_emp"].employee_code,
        "due_at": (timezone.now() + timedelta(days=5)).isoformat(),
    }
    response = api_client.post("/api/v1/checkouts/", payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# Rule 3: Max 3 open checkouts -> 409 on 4th
@pytest.mark.django_db
def test_checkout_rule_3_max_three_open_limit(api_client, base_data):
    emp = base_data["active_emp"]
    now = timezone.now()

    for i in range(3):
        a = Asset.objects.create(
            asset_tag=f"TAG_LIMIT_{i}",
            name=f"Sensor {i}",
            category=AssetCategory.SENSOR,
            status=AssetStatus.CHECKED_OUT,
            purchase_date=now.date(),
        )
        CheckOut.objects.create(
            asset=a,
            employee=emp,
            due_at=now + timedelta(days=2),
            returned_at=None,
        )

    payload = {
        "asset_tag": base_data["available_asset"].asset_tag,
        "employee_code": emp.employee_code,
        "due_at": (now + timedelta(days=5)).isoformat(),
    }
    response = api_client.post("/api/v1/checkouts/", payload, format="json")
    assert response.status_code == status.HTTP_409_CONFLICT


# Rule 4: due_at must be in the future and <= 30 days ahead
@pytest.mark.django_db
def test_checkout_rule_4_due_date_validation(api_client, base_data):
    now = timezone.now()
    res_past = api_client.post(
        "/api/v1/checkouts/",
        {
            "asset_tag": base_data["available_asset"].asset_tag,
            "employee_code": base_data["active_emp"].employee_code,
            "due_at": (now - timedelta(days=1)).isoformat(),
        },
        format="json",
    )
    assert res_past.status_code == status.HTTP_400_BAD_REQUEST

    res_far = api_client.post(
        "/api/v1/checkouts/",
        {
            "asset_tag": base_data["available_asset"].asset_tag,
            "employee_code": base_data["active_emp"].employee_code,
            "due_at": (now + timedelta(days=31)).isoformat(),
        },
        format="json",
    )
    assert res_far.status_code == status.HTTP_400_BAD_REQUEST


# Rule 5: Successful checkout transitions asset to CHECKED_OUT
@pytest.mark.django_db
def test_checkout_rule_5_successful_checkout(api_client, base_data):
    payload = {
        "asset_tag": base_data["available_asset"].asset_tag,
        "employee_code": base_data["active_emp"].employee_code,
        "due_at": (timezone.now() + timedelta(days=10)).isoformat(),
    }
    response = api_client.post("/api/v1/checkouts/", payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED

    base_data["available_asset"].refresh_from_db()
    assert base_data["available_asset"].status == AssetStatus.CHECKED_OUT


# Rule 6: Return sets returned_at, updates status, and rejects duplicate returns with 409
@pytest.mark.django_db
def test_checkout_rule_6_return_logic_and_maintenance(api_client, base_data):
    now = timezone.now()
    co = CheckOut.objects.create(
        asset=base_data["available_asset"],
        employee=base_data["active_emp"],
        due_at=now + timedelta(days=3),
    )
    CheckOut.objects.filter(id=co.id).update(checked_out_at=now - timedelta(days=2))
    base_data["available_asset"].status = AssetStatus.CHECKED_OUT
    base_data["available_asset"].save()

    res = api_client.post(
        f"/api/v1/checkouts/{co.id}/return/",
        {"condition_note": "Lens scratch", "needs_maintenance": True},
        format="json",
    )
    assert res.status_code == status.HTTP_200_OK

    base_data["available_asset"].refresh_from_db()
    assert base_data["available_asset"].status == AssetStatus.MAINTENANCE

    res_duplicate = api_client.post(f"/api/v1/checkouts/{co.id}/return/", {}, format="json")
    assert res_duplicate.status_code == status.HTTP_409_CONFLICT


# Rule 8: 404 for unknown asset or employee identifiers
@pytest.mark.django_db
def test_checkout_rule_8_unknown_identifiers_404(api_client, base_data):
    now = timezone.now()
    res_tag = api_client.post(
        "/api/v1/checkouts/",
        {
            "asset_tag": "NON_EXISTENT",
            "employee_code": base_data["active_emp"].employee_code,
            "due_at": (now + timedelta(days=1)).isoformat(),
        },
        format="json",
    )
    assert res_tag.status_code == status.HTTP_404_NOT_FOUND

    res_emp = api_client.post(
        "/api/v1/checkouts/",
        {
            "asset_tag": base_data["available_asset"].asset_tag,
            "employee_code": "NON_EXISTENT",
            "due_at": (now + timedelta(days=1)).isoformat(),
        },
        format="json",
    )
    assert res_emp.status_code == status.HTTP_404_NOT_FOUND


# Database constraint: unique checkout and notice_date
@pytest.mark.django_db
def test_overduenotice_daily_unique_constraint(db, base_data):
    now = timezone.now()
    today = now.date()
    co = CheckOut.objects.create(
        asset=base_data["available_asset"],
        employee=base_data["active_emp"],
        due_at=now - timedelta(days=2),
    )
    OverdueNotice.objects.create(checkout=co, notice_date=today)
    with pytest.raises(IntegrityError):
        OverdueNotice.objects.create(checkout=co, notice_date=today)


# Celery task idempotency
@pytest.mark.django_db
def test_celery_task_check_overdue_checkouts(db, base_data):
    now = timezone.now()
    today = now.date()
    co = CheckOut.objects.create(
        asset=base_data["available_asset"],
        employee=base_data["active_emp"],
        due_at=now - timedelta(days=5),
        returned_at=None,
    )

    result = check_overdue_checkouts()
    assert "Created: 1" in result
    assert OverdueNotice.objects.filter(checkout=co, notice_date=today).exists()

    result_second = check_overdue_checkouts()
    assert "Created: 0" in result_second
    assert "Skipped (already notified today): 1" in result_second


# Aggregation verification: Employee summary endpoint
@pytest.mark.django_db
def test_employee_summary_aggregation(api_client, base_data):
    emp = base_data["active_emp"]
    now = timezone.now()

    # Closed checkout: held for 4 days (checked out 10 days ago, returned 6 days ago)
    a1 = Asset.objects.create(
        asset_tag="TAG_SUMM_1",
        name="Dev Laptop",
        category=AssetCategory.LAPTOP,
        status=AssetStatus.AVAILABLE,
        purchase_date=now.date(),
    )
    c1 = CheckOut.objects.create(
        asset=a1,
        employee=emp,
        due_at=now - timedelta(days=5),
        returned_at=now - timedelta(days=6),
    )
    # Use update to bypass auto_now_add on checked_out_at
    CheckOut.objects.filter(id=c1.id).update(checked_out_at=now - timedelta(days=10))

    # Currently overdue checkout (due 2 days ago)
    a2 = Asset.objects.create(
        asset_tag="TAG_SUMM_2",
        name="Sensor 3D",
        category=AssetCategory.SENSOR,
        status=AssetStatus.CHECKED_OUT,
        purchase_date=now.date(),
    )
    c2 = CheckOut.objects.create(
        asset=a2,
        employee=emp,
        due_at=now - timedelta(days=2),
        returned_at=None,
    )
    CheckOut.objects.filter(id=c2.id).update(checked_out_at=now - timedelta(days=5))

    response = api_client.get(f"/api/v1/employees/{emp.employee_code}/summary/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["lifetime_checkout_count"] == 2
    assert data["count_currently_held"] == 1
    assert data["count_currently_overdue"] == 1
    assert data["mean_hold_duration_days"] == 4.0


# Rule 7: Concurrency & atomic state protection verification
@pytest.mark.django_db
def test_checkout_rule_7_concurrency_race(api_client, base_data):
    asset = base_data["available_asset"]
    emp = base_data["active_emp"]
    now = timezone.now()

    payload = {
        "asset_tag": asset.asset_tag,
        "employee_code": emp.employee_code,
        "due_at": (now + timedelta(days=5)).isoformat(),
    }

    res1 = api_client.post("/api/v1/checkouts/", payload, format="json")
    assert res1.status_code == status.HTTP_201_CREATED

    res2 = api_client.post("/api/v1/checkouts/", payload, format="json")
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert "not AVAILABLE" in res2.data["detail"]