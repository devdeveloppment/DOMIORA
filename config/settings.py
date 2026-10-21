"""
Django settings for DOMIORA project.
"""
import os
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-me-in-production-please")
DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", ".onrender.com"])
# Développement uniquement : domaines ngrok et locaux ajoutés pour que les tunnels fonctionnent
# sans redémarrage. Jamais en production (DEBUG=False).
if DEBUG:
    for _ngrok_domain in [".ngrok-free.dev", ".ngrok-free.app", ".ngrok.io", "localhost", "127.0.0.1"]:
        if _ngrok_domain not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_ngrok_domain)

# ----------------------------------------------------------------------------
# Applications
# ----------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sitemaps",

    # Third party
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",

    # DOMIORA apps
    "accounts",
    "core",
    "properties",
    "agents",
    "favorites",
    "rental_requests",
    "transactions",
    "notifications",
    "site_settings",
    "messaging",
    "appointments",
    "dashboard",
    "api",
    "virtual_tours",
    "ar_furniture",
    "price_analysis",
    "property_boost",
    "ratings",
    "payments",
    "field_verification",
    "owner_subscriptions",
    "moderation",
]

MIDDLEWARE = [
    "config.middleware.SelectiveGZipMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "dashboard.middleware.DashboardRoleMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_settings",
                "notifications.context_processors.unread_notifications",
                "dashboard.context_processors.user_dash_role",
                "payments.context_processors.payment_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ----------------------------------------------------------------------------
# Database
# Defaults to SQLite for zero-config local dev; set DATABASE_URL in .env to
# point to PostgreSQL, e.g.:
#   DATABASE_URL=postgres://domiora:domiora@localhost:5432/domiora
# ----------------------------------------------------------------------------
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}
# SQLite timeout — évite les blocages liés à OneDrive qui synchronise db.sqlite3
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"].setdefault("OPTIONS", {})
    DATABASES["default"]["OPTIONS"]["timeout"] = 30

# Connection pooling for better performance
DATABASES["default"]["CONN_MAX_AGE"] = 60  # Reuse connections for 60 seconds

# ----------------------------------------------------------------------------
# Session
# ----------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 86400 * 7  # 7 days
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# ----------------------------------------------------------------------------
# Auth
# ----------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:redirect"
LOGOUT_REDIRECT_URL = "core:home"

# CSRF settings
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SECURE = False  # Set to True in production with HTTPS

# ----------------------------------------------------------------------------
# Internationalization
# ----------------------------------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ----------------------------------------------------------------------------
# Static & media files
# ----------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Ajout pour la compatibilité avec django-cloudinary-storage (qui cherche cette variable)
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    "videos": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": BASE_DIR / "media" / "properties" / "generated_tours",
            "base_url": "/media/properties/generated_tours/",
        }
    },
}

WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_MAX_AGE = 31536000  # 1 year cache for hashed static files

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

CLOUDINARY_URL = env("CLOUDINARY_URL", default=None)
if CLOUDINARY_URL:
    INSTALLED_APPS.append('cloudinary')
    INSTALLED_APPS.append('cloudinary_storage')
    STORAGES["default"] = {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"}

# Fichiers sensibles (core/private_storage.py) : jamais servis par /media/.
PRIVATE_MEDIA_ROOT = env("PRIVATE_MEDIA_ROOT", default="") or str(BASE_DIR / "private_media")
PRIVATE_MEDIA_BACKEND = env("PRIVATE_MEDIA_BACKEND", default="cloudinary" if CLOUDINARY_URL else "filesystem")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ----------------------------------------------------------------------------
# Caching — LocMemCache for single-process, switch to Redis in production
# ----------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "domiora-cache",
        "TIMEOUT": 300,
    }
}

# ----------------------------------------------------------------------------
# Email (SMTP via .env). Falls back to console backend in DEBUG so the
# project runs out of the box without a mail server.
# ----------------------------------------------------------------------------
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend" if DEBUG else "services.mail_backend.BackgroundSMTPBackend",
)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="DOMIORA <denistchil@gmail.com>")
ADMIN_NOTIFICATION_EMAIL = env("ADMIN_NOTIFICATION_EMAIL", default="denistchil@gmail.com")

