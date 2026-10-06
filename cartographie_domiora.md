# CARTOGRAPHIE COMPLÈTE DU PROJET DOMIORA
**Phase 0 — Rapport d'analyse read-only**
Contexte de session : conversation précédente compactée + reprise.
Date d'analyse : 2026-08-18.

---

## A. Architecture générale

### A.1 Pile technologique serveur
| Couche | Technologie | Version / précision |
|---|---|---|
| Framework web | Django | 5.x |
| API REST | Django REST Framework (DRF) | avec `TokenAuthentication` + `SessionAuthentication` |
| AuthUtilisateurs | `AbstractUser` personnalisé | `accounts.User` (Role enum : CLIENT/BUYER/OWNER/AGENT/ADMIN) |
| ORM | Django ORM | SQLite (dev, default) / PostgreSQL (prod via `DATABASE_URL` / `dj-database-url`) |
| Template engine | Django templates | `APP_DIRS=True`, `DIRS=[BASE_DIR/templates]`, 3 context processors propriétaires |
| Tâches asynchrones | Celery | 5.4 — **broker = filesystem** (`celery.py` configure `broker_url` sur un répertoire local) ; Redis commenté comme backend de résultats |
| Cache | `LocMemCache` | style « Cloudflare », configuration en mémoire locale |
| Stockage fichiers | Whitenoise (static build) | + Cloudinary **optionnel** (conditionné) ; media via `django.core.files` défaut |
| Traitement médias | Pillow | images propriétés ; FFmpeg appelé **de manière synchrone** (pas via Celery) pour génération de visites virtuelles |
| Géolocalisation | Formule de Haversine | implémentée dans `properties/views.py` (`_haversine_km`) — recherche par rayon en km |
| Sécurité | CSRF / Session cookies | `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SECURE=False` (à activer en prod HTTPS), `CSRF_COOKIE_*`, `XFrameOptionsMiddleware` |
| Email | SMTP via `.env` | `EMAIL_HOST/USER/PASSWORD` — fallback `fail_silently=True` |
| Logging | `logging.config` | loggers par app (`properties`, `dashboard`, `accounts`, `core`, `api`, `services`) |

### A.2 Pile technologie client (frontend)
| Élément | Détails |
|---|---|
| CSS | Tailwind CSS (v3, **CDN-loaded** via `https://cdn.jsdelivr.net/npm/tailwindcss@2` dans `base.html`), classes utilitaires dans chaque template |
| JS interacctif | Alpine.js (CDN, `x-data`, `x-show`, `x-cloak`, `x-transition`) |
| JS CDN | 3 bibliothèques externes chargeées via CDN dans `base.html` |
| JS local | **13 fichiers JS locaux commentés** dans `base.html` comme « disabled for performance » (inutilisés actuellement) |
| WebSocket | **Absent** — la messagerie est purement HTTP-request based (`POST` form / DRF) |
| Responsive | Tailwind utilities (`sm:`, `lg:`, `md:` breakpoints); menus hamburger mobile via Alpine |

### A.3 Structure de l'application Django
```
domiora/
├── config/                  # projet Django (settings, urls, wsgi, asgi, celery.py)
├── templates/               # templates globaux (base.html, dashboard_base.html) + /partials + /properties + /dashboard + /accounts + /core + /messaging + /appointments + /notifications + /rental_requests + /agents
├── accounts/                # User model, auth, inscription, profil
├── core/                    # pages publiques (home, about, contact, blog, services, assistant_chat, donate, search_suggestions)
├── properties/              # Property model + vues + paiement CinetPay + recherche
├── agents/                  # Agent model, spécialités, avis
├── favorites/               # Favoris (Property↔User)
├── rental_requests/         # Demandes location/vente/visite (PropertyRequest)
├── transactions/            # Transaction commission + PaiementCinetPay
├── notifications/           # Notification in-app
├── site_settings/           # Réglages site (RS, téléphone, couleurs, etc.)
├── messaging/               # Conversation/Message + VisitRequest/RendezvousRequest
├── appointments/            # Rendez-vous (Appointment model + vues)
├── dashboard/               # Dashboard role-based (middleware + decorators + context_processors + vues)
├── api/                     # DRF ViewSets + endpoints REST
├── virtual_tours/           # (app déclarée) visite vidéo 360° via FFmpeg
├── ar_furniture/            # (app déclarée) mobilier AR
├── price_analysis/          # (app déclarée) analyse prix
├── property_boost/          # (app déclarée) boost annonce / mise en avant
└── services/                # ai_assistant.py (Mistral), email_service.py, n8n_service.py
```

