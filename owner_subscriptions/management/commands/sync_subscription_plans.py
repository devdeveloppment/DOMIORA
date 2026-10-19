"""Charge/actualise les plans à partir de settings.SUBSCRIPTION_PLAN_PROPOSALS (idempotent).
Ne touche jamais aux transactions déjà enregistrées (leurs montants sont figés)."""
from django.conf import settings
from django.core.management.base import BaseCommand

from owner_subscriptions.models import Plan


class Command(BaseCommand):
    help = "Synchronise les plans proposés (tarifs envisagés, non validés)."

    def handle(self, *args, **options):
        for p in settings.SUBSCRIPTION_PLAN_PROPOSALS:
            _, created = Plan.objects.update_or_create(code=p["code"], defaults={
                "name": p["name"], "price_xof": p["price_xof"], "visibility_level": p["visibility_level"],
                "max_promoted_listings": p["max_promoted_listings"], "order": p["order"],
                "features": p["features"], "is_active": p.get("active", True), "is_proposal": True, "is_demo": True,
            })
            self.stdout.write(f"{'créé' if created else 'mis à jour'} : {p['code']}")
