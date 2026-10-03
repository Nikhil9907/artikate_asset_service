import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "artikate.settings")

app = Celery("artikate")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Daily schedule at 08:00 UTC
app.conf.beat_schedule = {
    "check-overdue-checkouts-daily-8am": {
        "task": "checkouts.tasks.check_overdue_checkouts",
        "schedule": crontab(hour=8, minute=0),
    },
}