### A.4 Principaux flux applicatifs
1. **Propriétaire → Publier un bien** : `/accounts/publish_landing/` → register_owner → login → `/dashboard/proprietaire/` → création de propriété (form + images) → validation → liste sur site.
2. **Client → Contacter un propriétaire** : page property_detail → clic « Contacter » → paiement CinetPay (500 FCFA) → `register_client_post_payment` crée le compte client automatiquement → `PropertyUnlock` créé → page `payment_confirmation` affiche le téléphone/WhatsApp/adresse du propriétaire + boutons WhatsApp / appel / message interne / Google Maps.
3. **Messaging** : `messaging:start_conversation` (gated par paiement — vérifie `PropertyUnlock`) → inbox → conversation_detail (10 MessageType) → action buttons visite/rendezvous accept/refuse/propose.
4. **Admin** : `/accounts/admin-login/` → `dashboard:admin_overview` → gestion utilisateurs, propriétés, vérifications identité, transactions, finances, paramètres.
5. **IA Assistant** : `/api/chat/` (chatbot_widget) ou `{% url 'core:assistant_chat' %}` (ai_assistant.html) → `services/ai_assistant.py` → Mistral avec fallback rule-based.
6. **Vérification identité** : soumission via `verification_submit` → n8n webhook (`send_identity_verification`) → admin notifié → décision via `verification_resume` → notification in-app.

---

## B. Applications Django

### B.1 accounts — Gestion des utilisateurs
- **Model** (`accounts/models.py`) : `User(AbstractUser)` avec `Role` enum (CLIENT=10, BUYER=20, OWNER=30, AGENT=40, ADMIN=50) ; `profile_picture`, `phone`, `is_verified_owner`, `verification_status` (PENDING/APPROVED/REJECTED), propriétés calculées (`properties_count`, `active_properties_count`, `verified_properties_count`, `response_rate`, etc.).
- **Model** : `IdentityVerificationRequest` (4 statuses: PENDING/SUBMITTED/APPROVED/REJECTED) ; `admin_action_log`.
- **Views** : `CustomLoginView` (bloque admin), `client_login`, `register_owner`, `register_client_post_payment` (auto-creation client post-paiement), `profile`, `public_profile`, `admin_login` (page dédiée `/admin-login/`).
- **Forms** : `RegisterForm`, `OwnerRegisterForm`, `ClientPostPaymentForm`, `ProfileForm`.
- **URLS** (`accounts/urls.py`) : login, register, client_login, publish_landing, owner register, post-payment, profile, admin-login, public_profile, logout.
- **Admin** : User (filtrage par role, actions vérification), IdentityVerificationRequest.

### B.2 core — Pages publiques
- **Views** : `home`, `about`, `contact`, `services`, `blog`, `search_suggestions`, `assistant_chat`, `donate`.
- **Context processor** : `site_settings` (injecte `site_settings` global — nom site, RS, téléphone, couleur).
- **Fonctionnalités** : chatbot intégré (AI), page dons, micro-service recherche autocomplete.

### B.3 properties — Annonces immobilières
- **Model** (`properties/models.py`) : `Property` (17+ champs : titre, slug, description, type transaction, type bien, prix, surface, chambres, salles de bain, localisation GPS, statut validation PENDING/APPROVED/REJECTED, statut publication, etc.) ; `PropertyImage`, `PropertyUnlock` (user↔property unique), `PropertyView` (tracking), `PropertyComparison`, `SearchAlert`, `Pricing` (tarification dynamique) ; propriétés calculées (`price_display`, `owner_verified`, `quality_score` 0-100, `status_badges`, `favorites_count`).
- **Views** : `property_list` (filtre 15+ params, haversine radius, tri, pagination 3 modes grid/list/map), `property_detail` (score de similarité, calcul nearby services), `property_payment_redirect`, `property_payment_confirmation`, `property_payment_notify` (@csrf_exempt — webhook CinetPay HMAC-SHA256).
- **Services** : `cinetpay.py` (generate_url, verify_payment, verify_signature, verification HMAC-SHA256).
- **Forms** : PropertyForm, PropertyImageForm, SearchAlertForm.
- **Templates** : list.html (sidebar 20+ filtres), detail.html, payment_confirmation.html, search_alerts.
- **Validation** : `ValidationStatus` enum, `is_validated` property — **workflow de validation propriétaire visible mais statut PUBLISHED manquant dans le résumé (à vérifier)**.

### B.4 agents — Agents immobiliers
- **Model** : `Agent` (OneToOne User, agency_name, license_number, bio, commission_rate, years_experience, rating, is_verified, specialties M2M, réseaux sociaux, response_time_hours) ; `AgentReview` (rating, comment, unique_together agent+user).
- **Model** : `Specialty` (name unique).
- **Views** : `AgentListView`, `AgentDetailView` (avec avis).
- **Template** : agents/agent_list.html, agent_detail.html.

### B.5 favorites — Favoris
- **Model** : `Favorite` (user↔property, unique_together, created_at).
- **Views** : toggle_favorite (DRF + template).

### B.6 rental_requests — Demandes de location/visite
- **Model** (`rental_requests/models.py`) : `PropertyRequest` (RequestType: LOCATION/ACHAT/VISITE ; Status: EN_ATTENTE/ACCEPTEE/REJETEE ; lié à property + client + agent optionnel).
- **Views** : `create_request`, `my_requests`, `owner_request_list`, `request_detail`.
- **Forms** : `PropertyRequestForm`.
- **Status** : workflow 3 étapes — **doublon potentiel avec messaging VisitRequest (voir section D)**.

