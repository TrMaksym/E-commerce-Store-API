import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "cancel-expired-orders-every-hour": {
        "task": "store.tasks.cancel_expired_orders",
        "schedule": crontab(minute=0, hour="*"),
    },
}