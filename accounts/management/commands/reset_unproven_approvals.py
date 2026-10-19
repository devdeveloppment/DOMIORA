"""
Repasse en « non vérifié » les propriétaires approuvés SANS aucune preuve.

Critère (tous requis) : rôle owner, statut approved, aucun dossier d'identité approuvé,
aucune date de validation. Seuls verification_status et can_publish_properties changent ;
annonces, relations, messages et historique sont conservés.

    python manage.py reset_unproven_approvals              # simulation (aucune écriture)
    python manage.py reset_unproven_approvals --apply      # écrit + journal JSON de retour arrière
    python manage.py reset_unproven_approvals --rollback FICHIER.json
"""
import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import IdentityVerificationRequest, User

TARGET_STATUS = User.VerificationStatus.UNVERIFIED


def unproven_owners():
    return (
        User.objects.filter(role=User.Role.OWNER, verification_status=User.VerificationStatus.APPROVED,
                            verification_date__isnull=True)
        .exclude(verification_requests__status=IdentityVerificationRequest.Status.APPROVED)
        .distinct().order_by("pk")
    )


class Command(BaseCommand):
    help = "Repasse les approbations sans preuve en « non vérifié » (simulation par défaut)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--rollback", metavar="JOURNAL")

    def handle(self, *args, apply=False, rollback=None, **options):
        if rollback:
            return self._rollback(Path(rollback))
        owners = list(unproven_owners())
        self.stdout.write(f"Comptes concernés : {len(owners)}")
        for o in owners:
            published = o.properties.filter(is_published=True).count()
            self.stdout.write(f"  id={o.pk} {o.verification_status} → {TARGET_STATUS} ; "
                              f"can_publish {o.can_publish_properties} → False ; annonces publiées conservées : {published}")
        if not apply:
            self.stdout.write("Simulation : aucune modification. Relancer avec --apply.")
            return
        journal = [{"id": o.pk, "verification_status": o.verification_status,
                    "can_publish_properties": o.can_publish_properties} for o in owners]
        out_dir = Path(settings.BASE_DIR).parent / "domiora_backups"
        out_dir.mkdir(exist_ok=True)
        path = out_dir / f"reset_unproven_approvals_{datetime.now():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps(journal, indent=2), encoding="utf-8")
        with transaction.atomic():
            n = User.objects.filter(pk__in=[o.pk for o in owners]).update(
                verification_status=TARGET_STATUS, can_publish_properties=False)
        self.stdout.write(self.style.SUCCESS(f"{n} compte(s) modifié(s). Journal de retour arrière : {path}"))

    def _rollback(self, path):
        if not path.exists():
            raise CommandError(f"Journal introuvable : {path}")
        entries = json.loads(path.read_text(encoding="utf-8"))
        with transaction.atomic():
            for e in entries:
                User.objects.filter(pk=e["id"]).update(verification_status=e["verification_status"],
                                                       can_publish_properties=e["can_publish_properties"])
        self.stdout.write(self.style.SUCCESS(f"{len(entries)} compte(s) restauré(s)."))
