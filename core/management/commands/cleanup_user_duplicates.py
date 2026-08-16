from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import User


class Command(BaseCommand):
    help = 'Identifie et nettoie les doublons d\'utilisateurs basés sur l\'email'

    def handle(self, *args, **options):
        self.stdout.write("Recherche des doublons d'utilisateurs...")
        
        # Trouver les emails en double
        from django.db.models import Count
        duplicate_emails = (
            User.objects.values('email')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
            .exclude(email='')
            .order_by('-count')
        )
        
        total_duplicates = duplicate_emails.count()
        
        if total_duplicates == 0:
            self.stdout.write(self.style.SUCCESS("Aucun doublon d'email trouvé."))
            return
        
        self.stdout.write(f"Trouvé {total_duplicates} emails avec des doublons.")
        
        # Afficher les détails
        for entry in duplicate_emails:
            email = entry['email']
            count = entry['count']
            
            self.stdout.write(f"\nEmail: {email} ({count} utilisateurs)")
            
            # Récupérer tous les utilisateurs avec cet email
            users = User.objects.filter(email=email).order_by('-date_joined')
            
            for user in users:
                self.stdout.write(f"  - {user.username} (ID: {user.id}, créé: {user.date_joined}, rôle: {user.role})")
        
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(f"Total: {total_duplicates} emails avec doublons")
        self.stdout.write(f"{'='*50}")
        
        response = input("\nVoulez-vous supprimer les doublons (garder le plus récent pour chaque email)? (oui/non): ")
        
        if response.lower() not in ['oui', 'yes', 'o', 'y']:
            self.stdout.write(self.style.WARNING("Opération annulée."))
            return
        
        # Suppression des doublons
        deleted_count = 0
        with transaction.atomic():
            for entry in duplicate_emails:
                email = entry['email']
                users = User.objects.filter(email=email).order_by('-date_joined')
                
                # Garder le premier (plus récent), supprimer les autres
                user_to_keep = users.first()
                users_to_delete = users[1:]
                
                for user in users_to_delete:
                    username = user.username
                    user.delete()
                    self.stdout.write(f"Supprimé: {username} (ID: {user.id})")
                    deleted_count += 1
        
        self.stdout.write(self.style.SUCCESS(f"\nNettoyage terminé! {deleted_count} utilisateurs supprimés."))
