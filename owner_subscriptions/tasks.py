"""Tâche périodique (Celery beat) équivalente à `manage.py process_owner_subscriptions`."""
from celery import shared_task


@shared_task(name="owner_subscriptions.process_due", ignore_result=True, soft_time_limit=120)
def process_owner_subscriptions_task():
    from .services import process_due

    return process_due()
