"""Traite les échéances d'abonnement (expiration, annulation effective, plan programmé).
Idempotent : à lancer périodiquement (cron Render ou tâche planifiée), par exemple chaque heure."""
from django.core.management.base import BaseCommand

from owner_subscriptions.services import process_due


class Command(BaseCommand):
    help = "Traite les abonnements arrivés à échéance."

    def handle(self, *args, **options):
        self.stdout.write(f"{process_due()} abonnement(s) traité(s).")
