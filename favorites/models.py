# Modèle pour la gestion des favoris dans DOMIORA
# Ce fichier permet aux utilisateurs de sauvegarder les propriétés qui les intéressent

from django.db import models
from django.conf import settings


class Favorite(models.Model):
    """
    Modèle représentant les favoris des utilisateurs
    Permet de sauvegarder les propriétés intéressantes pour consultation ultérieure
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")  # Utilisateur qui ajoute le favori
    property = models.ForeignKey("properties.Property", on_delete=models.CASCADE, related_name="favorited_by")  # Propriété ajoutée aux favoris
    created_at = models.DateTimeField(auto_now_add=True)  # Date d'ajout aux favoris

    class Meta:
        unique_together = ("user", "property")  # Un utilisateur ne peut ajouter qu'une fois une propriété en favori
        ordering = ["-created_at"]  # Tri par date d'ajout décroissante

    def __str__(self):
        return f"{self.user} ♥ {self.property}"
