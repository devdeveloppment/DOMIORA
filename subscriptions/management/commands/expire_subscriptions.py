from django.core.management.base import BaseCommand
from django.utils import timezone
from subscriptions.models import AgentSubscription
from properties.models import Property
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Vérifie et expire les abonnements arrivés à terme, et masque les annonces associées.'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        
        # Trouver tous les abonnements actifs dont la date de fin est dépassée
        # Note: end_date peut être null (illimité), on exclut les end_date nulles
        expired_subs = AgentSubscription.objects.filter(
            status=AgentSubscription.Status.ACTIVE,
            end_date__lt=now
        )
        
        count = expired_subs.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("Aucun abonnement à expirer aujourd'hui."))
            return

        for sub in expired_subs:
            # Si le renouvellement auto est activé, on pourrait générer une facture ici.
            # Pour la V1, on marque simplement comme expiré.
            sub.status = AgentSubscription.Status.EXPIRED
            sub.save(update_fields=['status'])
            
            # Action: Masquer toutes les propriétés publiées par cet agent
            agent = sub.agent
            properties = Property.objects.filter(agent=agent, is_published=True)
            properties_count = properties.count()
            
            if properties_count > 0:
                properties.update(is_published=False)
            
            logger.info(f"Abonnement expiré pour l'agent {agent.user.email}. {properties_count} annonces masquées.")
            self.stdout.write(self.style.WARNING(f"Agent {agent.user.email} expiré. {properties_count} annonces masquées."))

        self.stdout.write(self.style.SUCCESS(f"Tâche terminée : {count} abonnements expirés traités."))
