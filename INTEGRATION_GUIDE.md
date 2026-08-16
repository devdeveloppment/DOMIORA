# DOMIORA - Guide d'Intégration Complète

## 📋 Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Configuration requise](#configuration-requise)
3. [Workflow de vérification d'identité](#workflow-de-vérification-didentité)
4. [API Endpoints](#api-endpoints)
5. [Assistant IA Gemini](#assistant-ia-gemini)
6. [Configuration ngrok](#configuration-ngrok)
7. [Tests et Dépannage](#tests-et-dépannage)

---

## Vue d'ensemble

Cette intégration ajoute les fonctionnalités suivantes à DOMIORA :

- ✅ Vérification automatique d'identité des propriétaires via n8n
- ✅ Workflow de validation admin avec notifications
- ✅ Emails automatiques (validation/refus)
- ✅ Assistant IA conversationnel avec Gemini API
- ✅ Recherche intelligente de propriétés
- ✅ Sécurité renforcée (validation fichiers, permissions)

---

## Configuration requise

### 1. Variables d'environnement (.env)

Ajoutez ces variables à votre fichier `.env` :

```bash
# Base URL pour les webhooks (utilisez ngrok pour localhost)
BASE_URL=https://abcd-1234.ngrok-free.app

# Clé API Gemini pour l'assistant IA
GEMINI_API_KEY=your_gemini_api_key_here

# Configuration SMTP Gmail
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=mewenemessedenis@gmail.com
EMAIL_HOST_PASSWORD=n g cw n j g k v h x m j m n d

# Webhooks n8n
N8N_IDENTITY_VERIFICATION_WEBHOOK=https://deniscodeur.app.n8n.cloud/webhook/domiora-identity-verification
N8N_ADMIN_NOTIFICATION_WEBHOOK=https://abcd-1234.ngrok-free.app/api/admin/notifications/
```

### 2. Migrations de base de données

Les migrations ont déjà été appliquées :
```bash
python manage.py makemigrations accounts
python manage.py migrate
```

### 3. Configuration Gmail

Pour utiliser Gmail comme serveur SMTP :
1. Activez la "2-step verification" sur votre compte Google
2. Générez un "App Password" dans les paramètres de sécurité
3. Utilisez ce mot de passe dans `EMAIL_HOST_PASSWORD`

---

## Workflow de vérification d'identité

### Étape 1: Soumission des documents

**Endpoint**: `POST /api/verification/submit/`

**Headers**:
```
Authorization: Token <votre_token>
Content-Type: multipart/form-data
```

**Body**:
```
id_card_front: <fichier image>
id_card_back: <fichier image>
id_document_type: "CNI"
id_document_number: "123456789"
```

**Réponse**:
```json
{
  "message": "Documents envoyés pour vérification",
  "status": "pending",
  "verification_id": 1,
  "n8n_sent": true
}
```

### Étape 2: Envoi vers n8n

Django envoie automatiquement les données au webhook n8n :
- URL: `https://deniscodeur.app.n8n.cloud/webhook/domiora-identity-verification`
- Données envoyées: owner_id, first_name, last_name, email, phone, URLs Cloudinary des documents

### Étape 3: Validation admin via n8n

Le workflow n8n attend la décision de l'admin, puis envoie vers Django :

**Endpoint**: `POST /api/verification/resume/{verification_id}/`

**Body (validation)**:
```json
{
  "decision": "validated",
  "reason": "",
  "reviewed_by": "admin@domiora.com"
}
```

**Body (refus)**:
```json
{
  "decision": "rejected",
  "reason": "Document illisible",
  "reviewed_by": "admin@domiora.com"
}
```

### Étape 4: Notifications automatiques

Django crée automatiquement :
- ✅ Notification interne pour le propriétaire
- ✅ Email HTML de validation ou refus
- ✅ Mise à jour du statut du propriétaire
- ✅ Activation de `can_publish_properties` si validé

---

## API Endpoints

### 1. Vérification d'identité

#### Soumettre des documents
```
POST /api/verification/submit/
```
- Authentification requise
- Réservé aux propriétaires
- Validation des fichiers (JPG, PNG, WebP, max 5MB)

#### Reprendre le workflow (webhook n8n)
```
POST /api/verification/resume/{verification_id}/
```
- Appelé par n8n après décision admin
- Met à jour le statut et envoie notifications

### 2. Assistant IA

#### Chat avec l'assistant
```
POST /api/chat/
```

**Body**:
```json
{
  "message": "Je cherche une maison 3 chambres à Lomé",
  "history": []
}
```

**Réponse**:
```json
{
  "response": "Voici les logements disponibles...",
  "matches": [
    {
      "title": "Villa moderne 3 chambres",
      "url": "/properties/villa-moderne/",
      "price": "500000 FCFA/mois",
      "image": "https://...",
      "city": "Lomé",
      "country": "Togo",
      "bedrooms": 3,
      "surface_area": 150
    }
  ],
  "source": "gemini"
}
```

### 3. Notifications Admin

#### Webhook pour notifications n8n
```
POST /api/admin/notifications/
```

**Body**:
```json
{
  "notification_type": "verification_approved",
  "title": "Identité validée",
  "message": "Votre identité a été validée...",
  "user_id": 123
}
```

---

## Assistant IA Gemini

### Fonctionnalités

L'assistant IA comprend :
- 🔍 Recherche de logements (ville, prix, chambres, type)
- 💰 Questions sur les prix et budgets
- 📍 Disponibilité des biens
- 📝 Processus de création de compte
- 🏠 Publication de propriétés
- ✅ Vérification d'identité
- ℹ️ Fonctionnement général de DOMIORA

### Recherche intelligente

L'assistant interroge PostgreSQL pour trouver des propriétés correspondantes :

**Exemple de requête**:
```
"Trouve-moi une maison 3 chambres à Lomé sous 600000 FCFA"
```

**Traitement**:
1. Analyse des critères (ville, chambres, prix)
2. Recherche dans le modèle Property
3. Filtrage par disponibilité et statut
4. Réponse naturelle avec liens vers les propriétés

### Fallback

Si l'API Gemini échoue, le système utilise des réponses basées sur des règles prédéfinies pour garantir une réponse.

---

## Configuration ngrok

### Pourquoi ngrok ?

n8n Cloud ne peut pas accéder à `localhost:8000`. ngrok crée un tunnel HTTPS public.

### Installation

```bash
# Windows (via Chocolatey)
choco install ngrok

# Ou téléchargez depuis https://ngrok.com/download
```

### Utilisation

```bash
# Démarrer ngrok sur le port 8000
ngrok http 8000

# Vous obtiendrez une URL comme: https://abcd-1234.ngrok-free.app
```

### Mise à jour de la configuration

1. Copiez l'URL ngrok générée
2. Mettez à jour `BASE_URL` dans `.env`
3. Mettez à jour `N8N_ADMIN_NOTIFICATION_WEBHOOK` dans `.env`
4. Redémarrez le serveur Django

### Version gratuite ngrok

- URL change à chaque redémarrage
- Mettez à jour les webhooks n8n après chaque redémarrage
- Pour la production, utilisez un domaine fixe (version payante)

---

## Tests et Dépannage

### 1. Tester la soumission de documents

```bash
# Obtenir un token d'authentification
curl -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "owner_user", "password": "password"}'

# Soumettre des documents
curl -X POST http://127.0.0.1:8000/api/verification/submit/ \
  -H "Authorization: Token <votre_token>" \
  -F "id_card_front=@front.jpg" \
  -F "id_card_back=@back.jpg" \
  -F "id_document_type=CNI" \
  -F "id_document_number=123456789"
```

### 2. Tester l'assistant IA

```bash
curl -X POST http://127.0.0.1:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Bonjour, je cherche un appartement à Lomé", "history": []}'
```

### 3. Vérifier les logs Django

```bash
# En développement, les emails sont affichés dans la console
# Vérifiez les logs pour les appels API n8n et Gemini
```

### Problèmes courants

**Erreur 404 sur Gemini API**:
- Vérifiez que `GEMINI_API_KEY` est correct dans `.env`
- Assurez-vous que la clé est active et a des crédits

**Erreur connexion SMTP**:
- Vérifiez le mot de passe d'application Gmail
- Assurez-vous que "Less secure apps" est activé ou utilisez App Password

**Webhook n8n timeout**:
- Vérifiez que ngrok est actif
- Assurez-vous que `BASE_URL` est correct dans `.env`
- Vérifiez les logs Django pour les erreurs

**Fichiers non acceptés**:
- Formats acceptés: JPG, PNG, WebP
- Taille maximale: 5MB
- Vérifiez le content-type du fichier

---

## Sécurité

### Validation des fichiers

- Types acceptés: image/jpeg, image/jpg, image/png, image/webp
- Taille maximale: 5MB
- Validation côté serveur

### Permissions API

- `verification_submit`: Authentifié + rôle OWNER uniquement
- `verification_resume`: Authentifié (webhook n8n)
- `chat`: Public (pour les visiteurs)
- `admin_notification_webhook`: Public (webhook n8n)

### Variables sensibles

Toutes les clés API et mots de passe sont dans `.env` (non inclus dans git).

---

## Structure du code

### Nouveaux fichiers créés

```
services/
├── __init__.py
├── n8n_service.py          # Communication avec n8n
└── email_service.py        # Envoi d'emails

templates/accounts/emails/
├── identity_verified.html  # Email validation
└── identity_rejected.html  # Email refus

api/
├── views.py                # Nouveaux endpoints API
└── urls.py                 # Routes API
```

### Modèles modifiés

- `accounts/models.py`:
  - Ajout de `can_publish_properties` à User
  - Ajout de champs n8n à IdentityVerificationRequest

- `notifications/models.py`:
  - Ajout de types de notification verification_approved/rejected

---

## Production

### Avant de déployer en production

1. **Remplacer ngrok par un vrai domaine**
   - Utilisez un nom de domaine avec HTTPS
   - Configurez les webhooks n8n avec l'URL de production

2. **Variables d'environnement de production**
   - Utilisez des clés API de production
   - Configurez SMTP avec un service d'envoi d'emails (SendGrid, Mailgun, etc.)

3. **Sécurité**
   - Activez HTTPS
   - Configurez `CSRF_COOKIE_SECURE = True`
   - Configurez `SESSION_COOKIE_SECURE = True`

4. **Monitoring**
   - Surveillez les logs d'erreurs API
   - Configurez des alertes pour les échecs d'envoi d'emails

---

## Support

Pour toute question ou problème, consultez :
- Logs Django dans la console
- Logs n8n dans le tableau de bord n8n
- Documentation Gemini API: https://ai.google.dev/docs

---

**Version**: 1.0  
**Date**: 10 Juillet 2026  
**Statut**: ✅ Intégration complète et fonctionnelle