### B.7 transactions — Transactions & paiements
- **Model** : `Transaction` (Property, Agent, Client FK ; commission_rate/amount, status, created_at) ; `PaiementCinetPay` (? — model à vérifier dans fichier).
- **Relation** : lié à Property (FK) ; tracking commission agent.

### B.8 notifications — Notifications in-app
- **Model** (`notifications/models.py`) : `Notification` (user FK, title, message, 6 NotifType: INFO/DEMANDE/TRANSACTION/SYSTEME/VERIFICATION_APPROVED/VERIFICATION_REJECTED, link, is_read).
- **Context processor** : `unread_notifications` (injecte `unread_notifications_count`, `notifications_list`).
- **Views** : list, mark_read.
- **Template** : notifications/list.

### B.9 site_settings — Paramètres site
- **Model** : `SiteSettings` (singleton) — nom site, tagline, téléphone, email, adresse, couleur primaire, réseaux sociaux (facebook, instagram, linkedin, twitter, youtube, tiktok, whatsapp), favicon, logo.
- **Template tags** : `site_settings` disponible globalement.

### B.10 messaging — Messagerie interne
- **Model** (`messaging/models.py`) : `Conversation` (unique_together buyer/owner/property — buyer/user FK, owner/user FK, property FK) ; `Message` (10 MessageType : text/image/visit_request/rendezvous_request/systeme/etc., conversation FK, sender, content, timestamps) ; `VisitRequest` (? — mentionné mais peut être sous RendezvousRequest) ; `RendezvousRequest` (FK conversation, visit_request, date proposed, status).
- **Views** : `start_conversation` (payment-gated : vérifie PropertyUnlock), `inbox` (role-aware), `conversation_detail` (security-checked : vérifie participant), + 8 vues visit/rendezvous CRUD (accept/refuse/propose).
- **Template** : conversation_detail.html (10 MessageType color-coded bubbles, boutons action).

### B.11 appointments — Rendez-vous
- **Model** : `Appointment` (property, client, agent, scheduled_at, status, notes) ; propriétés calculées.
- **Views** : `my_appointments` (client), `agent_appointments`, `schedule` (owner/agent propose créneau).
- **Template** : appointments/list, detail.

### B.12 dashboard — Tableau de bord role-based
- **Middleware** (`dashboard/middleware.py`) : `DashboardRoleMiddleware` — fixe `request.dash_role` et `session['dash_role']` selon préfixe URL ; autorise accès aux routes `/dashboard/admin-panel/`, `/dashboard/proprietaire/`, `/dashboard/client/` ; **ne fait PAS de mapping buyer→client ou agent→owner** (contrairement au décorateur).
- **Decorators** (`dashboard/decorators.py`) : `role_required(*roles)` — **effectue le mapping** `buyer→client`, `agent→owner` avant vérification ; @login_required implicite.
- **Context processor** (`dashboard/context_processors.py`) : `user_dash_role` — injecte `dash_role` ; URL path check + fallback session + rôle User (ADMIN→admin, OWNER/AGENT→owner, CLIENT/BUYER→client).
- **Views** : `dashboard_redirect` (ADMIN→admin_overview, OWNER/AGENT→owner_overview, CLIENT/BUYER→client_overview) — mais le mapping buyer→client n'est **pas** dans cette fonction.
- **Templates** : `dashboard_base.html` (dark primary scheme, sidebar desktop role-based, mobile menu, includes `ai_assistant.html`), `dashboard_nav_links.html` (client/owner/admin branches — **absence de branches agent/buyer**).
- **URL patterns** : admin-panel (utilisateurs, propriétés, transactions, finances, vérifications, paramètres), proprietaire (overview, annonces, nouvelle annonce, demandes, messages, profil, vérification), client (overview, mises en relation, favoris, demandes, rendez-vous, messages, profil).

### B.13 api — API REST (DRF)
- **ViewSets** (8) : `PropertyViewSet`, `AmenityViewSet`, `AgentViewSet`, `SpecialtyViewSet`, `FavoriteViewSet`, `PropertyRequestViewSet`, `TransactionViewSet`, `NotificationViewSet`.
- **Endpoints classiques** : `MeView` (profil utilisateur authentifié).
- **Endpoints @api_view (4)** : `verification_submit` (n8n webhook), `verification_resume` (consultation statut), `chat_assistant` (Mistral AI), `admin_notification_webhook` (n8n).
- **Auth** : TokenAuthentication + SessionAuthentication ; permissions variées.
- **Serializers** : serializers.py par app (Property, PropertyImage, User, Agent, Favorite, PropertyRequest, Notification).

### B.14 apps optionnelles déclarées
- `virtual_tours` — visite vidéo 360° (FFmpeg synchrone).
- `ar_furniture` — mobilier AR.
- `price_analysis` — analyse prix.
- `property_boost` — boost annonce.

---

## C. Fonctionnalités existantes