# Base URL for n8n webhooks (use ngrok for localhost)
# Sur Render, RENDER_EXTERNAL_URL (fournie par la plateforme) sert de valeur par défaut.
BASE_URL = env("BASE_URL", default=env("RENDER_EXTERNAL_URL", default="http://127.0.0.1:8000"))

# Mistral API configuration for the AI assistant
MISTRAL_API_KEY = env("MISTRAL_API_KEY", default="")
MISTRAL_MODEL = env("MISTRAL_MODEL", default="ministral-14b-latest")

# n8n Webhooks
N8N_IDENTITY_VERIFICATION_WEBHOOK = env(
    "N8N_IDENTITY_VERIFICATION_WEBHOOK",
    default="https://deniscodeur.app.n8n.cloud/webhook/domiora-identity-verification"
)

# Performance optimizations
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "domiora-cache",
        "OPTIONS": {
            "MAX_ENTRIES": 1000,
        }
    }
}

# Static files caching
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

N8N_ADMIN_NOTIFICATION_WEBHOOK = env("N8N_ADMIN_NOTIFICATION_WEBHOOK", default="")

# ----------------------------------------------------------------------------
# Django REST Framework
# ----------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 12,
}

# ----------------------------------------------------------------------------
# Security (mostly relevant once DEBUG=False in production)
# ----------------------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
if env("RENDER_EXTERNAL_URL", default="") and env("RENDER_EXTERNAL_URL") not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(env("RENDER_EXTERNAL_URL"))
# Développement uniquement : origines ngrok et locales (jamais de confiance CSRF envers
# des tunnels tiers en production).
if DEBUG:
    for _origin in [
        "https://*.ngrok-free.dev",
        "https://*.ngrok-free.app",
        "https://*.ngrok.io",
        "http://localhost",
        "http://127.0.0.1",
    ]:
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)
if not DEBUG:
    # Render termine le HTTPS devant l'application et transmet X-Forwarded-Proto :
    # sans cet en-tête, SECURE_SSL_REDIRECT provoquerait une boucle de redirection.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

SITE_NAME = "DOMIORA"

# Optional secondary provider used when Mistral is unavailable.
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", default="claude-sonnet-5-5")
ANTHROPIC_EFFORT = env("ANTHROPIC_EFFORT", default="low")

# Limitation des requêtes IA (recherche intelligente, comparateur, assistant)
AI_RATE_LIMIT = env.int("AI_RATE_LIMIT", default=20)
AI_RATE_WINDOW_SECONDS = env.int("AI_RATE_WINDOW_SECONDS", default=60)

# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# ----------------------------------------------------------------------------
# Payment Settings
# ----------------------------------------------------------------------------
# Héritage : ni PAYMENT_LINK ni PAYMENT_AMOUNT ne sont utilisés par les parcours actifs.
# PAYMENT_AMOUNT (2000) contredit le tarif réellement appliqué (500 FCFA) — conservé
# uniquement pour compatibilité ; la source de vérité est CONTACT_FEE_AMOUNT ci-dessous.
PAYMENT_LINK = "https://neopixel-studio.mymaketou.store/fr/products/domiora/checkout"
PAYMENT_AMOUNT = 2000  # FCFA (obsolète)

# Frais de mise en relation client ↔ propriétaire (une seule fois par propriétaire).
# 500 FCFA est la valeur appliquée jusqu'ici par le code et affichée dans l'interface.
CONTACT_FEE_AMOUNT = env.int("CONTACT_FEE_AMOUNT", default=500)
CONTACT_FEE_CURRENCY = "XOF"

# Mode de paiement : "simulation" (démonstration, aucun argent réel, aucun appel FedaPay)
# ou "fedapay" (fournisseur réel). La simulation est active par défaut uniquement en
# développement (DEBUG=True). En production elle doit être demandée explicitement ET
# confirmée par PAYMENT_SIMULATION_ALLOWED_IN_PRODUCTION=True (double verrou).
PAYMENT_MODE = env("PAYMENT_MODE", default="simulation" if DEBUG else "fedapay")
if PAYMENT_MODE not in ("simulation", "fedapay"):
    PAYMENT_MODE = "fedapay"
if PAYMENT_MODE == "simulation" and not DEBUG and not env.bool(
    "PAYMENT_SIMULATION_ALLOWED_IN_PRODUCTION", default=False
):
    PAYMENT_MODE = "fedapay"
