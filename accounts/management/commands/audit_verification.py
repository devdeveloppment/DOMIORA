"""
Audit de cohérence des statuts de vérification des propriétaires (LECTURE SEULE par défaut).

Source de vérité : User.verification_status (conditionne la publication).
- IdentityVerificationRequest = dossier et historique des demandes.
- User.can_publish_properties = drapeau dérivé, synchronisé par approve()/reject().
- agents.Agent.is_verified = profil vitrine d'AGENT IMMOBILIER, sans lien avec la
  vérification d'identité ni avec les vérificateurs de terrain.

Un propriétaire « approuvé » SANS preuve (aucun dossier approuvé, aucune date de
validation) est signalé comme anomalie : la commande ne lui accorde JAMAIS de droit.
--fix n'aligne le drapeau que pour les comptes dont l'approbation est justifiée, et exige
--confirm. Aucune autre donnée n'est modifiée.
"""
from django.core.management.base import BaseCommand

from accounts.models import IdentityVerificationRequest, User


def evidence_for(owner):
    approved_request = owner.verification_requests.filter(status=IdentityVerificationRequest.Status.APPROVED).exists()
    return {
        "dossier_approuve": approved_request,
        "date_validation": bool(owner.verification_date),
        "piece_identite": bool(owner.id_document) or owner.verification_requests.exists(),
        "visite_terrain": bool(owner.field_visit_completed),
    }


class Command(BaseCommand):
    help = "Rapport (lecture seule) des incohérences de vérification des propriétaires."

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="Aligne can_publish pour les approbations justifiées uniquement.")
        parser.add_argument("--confirm", action="store_true", help="Obligatoire avec --fix.")

    def handle(self, *args, fix=False, confirm=False, **options):
        approved = User.VerificationStatus.APPROVED
        owners = User.objects.filter(role=User.Role.OWNER).order_by("pk")
        justified, unproven = [], []
        for owner in owners.filter(verification_status=approved):
            ev = evidence_for(owner)
            (justified if ev["dossier_approuve"] or ev["date_validation"] else unproven).append((owner, ev))

        self.stdout.write(f"Propriétaires : {owners.count()} · approuvés : {len(justified) + len(unproven)}")
        self.stdout.write("\nApprouvés SANS preuve (anomalie — état attendu : non vérifié, décision admin requise) :")
        for owner, ev in unproven:
            published = owner.properties.filter(is_published=True, is_validated=True).count()
            self.stdout.write(
                f"  id={owner.pk} can_publish={owner.can_publish_properties} preuves={ev} "
                f"annonces_publiees={published}"
            )
        mismatch = [o for o, _ in justified if not o.can_publish_properties]
        mismatch += list(owners.exclude(verification_status=approved).filter(can_publish_properties=True))
        self.stdout.write(f"\nDrapeau can_publish à aligner (approbations justifiées / non approuvés) : {len(mismatch)}")
        for owner in mismatch:
            self.stdout.write(f"  id={owner.pk} statut={owner.verification_status} can_publish={owner.can_publish_properties}")

        if not fix:
            self.stdout.write("\nLecture seule : aucune modification.")
            return
        if not confirm:
            self.stdout.write(self.style.WARNING("--fix exige --confirm. Aucune modification."))
            return
        for owner in mismatch:
            owner.can_publish_properties = owner.verification_status == approved
            owner.save(update_fields=["can_publish_properties"])
        self.stdout.write(self.style.SUCCESS(
            f"{len(mismatch)} drapeau(x) aligné(s). Les {len(unproven)} approbations sans preuve n'ont PAS été modifiées."))