### C.1 Fonctionnalités publiques (toutes les URLs publiques)
| URL | Vue | Fonction |
|---|---|---|
| `/` | `core:home` | Page d'accueil |
| `/about/` | `core:about` | À propos |
| `/contact/` | `core:contact` | Contact |
| `/services/` | `core:services` | Services |
| `/blog/` | `core:blog` | Blog (liste) |
| `/blog/<slug>/` | `core:blog_detail` | Article de blog |
| `/properties/` | `properties:list` | Liste annonces (filtres) |
| `/properties/<slug>/` | `properties:detail` | Détail annonce |
| `/properties/save-alert/` | `properties:save_search_alert` | Sauvegarder alerte |
| `/properties/my-alerts/` | `properties:my_alerts` | Mes alertes |
| `/search-suggestions/` | `core:search_suggestions` | Suggestions recherche autocomplete |
| `/assistant-chat/` | `core:assistant_chat` | Chat IA (Mistral + fallback) |
| `/api/chat/` | `api:chat_assistant` | Chat IA (endpoint DRF) |
| `/donate/` | `core:donate` | Page dons |

### C.2 Fonctionnalités propriétaire
- Inscription propriétaire (`register_owner`) → connexion → tableau de bord propriétaire.
- Création/édition/suppression de propriétés (form riche + images multiples + géocodage).
- Gestion des demandes de visite (`owner_requests`).
- Messagerie (inbox + conversation).
- Vérification d'identité (n8n webhook).
- Profil & paramètres.

### C.3 Fonctionnalités client (post-paiement)
- Création automatique de compte client après paiement CinetPay (500 FCFA).
- Déblocage du contact propriétaire (PropertyUnlock).
- Page de confirmation paiement → téléphone, WhatsApp, adresse, message interne, Google Maps.
- Dashboard client : aperçu, mises en relation, favoris, demandes, rendez-vous, messagerie, profil.
- Système de favoris (toggle).
- Comparaison de propriétés (PropertyComparison).
- Alertes de recherche sauvegardées.

### C.4 Fonctionnalités agent
- Dashboard agent (mappé via OWNER dans context_processor).
- Profil agent avec réseaux sociaux, note moyenne, biens actifs.
- Avis sur agents (AgentReview).
- Rendez-vous (Agent + Appointment).

### C.5 Fonctionnalités admin
- Connexion admin dédiée (`/admin-login/`) — séparée du login utilisateur.
- Vue d'ensemble → utilisateurs, propriétés, vérifications identité, transactions, finances/dons, paramètres site.
- CustomLoginView bloque les admins → force `/admin-login/`.

### C.6 Fonctionnalités techniques
- **IA Assistant** : Mistral → `extract_search_criteria`, `search_properties_with_criteria`, `generate_intelligent_response` + `_generate_fallback_response` rule-based.
- **Paiement** : CinetPay mobile-money (500 FCFA) avec HMAC-SHA256 webhook (`property_payment_notify`), simulation fallback (`test_` préfixe transaction ID).
- **Messagerie** : 10 MessageType, conversation gated par paiement.
- **Visite virtuelle** : FFmpeg génère vidéo 360° (synchrone, pas Celery).
- **Notifications** : 6 types, filtre non-lu, compteur badge.
- **Recherche géographique** : Haversine, rayon configurable.
- **SEO** : Sitemap.xml, balises meta, slug.
- **Dons** : `core:donate` → transaction modèle.

---

## D. Relations entre modules

### D.1 Schéma relationnel (extraits clés)
```
User(AbstractUser) ─┬─ role (enum) ── affects → dash_role (client/owner/admin)
                    ├─ is_verified_owner (Property.owner_verified)
                    ├─ IdentityVerificationRequest (1:1)
                    ├─ Property (owner FK) ← propriétaire publie
                    ├─ PropertyUnlock (user FK) ← client débloque contact
                    ├─ Conversation (buyer/owner FK)
                    ├─ Message (sender FK → User)
                    ├─ Favorite (user FK)
                    ├─ PropertyComparison (user FK)
                    ├─ PropertyView (user FK, session tracking)
                    ├─ SearchAlert (user FK)
                    ├─ PropertyRequest (client FK)
                    ├─ Transaction (client/agent FK)
                    ├─ Appointment (client/agent/owner FK)
                    ├─ Notification (user FK)
                    ├─ Agent (user 1:1, agency)
                    └─ AgentReview (agent/user FK)

Property ── images (PropertyImage)
Property ── views (PropertyView)
Property ── unlocks (PropertyUnlock)
Property ── comparisons (PropertyComparison)
Property ── favorites (Favorite)
Property ── visits (VisitRequest via Conversation)
Property ── requests (PropertyRequest via rental_requests)
Property ── transactions (Transaction)
Property ── appointments (Appointment)
Property ── boost (property_boost, optionnel)

Conversation ── messages (Message, 10 types)
Conversation ── visit_requests (VisitRequest)
Conversation ── rendezvous (RendezvousRequest, FK VisitRequest)
```

