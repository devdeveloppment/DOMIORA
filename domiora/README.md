# DOMIORA — Plateforme SaaS Immobilière Premium

> **DOMIORA — Find. Rent. Own. Effortlessly.**

DOMIORA est une plateforme SaaS immobilière complète connectant acheteurs/locataires, agents
immobiliers et administrateurs autour d'un catalogue de biens d'exception. Construite avec
**Django 5 + Django REST Framework + Tailwind CSS**.

---

## 1. Stack technique

| Couche       | Technologie |
|--------------|-------------|
| Frontend     | HTML5, Tailwind CSS (CDN), Alpine.js, Chart.js |
| Backend      | Python / Django, Django REST Framework |
| Base de données | PostgreSQL (SQLite en local par défaut) |
| E-mails      | Django Email Backend (SMTP, configurable via `.env`) |
| Médias       | Upload d'images, galeries multiples |
| Sécurité     | CSRF, validation de formulaires, rôles & permissions, `.env` |

## 2. Architecture du projet

```
domiora/
├── config/             # Settings, urls, wsgi/asgi (le "projet" Django)
├── accounts/           # Utilisateur custom (rôles: buyer / agent / admin), auth
├── properties/         # Biens immobiliers, images, équipements
├── agents/             # Profils agents, spécialités
├── favorites/          # Favoris des acheteurs/locataires
├── rental_requests/    # Demandes (visite / location / achat) — renommé depuis "requests"
│                         pour éviter le conflit avec le package Python `requests`
├── transactions/       # Historique des ventes / locations, commissions
├── notifications/      # Notifications utilisateurs + centre de notifications
├── messaging/          # Messagerie interne acheteur ↔ agent
├── appointments/       # Prise de rendez-vous avec calendrier
├── site_settings/      # Paramètres système (singleton) — renommé depuis "settings"
│                         pour éviter le conflit avec `config/settings.py`
├── dashboard/          # 3 tableaux de bord séparés (acheteur / agent / admin)
├── api/                # API REST (Django REST Framework)
├── core/               # Pages publiques (accueil, à propos, contact), testimonials
├── templates/          # Tous les templates HTML + Tailwind
├── static/             # Assets statiques locaux
├── media/              # Fichiers uploadés (avatars, photos de biens...)
├── requirements.txt
├── .env.example
└── manage.py
```

> **Note sur les noms d'apps** : `requests/` et `settings/` ont été renommés en
> `rental_requests/` et `site_settings/` car ils entrent en conflit avec, respectivement,
> le package Python `requests` et le module `config/settings.py` de Django. Le comportement
> fonctionnel demandé reste identique.

## 3. Installation locale

```bash
# 1. Cloner / dézipper le projet puis se placer dedans
cd domiora

# 2. Créer un environnement virtuel (recommandé)
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Copier le fichier d'environnement et l'adapter
cp .env.example .env

# 5. Appliquer les migrations
python manage.py migrate

# 6. Créer un super-utilisateur (accès admin Django)
python manage.py createsuperuser

# 7. (Recommandé) Charger des données de démonstration complètes
python manage.py seed_demo_data

# 8. Lancer le serveur
python manage.py runserver
```

Le site est alors disponible sur **http://127.0.0.1:8000/**
et l'admin Django sur **http://127.0.0.1:8000/admin/**.

### Comptes de démonstration (créés par `seed_demo_data`)

| Rôle    | Identifiant       | Mot de passe   |
|---------|-------------------|----------------|
| Admin   | `admin`           | `Admin1234!`   |
| Agent   | `agent_sophie`    | `Agent1234!`   |
| Acheteur| `buyer_julie`     | `Buyer1234!`   |

(D'autres agents `agent_thomas`, `agent_marie`, `agent_hugo`... et acheteurs `buyer_antoine`, `buyer_claire`...
sont aussi créés (20 agents et 50 acheteurs au total), tous avec le même schéma de mot de passe
`Agent1234!` / `Buyer1234!`.)

## 4. Configuration PostgreSQL (production)

Par défaut, **si `DATABASE_URL` n'est pas défini**, le projet utilise SQLite (`db.sqlite3`)
pour permettre un démarrage immédiat sans installation supplémentaire.

Pour utiliser PostgreSQL :

```bash
# Créer la base et l'utilisateur PostgreSQL
sudo -u postgres psql
CREATE DATABASE domiora;
CREATE USER domiora WITH PASSWORD 'domiora';
GRANT ALL PRIVILEGES ON DATABASE domiora TO domiora;
\q
```