# Abonnements propriétaires / agents. Actifs par défaut en développement uniquement ;
# en production ils restent désactivés tant que les tarifs ne sont pas validés.
# Les paiements d'abonnement sont TOUJOURS simulés (aucun fournisseur réel branché).
OWNER_SUBSCRIPTIONS_ENABLED = env.bool("OWNER_SUBSCRIPTIONS_ENABLED", default=DEBUG)
# Essai gratuit préparé (30 jours) mais INACTIF tant qu'il n'est pas validé :
# - SUBSCRIPTION_TRIAL_ENABLED=False par défaut ;
# - seuls les propriétaires inscrits à partir de SUBSCRIPTION_TRIAL_ELIGIBLE_FROM (AAAA-MM-JJ)
#   y ont droit : les anciens comptes ne le reçoivent jamais automatiquement (vide = personne).
SUBSCRIPTION_TRIAL_ENABLED = env.bool("SUBSCRIPTION_TRIAL_ENABLED", default=False)
SUBSCRIPTION_TRIAL_DAYS = env.int("SUBSCRIPTION_TRIAL_DAYS", default=30)
SUBSCRIPTION_TRIAL_ELIGIBLE_FROM = env("SUBSCRIPTION_TRIAL_ELIGIBLE_FROM", default="")
# PROPOSITIONS tarifaires (non validées). Chargées en base par
# `manage.py sync_subscription_plans` ; la base devient ensuite la source de vérité.
# Aucun tarif de 700 FCFA n'existe dans le code ni l'historique Git (seul « 700 » métier : une
# distance en mètres dans properties/views.py). Les frais de mise en relation sont de 500 FCFA.
SUBSCRIPTION_PLAN_PROPOSALS = [
    {"code": "gratuit", "name": "Gratuit", "price_xof": 0, "visibility_level": 0, "max_promoted_listings": 0,
     "order": 0, "features": ["Publication des annonces après vérification", "Classement organique normal",
                              "Messagerie et demandes de visite"]},
    {"code": "intermediaire", "name": "Intermédiaire", "price_xof": 1000, "visibility_level": 1, "max_promoted_listings": 1,
     "order": 1, "features": ["Tout le plan Gratuit", "Priorité de visibilité niveau 1", "1 annonce mise en avant (Sponsorisé)"]},
    {"code": "superieur", "name": "Supérieur", "price_xof": 2000, "visibility_level": 2, "max_promoted_listings": 3,
     "order": 2, "features": ["Tout le plan Intermédiaire", "Priorité de visibilité niveau 2", "3 annonces mises en avant"]},
    {"code": "premium", "name": "Premium", "price_xof": 5000, "visibility_level": 3, "max_promoted_listings": 5,
     "order": 3, "features": ["Tout le plan Supérieur", "Priorité de visibilité niveau 3", "5 annonces mises en avant"]},
    # Quatrième niveau envisagé : tarif et avantages à définir → non souscriptible.
    {"code": "entreprise", "name": "Entreprise (à définir)", "price_xof": None, "visibility_level": 3,
     "max_promoted_listings": 5, "order": 4, "active": False, "features": ["Avantages à définir"]},
]

# Classement des annonces (voir properties/ranking.py). Pondérations configurables.
RANKING_WEIGHTS = {
    "freshness": 30,      # récence (décroît sur RANKING_FRESHNESS_DAYS)
    "quality": 30,        # complétude : photos, description, surface, coordonnées
    "verified": 10,       # propriétaire vérifié
    "plan_per_level": 6,  # bonus par niveau de plan (plafonné, voir RANKING_PLAN_BONUS_CAP)
}
RANKING_FRESHNESS_DAYS = 60
RANKING_PLAN_BONUS_CAP = 18          # le bonus d'abonnement ne dépasse jamais ~20 % du score
RANKING_SPONSORED_SLOTS = 2          # emplacements « Sponsorisé » en tête de la 1re page
# Fraîcheur du badge « Vérifié DOMIORA » (mois après la dernière validation).
VERIFICATION_FRESHNESS_MONTHS = env.int("VERIFICATION_FRESHNESS_MONTHS", default=12)
# Isolation de la démonstration : la simulation n'est utilisable qu'entre comptes marqués
# is_demo (client ET propriétaire). Obligatoire par défaut hors développement.
PAYMENT_SIMULATION_DEMO_ACCOUNTS_ONLY = env.bool("PAYMENT_SIMULATION_DEMO_ACCOUNTS_ONLY", default=not DEBUG)
# Durée de validité d'une tentative de paiement en attente (minutes).
PAYMENT_ATTEMPT_TTL_MINUTES = env.int("PAYMENT_ATTEMPT_TTL_MINUTES", default=30)

