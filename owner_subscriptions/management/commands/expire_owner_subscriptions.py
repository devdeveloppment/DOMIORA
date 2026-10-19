from django.core.management.base import BaseCommand

from owner_subscriptions.services import expire_due


class Command(BaseCommand):
    help = "Marque comme expirés les abonnements (simulés) arrivés à échéance."

    def handle(self, *args, **options):
        self.stdout.write(f"{expire_due()} abonnement(s) expiré(s).")