Puis, dans `.env` :

```
DATABASE_URL=postgres://domiora:domiora@localhost:5432/domiora
```

Relancer les migrations : `python manage.py migrate`.

## 5. Configuration des e-mails (SMTP)

En développement (`DEBUG=True`), les e-mails sont affichés dans la console par défaut
(aucune configuration requise). Pour activer un envoi SMTP réel, renseignez dans `.env` :

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=votre-email@gmail.com
EMAIL_HOST_PASSWORD=votre-mot-de-passe-application
DEFAULT_FROM_EMAIL=DOMIORA <contact@domiora.com>
```

Les e-mails sont envoyés automatiquement pour : inscription, contact, mise à jour
du statut d'une demande (acceptée/rejetée).

## 6. Fonctionnalités principales

### Innovation & fonctionnalités avancées (v2)
- **Assistant IA conversationnel** (bulle flottante) : recherche de biens en langage naturel.
  Fonctionne immédiatement en mode "intelligent par mots-clés" (sans coût), et passe en mode
  Claude (Anthropic) dès que `ANTHROPIC_API_KEY` est renseigné dans `.env`.
- **Comparateur de biens** : jusqu'à 3 biens comparés côte à côte (prix, surface, équipements...).
- **Avis & notation des agents** : les acheteurs notent et commentent un agent ; note moyenne calculée automatiquement.
- **Messagerie interne** : conversations directes acheteur ↔ agent, par bien ou en général.
- **Prise de rendez-vous** : demande de RDV avec un agent (date/heure), confirmation/annulation côté agent.
- **Centre de notifications** dédié + badge temps réel dans la barre de navigation.
- **Recherche intelligente (⌘K)** : palette de recherche globale (biens, villes, agents) avec auto-complétion.
- **Carte interactive** (Leaflet + OpenStreetMap, gratuite, sans clé API) : sur la fiche d'un bien et en vue "carte" du catalogue.
- **Visite virtuelle** : champ dédié pour intégrer un lien Matterport / vidéo 360° / YouTube.
- **Mode sombre / clair** (persisté par utilisateur).
- **Badges intelligents** : Nouveau, Coup de cœur, Exclusif, Top Agent, Agent vérifié.
- **Centre d'activité admin** : flux unifié des dernières actions (inscriptions, biens, demandes, transactions).
- **Partage social** : WhatsApp, Facebook, e-mail, lien copié, sur chaque fiche bien.

### Site public
- Page d'accueil premium (hero, recherche avancée, biens en vedette, agents, témoignages, stats)
- Recherche avancée multi-critères (type, transaction, prix, ville, pays, chambres, sdb, surface)
- Catalogue avec pagination, vue grille / liste, tri (récent / prix / popularité)
- Page détail (galerie, description, équipements, localisation, agent, formulaire de demande)
- Pages agents (liste, profil détaillé, portefeuille, contact)
- Page contact avec envoi d'e-mail automatique

### Authentification
- Inscription (acheteur ou agent), connexion, déconnexion
- Mot de passe oublié / réinitialisation (par e-mail)
- Modification du profil (y compris photo)

### Dashboard Acheteur / Locataire (`/dashboard/acheteur/`)
- Aperçu (statistiques personnelles)
- Favoris (ajout / suppression, persistant en base)
- Mes demandes (historique + statut)

### Dashboard Agent (`/dashboard/agent/`)
- Aperçu (KPIs, revenus, biens & demandes récents)
- Gestion des biens : CRUD complet, upload multi-images, publier/dépublier
- Demandes reçues : accepter / rejeter (déclenche notification + e-mail au client)
- Historique des transactions & revenus
- Profil agent (agence, licence, bio, réseaux sociaux)

### Dashboard Administrateur (`/dashboard/admin-panel/`)
- Totalement séparé du site public et du dashboard agent/acheteur
- Statistiques globales + graphique Chart.js (volume de transactions / 6 mois)
- Gestion des utilisateurs (CRUD, activation/suspension)
- Gestion des propriétés (validation des annonces, suppression)
- Historique complet des transactions (filtrage par statut)
- Paramètres système (nom du site, logo, coordonnées, réseaux sociaux, SMTP)
- Accès direct à l'admin Django (`/admin/`) pour une gestion bas niveau complète

### API REST (`/api/`)
Construite avec Django REST Framework, prête pour une future application mobile :

| Endpoint                  | Description |
|----------------------------|--------------|
| `POST /api/auth/token/`    | Authentification (obtention d'un token) |
| `/api/properties/`         | CRUD biens (lecture publique, écriture agents/admin) |
| `/api/agents/`              | Liste / détail des agents |
| `/api/amenities/`           | Équipements disponibles |
| `/api/specialties/`         | Spécialités agents |
| `/api/favorites/`           | Favoris de l'utilisateur connecté |
| `/api/requests/`            | Demandes de location/achat/visite |
| `/api/transactions/`        | Historique des transactions (lecture) |
| `/api/notifications/`       | Notifications utilisateur |
| `/api/me/`                  | Profil de l'utilisateur connecté |

Filtres, recherche et tri disponibles via `django-filter` / DRF (`?search=`, `?ordering=`,
`?property_type=`, `?transaction_type=`, etc.). Pagination par page de 12 éléments.

## 7. Données de démonstration

La commande `python manage.py seed_demo_data` génère :
- 1 administrateur, **20 agents** (spécialités, licences, taux de commission, vérification), **50 acheteurs**
- **120 propriétés** dont le **titre, le type et les photos sont cohérents entre eux** (une « Villa... »
  a bien des photos de villa et `property_type=villa`), réparties sur 15 villes (US, FR, TG) avec
  coordonnées GPS réalistes pour la carte interactive
- Favoris, demandes de visite/location/achat, transactions avec commissions calculées
- **Avis agents**, **rendez-vous**, **conversations de messagerie** avec échanges réalistes
- Notifications de bienvenue et 5 témoignages clients

Options :
```bash
python manage.py seed_demo_data --properties 200 --agents 20 --buyers 50
```

> Les photos de démonstration sont des URLs Unsplash hotlinkées par catégorie (pas de fichiers
> stockés dans `media/`). C'est un choix pragmatique pour un jeu de données riche sans pipeline
> d'upload : en production, les agents uploadent leurs propres photos via le dashboard (CRUD biens),
> qui prennent automatiquement le pas sur les photos de démonstration.

## 8. Sécurité

- Protection CSRF activée sur tous les formulaires
- Mots de passe hashés (PBKDF2 par défaut Django)
- Permissions par rôle (decorator `@role_required` + permissions DRF dédiées)
- Toutes les informations sensibles (clé secrète, identifiants SMTP/BDD) externalisées dans `.env`
- En production (`DEBUG=False`) : cookies sécurisés, redirection HTTPS, headers de sécurité activés

## 9. Déploiement en production (résumé)

```bash
DEBUG=False
ALLOWED_HOSTS=votredomaine.com
DATABASE_URL=postgres://...
CSRF_TRUSTED_ORIGINS=https://votredomaine.com