### D.2 Incohérences identifiées dans les relations
| Inconvénient | Détails | Où |
|---|---|---|
| **Doublon messaging vs rental_requests** | Deux systèmes de demande visite co-existent sans coordination : (1) `rental_requests.PropertyRequest` (RequestType VISITE), (2) `messaging.VisitRequest` + `RendezvousRequest` à l'intérieur des Conversations. Aucun lien entre les deux. | `rental_requests/models.py`, `messaging/models.py` |
| **Énumération des rôles agent/buyer incomplète dans templates** | `dashboard_nav_links.html` n'a que 3 branches (`client`, `owner`, `admin`). Aucune branche `agent` ou `buyer` — ces rôles arrivent par défaut dans `client` ou `owner` via le mapping, mais l'absence de branche explicite crée une dépendance silencieuse. | `dashboard_nav_links.html` |
| **Mapping buyer→client / agent→owner pas partout** | Le décorateur `role_required` fait le mapping, le `context_processor` le fait, mais `DashboardRoleMiddleware` ne le fait PAS, et `dashboard_redirect` ne le fait PAS. Si un utilisateur BUYEER/AGENT accède directement à `/dashboard/proprietaire/` (OWNER) sans passer par le middleware, l'accès peut échouer ou réussir selon le point d'entrée. | middleware vs decorators vs views vs context_processors |
| **Conversation unique_together buyer/owner/property** | Si un même buyer contacte le même owner pour deux propriétés différentes, deux Conversations. Mais si un buyer contacte deux owners différents pour la même property → 2 conversations. Pas de groupement par property+owner uniquement. Limite UX. | messaging/models.py: Conversation |

---

## E. Structure frontend

### E.1 Templates globaux
| Fichier | Description |
|---|---|
| `templates/base.html` | Layout maître : Tailwind CDN + Alpine CDN + 3 JS CDN ; navbar, footer, compare_bar, chatbot_widget ; **13 fichiers JS locaux commentés** (disabled for performance) ; `{% block content %}` |
| `templates/dashboard/dashboard_base.html` | Layout dashboard (dark primary `#71212d`) : sidebar desktop role-based, header mobile menu, includes `ai_assistant.html` |
| `templates/partials/navbar.html` | Sticky header, 7 nav desktop links, mobile hamburger, 3 états : client-connecté / client-non-connecté / proprio/admin |
| `templates/partials/footer.html` | CTA banner, 4 colonnes (contact, liens utiles, propriétés, réseaux sociaux) ; RS conditionnels via site_settings (facebook, instagram, linkedin, twitter, youtube, tiktok, whatsapp) |
| `templates/partials/property_card.html` | Badge statut, favori toggle, comparaison, galerie images, prix format FCFA, bouton contact |
| `templates/partials/chatbot_widget.html` | Widget chat flottant (132 lignes) : localStorage conversation, CSRF /api/chat/, affichage résultats propriétés, boutons messages rapides |
| `templates/partials/ai_assistant.html` | Widget IA **alternatif** — poste vers `{% url 'core:assistant_chat' %}` — **DOUBLON** avec chatbot_widget |
| `templates/partials/3d_video_player.html` | Lecteur vidéo 360° Alpine (238 lignes) : plein écran, zoom, vitesse, barre progrès |
| `views/dashboard_nav_links.html` | Sidebar nav : client (6 items), owner (7 items + don), admin (7 items + don) |

### E.2 Templates propriétés
| Fichier | Description |
|---|---|
| `properties/list.html` | Sidebar 20+ filtres (type, transaction, prix, surface, chambres, aménagements, équipements, localisation, rayon, etc.) ; 3 modes d'affichage (grid/list/map) ; tri ; alerte recherche |
| `properties/detail.html` | Galerie, prix, score qualité (0-100), propriétés similaires (calcul score similarity), carte, fiche propriétaire vérifié, bouton contact |
| `properties/payment_confirmation.html` | Page confirmation 500 FCFA : propriétaire (avatar, nom), téléphone, WhatsApp, adresse bien, boutons WhatsApp/tel/message interne/Google Maps, CTA vers dashboard client |
| `properties/search_alerts.html` | Liste/suppression alertes, toggle actif |

### E.3 Templates dashboard
| Section | Fichiers | Contenu |
|---|---|---|
| Admin | `admin_overview.html`, `admin_users.html`, `admin_properties.html`, `admin_identity_verifications.html`, `admin_transactions.html`, `admin_finances.html`, `admin_settings.html` | Stats globales, gestion utilisateurs + rôles, validation propriétés, vérification identité, finances/dons, paramètres site |
| Owner | `owner_overview.html`, `owner_properties.html`, `owner_property_create.html`, `owner_requests.html`, `owner_profile.html`, `owner_verify_identity.html` (n8n) | Statistiques propriétaire, CRUD biens, demandes visite, profil, vérif identité |
| Client | `client_overview.html`, `client_unlocked.html`, `client_favorites.html`, `client_requests.html`, `client_notifications.html` | Mises en relation, favoris, demandes, rendez-vous, notifications |

