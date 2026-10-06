# Modèles pour le système de messagerie dans DOMIORA
# Ce fichier gère les conversations, messages, demandes de visite et rendez-vous

from django.db import models
from django.conf import settings


class Conversation(models.Model):
    """
    Représente une conversation entre un acheteur et un propriétaire ou agent.
    Une conversation est généralement liée à une propriété précise.
    """
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations_as_buyer")  # Acheteur/Locataire
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations_as_owner")  # Propriétaire/Agent
    property = models.ForeignKey("properties.Property", on_delete=models.SET_NULL, null=True, blank=True, related_name="conversations")  # Propriété concernée
    created_at = models.DateTimeField(auto_now_add=True)  # Date de création
    updated_at = models.DateTimeField(auto_now=True)  # Date de dernière activité

    class Meta:
        unique_together = ("buyer", "owner", "property")  # Une seule conversation par triplet
        ordering = ["-updated_at"]  # Tri par dernière activité décroissante

    def __str__(self):
        return f"{self.buyer} ↔ {self.owner}"

    def last_message(self):
        """Retourne le dernier message de la conversation"""
        return self.messages.order_by("-created_at").first()

    def unread_count_for(self, user):
        """Compte les messages non lus pour un utilisateur"""
        return self.messages.exclude(sender=user).filter(is_read=False).count()


class Message(models.Model):
    """
    Représente un message envoyé dans une conversation.
    Il peut s'agir d'un simple message texte ou d'un événement métier : visite, rendez-vous, etc.
    """
    class MessageType(models.TextChoices):
        """Types de messages disponibles"""
        TEXT = "text", "Message texte"
        VISIT_REQUEST = "visit_request", "Demande de visite"
        VISIT_ACCEPTED = "visit_accepted", "Visite acceptée"
        VISIT_REFUSED = "visit_refused", "Visite refusée"
        VISIT_PROPOSED = "visit_proposed", "Nouvelle date proposée"
        RENDEZVOUS_REQUEST = "rendezvous_request", "Demande de rendez-vous"
        RENDEZVOUS_ACCEPTED = "rendezvous_accepted", "Rendez-vous accepté"
        RENDEZVOUS_REFUSED = "rendezvous_refused", "Rendez-vous refusé"
        RENDEZVOUS_PROPOSED = "rendezvous_proposed", "Nouvelle date proposée"
        INFO = "info", "Information"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")  # Conversation parente
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")  # Expéditeur
    body = models.TextField()  # Contenu du message
    message_type = models.CharField(max_length=25, choices=MessageType.choices, default=MessageType.TEXT)  # Type de message
    is_read = models.BooleanField(default=False)  # Statut de lecture
    created_at = models.DateTimeField(auto_now_add=True)  # Date d'envoi

    # Champs spécifiques aux demandes de visite
    visit_request = models.ForeignKey('VisitRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name="messages", help_text="Related visit request if this message is about a visit")  # Demande de visite associée
    rendezvous_request = models.ForeignKey('RendezvousRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name="messages", help_text="Related rendezvous request if this message is about a rendezvous")  # Demande de rendez-vous associée
    proposed_date = models.DateTimeField(null=True, blank=True, help_text="Proposed date for visit or rendezvous")  # Date proposée
    visit_status = models.CharField(max_length=20, blank=True, help_text="Status of visit request")  # Statut de la demande

    class Meta:
        ordering = ["created_at"]  # Tri chronologique

    def __str__(self):
        return f"{self.sender}: {self.body[:30]}"


class VisitRequest(models.Model):
    """
    Demande de visite d'un bien immobilier par un client.
    Elle suit le cycle de vie complet : en attente, acceptée, refusée, date proposée, etc.
    """
    class Status(models.TextChoices):
        """Statuts possibles d'une demande de visite"""
        PENDING = "pending", "En attente"
        ACCEPTED = "accepted", "Acceptée"
        REFUSED = "refused", "Refusée"
        PROPOSED = "proposed", "Nouvelle date proposée"
        CANCELLED = "cancelled", "Annulée"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="visit_requests")  # Conversation associée
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_visit_requests")  # Demandeur
    proposed_date = models.DateTimeField()  # Date proposée
    message = models.TextField(help_text="Additional message from requester")  # Message additionnel
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)  # Statut actuel
    response_message = models.TextField(blank=True, help_text="Owner's response message")  # Message de réponse du propriétaire
    created_at = models.DateTimeField(auto_now_add=True)  # Date de création
    updated_at = models.DateTimeField(auto_now=True)  # Date de dernière modification

    class Meta:
        ordering = ["-created_at"]  # Tri par date décroissante

    def __str__(self):
        return f"Visit request for {self.conversation.property.title if self.conversation.property else 'Unknown'} - {self.status}"


class RendezvousRequest(models.Model):
    """
    Demande de rendez-vous entre un client et un propriétaire.
    Elle suit la même logique que les demandes de visite, mais pour un rendez-vous plus général.
    """
    class Status(models.TextChoices):
        """Statuts possibles d'une demande de rendez-vous"""
        PENDING = "pending", "En attente"
        ACCEPTED = "accepted", "Accepté"
        REFUSED = "refused", "Refusé"
        PROPOSED = "proposed", "Nouvelle date proposée"
        CANCELLED = "cancelled", "Annulé"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="rendezvous_requests")  # Conversation associée
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_rendezvous_requests")  # Demandeur
    proposed_date = models.DateTimeField()  # Date proposée
    message = models.TextField(help_text="Additional message from requester")  # Message additionnel
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)  # Statut actuel
    response_message = models.TextField(blank=True, help_text="Owner's response message")  # Message de réponse
    created_at = models.DateTimeField(auto_now_add=True)  # Date de création
    updated_at = models.DateTimeField(auto_now=True)  # Date de dernière modification

    class Meta:
        ordering = ["-created_at"]  # Tri par date décroissante

    def __str__(self):
        return f"Rendezvous request for {self.conversation.property.title if self.conversation.property else 'Unknown'} - {self.status}"