python manage.py collectstatic --noinput
python manage.py migrate
gunicorn config.wsgi:application
```

WhiteNoise est déjà configuré pour servir les fichiers statiques compressés directement
depuis Gunicorn (pas besoin de Nginx pour les assets en environnement simple).

## 10. Limites connues (transparence)

- **Photos de démonstration** : hotlinkées depuis Unsplash (pas de fichiers réels dans `media/`).
  Un agent qui uploade ses propres photos via le dashboard les remplace automatiquement.
- **Assistant IA** : le mode Claude nécessite votre propre clé `ANTHROPIC_API_KEY` (non fournie) ;
  le mode de secours par mots-clés n'a pas la nuance d'un LLM.
- **Mode sombre** : couverture large (pages principales, dashboards) mais pas garantie pixel-parfaite
  sur 100% des écrans secondaires.
- **Visite virtuelle 360°** : intégration par lien externe (Matterport/YouTube), pas de viewer 360° maison.
- **Tests automatisés** : aucun test unitaire/Django TestCase n'est inclus ; les vérifications de ce
  livrable ont été faites manuellement (parcours HTTP réels, voir section suivante).

## 11. Aller plus loin

- Brancher un vrai fournisseur de carte (Google Maps / Mapbox) sur la section "Localisation"
- Ajouter un module de signature électronique pour finaliser le cycle vente/location
- Ajouter Celery + Redis pour les notifications/e-mails asynchrones à plus grande échelle
- Étendre l'API pour l'application mobile (déjà prête côté endpoints)

---

**Contact projet :** businessriztech@gmail.com · +228 90 56 78 48 / +228 99 79 46 29