# FedaPay - passerelle de paiement
# FEDAPAY_SANDBOX=True en dev, False en production
FEDAPAY_PUBLIC_KEY = env("FEDAPAY_PUBLIC_KEY", default="")
FEDAPAY_SECRET_KEY = env("FEDAPAY_SECRET_KEY", default="")
FEDAPAY_SANDBOX = env.bool("FEDAPAY_SANDBOX", default=True)

# ----------------------------------------------------------------------------
# Celery Configuration
# ----------------------------------------------------------------------------
# Production (Render) : REDIS_URL = Render Key Value, partagé entre le service web
# et le Background Worker Celery.
# Développement local : broker "filesystem" (même machine uniquement), worker lancé avec
#   celery -A config worker --pool=solo --loglevel=info      (Windows)
#   celery -A config worker --concurrency=1 --loglevel=info  (Linux/macOS)
# Le broker filesystem ne doit jamais être utilisé entre plusieurs services Render.
REDIS_URL = env("REDIS_URL", default="")
if REDIS_URL:
    CELERY_BROKER_URL = REDIS_URL
    # Résultats conservés uniquement pour les tâches qui le demandent explicitement
    # (diagnostic `manage.py verify_virtual_tour`) ; la génération vidéo n'en produit pas.
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_RESULT_EXPIRES = 3600
else:
    CELERY_BROKER_URL = "filesystem://"
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        "data_folder_in": str(BASE_DIR / ".celery" / "broker" / "out"),
        "data_folder_out": str(BASE_DIR / ".celery" / "broker" / "out"),
        "data_folder_processed": str(BASE_DIR / ".celery" / "broker" / "processed"),
    }
    # Le transport filesystem ne crée pas ses dossiers : sans eux, toute mise en file échoue
    # (FileNotFoundError) et la visite virtuelle passe en erreur, notamment sur un conteneur Render neuf.
    for _folder in set(CELERY_BROKER_TRANSPORT_OPTIONS.values()):
        os.makedirs(_folder, exist_ok=True)
# L'avancement de la génération vidéo est suivi dans le modèle Property (pas dans les résultats Celery).
CELERY_TASK_IGNORE_RESULT = True
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
# Dev uniquement : exécute les tâches dans la requête (sans worker). Jamais en production.
CELERY_TASK_ALWAYS_EAGER = DEBUG and env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# Si le broker est indisponible, ne pas bloquer la requête HTTP qui met la tâche en file.
CELERY_TASK_PUBLISH_RETRY_POLICY = {"max_retries": 2, "interval_start": 0, "interval_step": 0.5, "interval_max": 1}
CELERY_BROKER_CONNECTION_TIMEOUT = 3

# ----------------------------------------------------------------------------
# Visite virtuelle (génération vidéo FFmpeg, cf. properties/video/)
# ----------------------------------------------------------------------------
VIRTUAL_TOUR_MIN_PHOTOS = 3
VIRTUAL_TOUR_MAX_PHOTOS = 20
# 720p par défaut : rendu fluide et stable sur une petite instance de worker.
VIRTUAL_TOUR_RESOLUTION = env("VIRTUAL_TOUR_RESOLUTION", default="1280x720")
VIRTUAL_TOUR_FPS = env.int("VIRTUAL_TOUR_FPS", default=25)
# Binaire FFmpeg explicite (sinon : ffmpeg du PATH, puis binaire fourni par imageio-ffmpeg).
FFMPEG_BINARY = env("FFMPEG_BINARY", default="")
VIRTUAL_TOUR_SOFT_TIME_LIMIT = env.int("VIRTUAL_TOUR_SOFT_TIME_LIMIT", default=900)
# Musique de fond : désactivée (aucune piste fournie). Chemin local d'un fichier audio libre de droits.
VIRTUAL_TOUR_MUSIC_PATH = env("VIRTUAL_TOUR_MUSIC_PATH", default="")

