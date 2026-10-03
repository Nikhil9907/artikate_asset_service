import logging
from celery import shared_task
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import CheckOut, OverdueNotice

logger = logging.getLogger(__name__)


@shared_task
def check_overdue_checkouts():
    now = timezone.now()
    today = now.date()

    overdue_checkouts = CheckOut.objects.filter(
        returned_at__isnull=True,
        due_at__lt=now,
    ).select_related("asset", "employee")

    created_count = 0
    skipped_count = 0

    for checkout in overdue_checkouts:
        try:
            with transaction.atomic():
                _, created = OverdueNotice.objects.get_or_create(
                    checkout=checkout,
                    notice_date=today,
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1
        except IntegrityError:
            skipped_count += 1

    summary = (
        f"Overdue checkouts scan completed for {today}. "
        f"Created: {created_count}, Skipped (already notified today): {skipped_count}."
    )
    logger.info(summary)
    return summary