"""
Audit de cohérence des statuts de vérification des propriétaires.

Source de vérité : User.verification_status (c'est lui qui conditionne la publication).
- IdentityVerificationRequest = dossier et historique des demandes.
- User.can_publish_properties = drapeau dérivé, synchronisé par approve()/reject().
- agents.Agent.is_verified = profil d'AGENT IMMOBILIER (vitrine), sans lien avec la
  vérification d'identité des propriétaires ni avec les vérificateurs de terrain.

Lecture seule par défaut ; --fix aligne uniquement can_publish_properties sur le statut.
"""
from django.core.management.base import BaseCommand

from accounts.models import IdentityVerificationRequest, User


class Command(BaseCommand):
    help = "Signale (et optionnellement corrige) les incohérences de vérification des propriétaires."

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="Aligne can_publish_properties sur verification_status.")

    def handle(self, *args, fix=False, **options):
        owners = User.objects.filter(role=User.Role.OWNER)
        approved = User.VerificationStatus.APPROVED
        flag_mismatch = owners.exclude(can_publish_properties=True).filter(verification_status=approved) | \
            owners.filter(can_publish_properties=True).exclude(verification_status=approved)
        self.stdout.write(f"Propriétaires : {owners.count()}")
        self.stdout.write(f"Drapeau can_publish incohérent : {flag_mismatch.count()}")

        no_request = owners.filter(verification_status=approved).exclude(
            verification_requests__status=IdentityVerificationRequest.Status.APPROVED).distinct()
        self.stdout.write(f"Approuvés sans dossier approuvé (validation manuelle ou données de démo) : {no_request.count()}")

        if fix:
            n1 = owners.filter(verification_status=approved).update(can_publish_properties=True)
            n2 = owners.exclude(verification_status=approved).update(can_publish_properties=False)
            self.stdout.write(self.style.SUCCESS(f"Drapeau aligné ({n1} autorisés, {n2} non autorisés)."))
        else:
            self.stdout.write("Lecture seule. Relancer avec --fix pour aligner le drapeau.")