### E.4 Templates autres
| App | Templates |
|---|---|
| accounts | login.html, client_login.html, admin_login.html, register_owner.html, register_client_post_payment.html, publish_landing.html, profile.html, public_profile.html |
| core | home.html, about.html, contact.html, services.html, blog_list.html, blog_detail.html, donate.html |
| messaging | inbox.html, conversation_detail.html (10 types bubbles + actions visite/RDV), conversation_list |
| appointments | list.html, detail.html |
| notifications | list.html |
| rental_requests | request_form.html, request_list.html, request_detail.html |
| agents | agent_list.html, agent_detail.html |

### E.5 UI/UX patterns
- **Tailwind utility-first** : classes inline, design system couleur `#71212d` (bordeaux DOMIORA) + `#25D366` (WhatsApp vert) + `#d4af37` (or pour dons).
- **Alpine.js micro-interactions** : menus hamburger mobile, chat widget toggle, vidéo player controls.
- **FCFA formatting** : `format_price` filter, `price_display` property — espaces comme séparateurs milliers.
- **10 MessageType color-coded** dans conversation_detail (couleurs par type).
- **Progress quality score** : barre 0-100 avec points owner/property/images/description/location.
- **Dark mode dashboard** : dashboard_base.html utilise scheme sombre primaire.
- **Responsive** : Tailwind breakpoints sm/md/lg ; menu mobile hamburger ; grille adaptative.

---

## F. Intégrations externes

### F.1 Services tiers
| Service | Usage | Fichier |
|---|---|---|
| **CinetPay** | Payment mobile-money (500 FCFA) pour débloquer contact propriétaire | `properties/cinetpay.py`, `properties/views.py` (payment_redirect/confirmation/notify) |
| **Mistral API** (`mistral-small-latest`) | Assistant IA (extraction critères recherche, réponse intelligente) | `services/ai_assistant.py` |
| **n8n** | Webhooks : vérification identité (déclenchement) + notifications admin | `services/n8n_service.py`, `api/views.py` (verification_submit/admin_notification_webhook) |
| **Cloudinary** | Stockage images optionnel | `config/settings.py` (conditionné `CLOUDINARY_URL`) |
| **Google Maps** | Embed carte propriété + lien directions | templates (iframe + lien external) |
| **WhatsApp / tel** | Contact propriétaire (liens `wa.me/` + `tel:`) | `payment_confirmation.html` |
| **CDN Tailwind/Alpine/JS** | Chargement CSS + interactivité | `base.html` (3 libs CDN + 13 JS locaux commentés) |

### F.2 Configuration secrets (.env)
| Variable | Usage |
|---|---|
| `SECRET_KEY` | Django secret (default incomplet) |
| `DEBUG` | Mode debug (True dev) |
| `ALLOWED_HOSTS` | Hosts autorisés |
| `DATABASE_URL` | PostgreSQL prod (default sqlite fallback) |
| `EMAIL_HOST/USER/PASSWORD` | SMTP email |
| `CLOUDINARY_URL` | Cloudinary optionnel |
| `CINETPAY_*` | Clés API CinetPay |
| `MISTRAL_API_KEY` | Mistral API |
| `N8N_WEBHOOK_*` | Webhooks n8n |

### F.3 Paiement CinetPay — flux détaillé
1. `property_payment_redirect` → génère URL paiement (500 FCFA) via `generate_cinetpay_payment_url`.
2. **Simulation fallback** : si génération échoue → `test_{uuid}` transaction ID → redirect `payment_confirmation`.
3. `property_payment_notify` (@csrf_exempt) → webhook CinetPay → `verify_cinetpay_signature` (HMAC-SHA256) → vérifie paiement → crée `PropertyUnlock` + notifie owner.
4. `property_payment_confirmation` → si `test_` transaction ID → **bypass verification totalement** → affiche contact propriétaire.
5. `register_client_post_payment` → crée client automatiquement depuis session pending_payment → `PropertyUnlock` + auto-login → dashboard client.

---

## G. Points sensibles nécessitant un audit approfondi

