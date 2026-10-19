"""
Suspend la diffusion publique des annonces dont le propriétaire n'est pas vérifié.

Seul is_published passe à False : l'annonce, sa validation, ses médias, vidéos, favoris,
vues, relations payées et conversations sont conservés. Le propriétaire ne peut pas la
republier tant qu'il n'est pas vérifié (owner_property_toggle_publish l'exige déjà).

    python manage.py suspend_unverified_owner_listings [--owner ID ...]          # simulation
    python manage.py suspend_unverified_owner_listings --owner 93 --apply        # + journal JSON
    python manage.py suspend_unverified_owner_listings --rollback JOURNAL.json
"""
import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from properties.models import Property


class Command(BaseCommand):
    help = "Suspend (sans suppression) les annonces publiées de propriétaires non vérifiés."

    def add_arguments(self, parser):
        parser.add_argument("--owner", type=int, nargs="*", default=None)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--rollback", metavar="JOURNAL")

    def handle(self, *args, owner=None, apply=False, rollback=None, **options):
        if rollback:
            path = Path(rollback)
            if not path.exists():
                raise CommandError(f"Journal introuvable : {path}")
            ids = [e["id"] for e in json.loads(path.read_text(encoding="utf-8"))]
            n = Property.objects.filter(pk__in=ids).update(is_published=True)
            self.stdout.write(self.style.SUCCESS(f"{n} annonce(s) republiée(s)."))
            return
        qs = Property.objects.filter(is_published=True).exclude(
            owner__verification_status=User.VerificationStatus.APPROVED).select_related("owner")
        if owner:
            qs = qs.filter(owner_id__in=owner)
        items = list(qs)
        for p in items:
            self.stdout.write(f"  annonce id={p.pk} propriétaire id={p.owner_id} ({p.owner.verification_status}) → diffusion suspendue")
        self.stdout.write(f"Annonces concernées : {len(items)}")
        if not apply:
            self.stdout.write("Simulation : aucune modification.")
            return
        out = Path(settings.BASE_DIR).parent / "domiora_backups"
        out.mkdir(exist_ok=True)
        path = out / f"suspend_listings_{datetime.now():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps([{"id": p.pk, "owner_id": p.owner_id} for p in items], indent=2), encoding="utf-8")
        with transaction.atomic():
            n = Property.objects.filter(pk__in=[p.pk for p in items]).update(is_published=False)
        self.stdout.write(self.style.SUCCESS(f"{n} annonce(s) suspendue(s). Journal : {path}"))