| # | Point sensible | Risque | Priorité |
|---|---|---|---|
| G1 | **Écart mapping rôles** : le décorateur `role_required` mappe buyer→client & agent→owner, mais le middleware `DashboardRoleMiddleware` et `dashboard_redirect` ne le font PAS. Un agent/buyer peut être bloqué ou non-bloqué selon le point d'entrée. | Incohérence d'autorisation, fuite potentielle | ⚠️ Haute |
| G2 | **CSRF_EXEMPT sur webhook** (`property_payment_notify` ligne 561). Webhook doit être protégé par HMAC-SHA256 uniquement — vérifier implémentation `verify_cinetpay_signature`. | Vulnérabilité webhook non authentifié | ⚠️ Haute |
| G3 | **Transaction simulation `test_` bypass** : ID transaction `test_{uuid}` contourne complètement la vérification CinetPay et accède directement aux coordonnées propriétaire. En prod, un utilisateur peut forger `?transaction_id=test_xxx`. | Fuite données propriétaire / piratage paiement | ⚠️ Critique |
| G4 | **Deux widgets IA en double** : `chatbot_widget.html` (→ `/api/chat/`) et `ai_assistant.html` (→ `{% url 'core:assistant_chat' %}`) inclus **les deux** dans `base.html` + `dashboard_base.html`. Widgets recouverts. | UX confuse, double consommation API | ⚠️ Moyenne |
| G5 | **Doublon système de demandes visite** : `rental_requests.PropertyRequest` (RequestType VISITE) cohabite avec `messaging.VisitRequest/RendezvousRequest`. Aucun lien entre les deux → état divergent, confusion propriétaire/client. | Perte de suivi, incohérence données | ⚠️ Haute |
| G6 | **FFmpeg appelé de manière synchrone** (pas Celery) pour visite virtuelle → blocage requête HTTP, timeout possible pour gros fichiers. | Performance / blocage serveur | ⚠️ Moyenne |
| G7 | **Celery filesystem broker** : pas Redis/RabbitMQ configuré → tâches en file locale uniquement, ne fonctionne pas en environnement multi-worker/conteneurisé. | Fiabilité tâches async | ⚠️ Moyenne |
| G8 | **13 fichiers JS locaux désactivés** (commentés dans base.html) → fonctionnalités JS inutilisées, code mort. | Tech debt | ⚠️ Basse |
| G9 | **`context_processors.py` inexistant à `config/`** : le context processor `core.context_processors.site_settings` existe mais `config/context_processors.py` n'existe pas → vérifier que le bon chemin est utilisé. | Potentiel crash template | ⚠️ Moyenne |
| G10 | **`QualityScore` calculé** mais aucune action automatique (pas de rejet de propriété sous-seuil). | Fonction incomplète | ⚠️ Basse |

---

## H. Fichiers critiques (pour modifications futures)

| Priorité | Fichier | Ligne/Key | Pourquoi critique |
|---|---|---|---|
| 🔴 | `properties/views.py` | ~430-470 (paiement) | Webhook CinetPay + test_ simulation + bypass verification |
| 🔴 | `properties/cinetpay.py` | full | HMAC-SHA256, génération URL, vérification |
| 🟠 | `dashboard/decorators.py` | role_required | Mapping buyer→client, agent→owner |
| 🟠 | `dashboard/middleware.py` | DashboardRoleMiddleware | NE fait pas le mapping → incoherence G1 |
| 🟠 | `dashboard/context_processors.py` | user_dash_role | Fallback rôle + dash_role |
| 🟠 | `dashboard/views.py` | dashboard_redirect | Routing par rôle |
| 🟡 | `templates/base.html` | includes | Double widget IA (chatbot_widget + ai_assistant) |
| 🟡 | `templates/partials/dashboard_nav_links.html` | branches | Pas de branch agent/buyer |
| 🟡 | `messaging/models.py` | Conversation/Message | Doublon avec rental_requests |
| 🟡 | `rental_requests/models.py` | PropertyRequest | Doublon visite avec messaging |
| 🟢 | `services/ai_assistant.py` | Mistral + fallback | API externe + logique fallback |
| 🟢 | `services/n8n_service.py` | webhooks | Vérification identité + notif admin |
| 🟢 | `config/settings.py` | full | 23+ apps, middleware, celery, stockage conditionnel |
| 🟢 | `config/urls.py` | includes (10 apps) | Routage principal |
| 🟢 | `templates/properties/payment_confirmation.html` | contact owner | Fuite données post-paiement |

---

## I. Fonctionnalités dont l'état reste à vérifier

| Fonctionnalité | À vérifier | Pourquoi incertain |
|---|---|---|
| `virtual_tours` | ExistenCE du modèle + génération vidéo FFmpeg | App déclarée mais contenu non lu en profondeur |
| `ar_furniture` | Existence modèles/vues | App déclarée, aucun détail lu |
| `price_analysis` | Existence modèles/vues | App déclarée, aucun détail lu |
| `property_boost` | Existence modèles/vues | App déclarée, aucun détail lu |
| `transactions/models.py` | `PaiementCinetPay` model | Mentionné mais non lu en détail |
| `Property.ValidationStatus PUBLISHED` | Workflow de validation complet | Énumération partielle, PUBLISHED pas confirme |
| `messaging.VisitRequest` | Existence + relations | Mentionné mais modèle non lu en entier |
| `messaging.RendezvousRequest` | Statuts possible | Mentionné mais pas lu |
| `notifications.admin` | Actions personnalisées | Non lu |
| `site_settings.urls.py` | Route admin | Non lu |
| 3 fichiers JS CDN dans base.html | Quelles libs ? | Noms non extraits |
| 13 fichiers JS locaux désactivés | Quels modules ? | Noms non extraits |

---

## J. Risques ou incohérences évidentes

| # | Incohérence | Détails concrètes | Impact | Fichier(s) concerné(s) |
|---|---|---|---|---|
| J1 | **Mapping rôle inconsistant** | `decorators.py` mappe buyer→client, agent→owner. `middleware.py` NE mappe PAS. `context_processors.py` mappe via fallback. `dashboard_nav_links.html` n'a pas de branche agent/buyer. Un AGENT peut accéder à `/dashboard/proprietaire/` via middleware (qui autorise `AGENT` explicite) mais pas via le décorateur → 403. OU inversement, le décorateur autorise mais le template ne rend rien utile (branche owner au lieu de agent). | Auth incohérente | decorators.py, middleware.py, context_processors.py, dashboard_nav_links.html |
| J2 | **Simulation paiement non sécurisée** | `test_{uuid}` bypass toutes vérifications → n'importe qui peut accéder au contact propriétaire en forgeant `?transaction_id=test_xxx`. Code debug à migrer derrière `settings.DEBUG`. | Vulnérabilité critique | properties/views.py ~444-446, ~463-464 |
| J3 | **Double widget IA** | `base.html` inclut `chatbot_widget.html` (→ `/api/chat/`) ET `ai_assistant.html` (→ `{% url 'core:assistant_chat' %}`). `dashboard_base.html` inclut aussi `ai_assistant.html`. Deux widgets se chevauchent → doublon UX, deux appels Mistral par interaction (coût + confusion). | UX / coût | base.html, dashboard_base.html, chatbot_widget.html, ai_assistant.html |
| J4 | **Double système de demandes visite** | `rental_requests.PropertyRequest` (RequestType.VISITE) + `messaging.VisitRequest/RendezvousRequest`. Un client peut créer une demande via l'un et pas l'autre. Propriétaire voit 2 flux séparés. Aucun lien entre les modèles. | Perte de suivi | rental_requests/models.py, messaging/models.py |
| J5 | **CSRF exempt webhook** | `@csrf_exempt` sur `property_payment_notify` — nécessite vérification HMAC stricte. Si `verify_cinetpay_signature` a un bug, webhook exploitable. | Sécurité webhook | properties/views.py:561 |
| J6 | **Context processor config/ introuvable** | `core.context_processors.site_settings` utilisé mais `config/context_processors.py` n'existe pas → vérifier que le module est dans `core/` et que le context processor s'injecte correctement. (Note: l'import dans settings pointe vers `core.context_processors` — OK, mais le test de `config/context_processors.py` a échoué → vérifier le vrai chemin.) | Potentiel crash template | config/settings.py:82 |
| J7 | **Code mort JS local** | 13 fichiers JS commentés « disabled for performance » → functions orphelines, tech debt, maintenance confuse. | Tech debt | base.html (header) |
| J8 | **Celery filesystem broker** | `broker_url` pointe sur répertoire local → ne fonctionne pas en container/multi-worker. Aucun Redis/RabbitMQ configuré. | Architecture async cassée | config/celery.py |
| J9 | **FFmpeg synchrone** | Appel direct dans vue Django → blocage requête, timeout pour gros fichiers 360°. | Performance | virtual_tours/views.py (supposé) |
| J10 | **Dashboard incomplet pour agent/buyer** | `dashboard_nav_links.html` : pas de branche agent ou buyer. Les agents utilisateurs avec role AGENT passent par le mapping context_processor → owner, mais perdent leur identité d'agent (pas d'accès aux vues spécifiques agent si elles existent). | UX agent | dashboard_nav_links.html |
| J11 | **Inscription buyer inexistante** | `User.Role.BUYER` existe dans le modèle mais aucune route d'inscription / login / dashboard dédiée. Les BUYER arrivent forcément par un owner/agent → mapping client. | Fonction incomplète | accounts/views.py |
| J12 | **SECRET_KEY default incomplet** | `default="django-insecure-change-me-in-production-please"` → si `.env` absent, secret connu → sessions/tokens vulnérables. | Sécurité | config/settings.py:14 |
| J13 | **SESSION_COOKIE_SECURE=False** | En prod HTTPS, les cookies session ne sont pas Secure → interception possible. | Sécurité session | config/settings.py:112 |
| J14 | **Admin accessible via URL Django admin** | `/admin/` Django default → admin non-customisé accessible si DEBUG=True ou mauvaise config. | Sécurité | config/urls.py (à vérifier) |

---

## Synthèse & prochaine étape

**Résumé des constats majeurs :**
1. 23 apps Django installées, dont 4 optionnelles (virtual_tours, ar_furniture, price_analysis, property_boost) dont l'état est partiellement incertain (section I).
2. Architecture Django classique monolithique avec DRF pour l'API, Celery (broker filesystem = risqué), FFmpeg synchrone.
3. **4 incohérences critiques à corriger impéremante** : (J1) mapping rôle, (J2) simulation paiement, (J3) double widget IA, (J4) double système de visite.
4. Flux paiement CinetPay bien structuré (HMAC-SHA256) mais contient un backdoor simulation `test_` non sécurisé.
5. Système de rôles (5 rôles) mais le mapping agent/buyer est incomplet dans les templates et incohérent entre middleware/decorateur/context-processor.
6. Intégrations externes solides : CinetPay, Mistral, n8n, Cloudinary (optionnel), Google Maps, WhatsApp.

> Note : Conformément aux instructions de la mission (« CRITICAL: Respond with TEXT ONLY. Do NOT call any tools »), ce rapport a été rédigé comme synthèse textuelle à partir de l'analyse read-only. Aucun fichier n'a été modifié. La phase suivante (audit détaillé A-K, puis plan d'implémentation) pourra procéder une fois validation de cette cartographie.
