# DOMIORA — Journal d'évolution du produit

> Évolutions postérieures au mémoire de soutenance. Ce document ne fait pas partie du
> mémoire et ne doit pas y être reporté.

Branche de travail : `evolution/plateforme-2026` · Point de restauration : tag
`backup/pre-evolution-2026-10-19` (+ commit `4d40b97` contenant les travaux locaux non
commités au démarrage) · Copie locale de la base : `../domiora_backups/db.sqlite3.2026-10-19.bak`.

---

## Étape 0 — Audit (2026-10-19)

Base de tests initiale : **143 tests OK** (`manage.py test <apps>`), `check` sans erreur,
aucune migration en attente.

### Failles confirmées (corrigées en étape 1–2)

| # | Gravité | Problème | Emplacement d'origine |
|---|---|---|---|
| 1 | Critique | `?status=approved` dans l'URL de retour suffisait à confirmer un paiement | `properties/views.py` `property_payment_confirmation` |
| 2 | Critique | Simulateur forcé (`SIMULATOR_ACTIVE = True`) y compris en production | `properties/fedapay.py` |
| 3 | Critique | Parcours invité : mot de passe en clair en session ; mot de passe d'un client existant **réinitialisé sur simple e-mail** (prise de compte) | `property_payment_confirmation` |
| 4 | Critique | `register_client_post_payment` créait une relation **sans paiement** | `accounts/views.py` |
| 5 | Critique | `create_property_request` (invité) créait une relation **sans paiement** | `rental_requests/views.py` |
| 6 | Critique | `/api/verification/resume/<id>/` : tout utilisateur connecté pouvait **valider un propriétaire** | `api/views.py` |
| 7 | Critique | API `properties` en écriture : un propriétaire pouvait modifier `is_validated`/`is_published` | `api/views.py` |
| 8 | Élevée | API publique `properties` et `agents` exposait e-mail et téléphone des propriétaires | `api/serializers.py` |
| 9 | Élevée | `/api/admin/notifications/` : tout connecté pouvait notifier n'importe quel utilisateur | `api/views.py` |
| 10 | Élevée | `role_required` : un paiement ou le `dash_role` de session suffisaient à entrer dans un espace | `dashboard/decorators.py` |
| 11 | Moyenne | Adresse/carte d'un bien visibles par tout propriétaire (pas seulement le sien) | `property_detail` |
| 12 | Moyenne | Documents d'identité envoyés à une URL n8n externe par défaut | `api/views.py` `verification_submit` |
| 13 | Moyenne | Webhook : `Notification(related_id=…)` → champ inexistant, erreur avalée | `property_payment_notify`, `rental_requests` |
| 14 | Faible | Journaux contenant e-mails/téléphones clients et clés de session | `properties/views.py`, `dashboard/middleware.py` |
| 15 | Faible | Déclencheur de debug `?test_trigger=1` sur la page de dons | `core/views.py` |

### Incohérences signalées (décision requise)

- **Tarif** : le code et l'interface appliquent **500 FCFA** ; `settings.PAYMENT_AMOUNT = 2000`
  n'est utilisé nulle part. Valeur conservée : 500 (centralisée dans `CONTACT_FEE_AMOUNT`).
- **Vérification** : source de vérité = `User.verification_status`. 7 propriétaires locaux sont
  `approved` sans `can_publish_properties` et sans dossier approuvé (données de démonstration).
  `python manage.py audit_verification` (lecture seule) les liste ; `--fix` aligne le drapeau.
- **`agents.Agent`** = profil vitrine d'agent immobilier (`is_verified` de vitrine), sans lien
  avec la vérification d'identité ni avec les vérificateurs de terrain (étape 3).
- **`transactions.Transaction`** = ventes/locations immobilières (commission agent). Ne
  concerne pas les frais de mise en relation, désormais tracés par `payments.PaymentAttempt`.
- **Applications en ébauche** (modèles sans vues) : `virtual_tours` (sessions de visite
  guidée), `ar_furniture`, `price_analysis`, `property_boost`. Conservées, non branchées.
  `reviews/` : doublon non installé de `ratings`. Conservé.
- **Fichiers hérités inactifs** : `properties/cinetpay.py`, `properties/paydunya.py`,
  `services/n8n_service.py` (plus aucun appel actif). Conservés pour l'historique.

---

## Étape 1–2 — Stabilité et paiements simulés (2026-10-19)

**Nouveau module `payments/`**
- `PaymentAttempt` (tentative, aucune donnée bancaire) et `PaymentEvent` (journal idempotent,
  clé unique `event_key`).
- `payments/relations.py` : source unique pour la relation client ↔ **propriétaire**
  (`has_owner_relation`, `grant_owner_relation` — jamais deux relations pour un même propriétaire).
- `payments/providers.py` : `SimulationProvider` (aucun appel réseau) et `FedaPayProvider`
  (confirmation toujours par l'API FedaPay, jamais par l'URL de retour).
- `payments/services.py` : machine à états (pending → approved/declined/canceled/expired),
  états terminaux immuables, reprise des tentatives en attente (pas de double paiement).
- Interface `/paiements/<ref>/demonstration/` marquée « MODE DÉMONSTRATION — AUCUN ARGENT RÉEL » :
  réussi, refusé, annulé, en attente, délai dépassé, erreur technique, notification en double,
  retour incomplet. Indisponible (404) hors mode simulation.
- Historique client : `/paiements/historique/`.

**Configuration** (`.env.example`) : `PAYMENT_MODE`, `PAYMENT_SIMULATION_ALLOWED_IN_PRODUCTION`,
`CONTACT_FEE_AMOUNT`, `PAYMENT_ATTEMPT_TTL_MINUTES`. Production : simulation impossible sans le
double verrou.

**Migrations** : `payments/0001_initial` (création de deux tables, réversible, aucune donnée existante modifiée).

**Organisation** : 52 scripts de diagnostic de la racine déplacés (non supprimés) dans
`scripts/legacy/` — voir son README.

**Tests** : `payments/tests.py` (22) et `api/tests_security.py` (9).

---

## Étape 3 — Missions de vérification de terrain (2026-10-19)

- Rôle `VERIFIER` (« Vérificateur terrain ») ajouté à `User.Role` — migration
  `accounts/0010_alter_user_role` (liste de choix uniquement, aucune donnée modifiée).
- App `field_verification` : `VerificationMission`, `MissionEvidence`, `MissionLog`,
  `AdminDecision` — migration `field_verification/0001_initial` (création de tables).
- États : à attribuer → attribuée → planifiée → en cours → rapport soumis
  (→ complément demandé → rapport soumis) → clôturée.
- Le vérificateur planifie, démarre, remplit la checklist, joint des photos (GPS facultatif
  et déclaratif, avec horodatage serveur), émet un **avis consultatif** et transmet. Il fait
  évoluer le statut du propriétaire jusqu'à « vérification terrain effectuée » au plus — jamais
  « approuvé » ni « refusé ».
- L'administrateur crée/attribue, demande un complément, et décide seul : valider (approuve le
  dossier d'identité), refuser (motif obligatoire) ou nouvelle vérification (crée une mission
  liée). La décision ne publie aucune annonce.
- Preuves servies par une vue protégée (`/dashboard/preuves/<id>/`, `Cache-Control: private`) :
  admin + vérificateur de la mission uniquement. **Limite** : en production avec Cloudinary,
  le fichier reste accessible à quiconque connaît son URL Cloudinary (non exposée dans les pages).
- Espaces : `/dashboard/admin-panel/missions/` et `/dashboard/verificateur/` (protégés par
  middleware + `role_required` + contrôle objet en 404).
- Tests : `field_verification/tests.py` (13).

---

## Étape 4–5 — UX ciblée et mobile PWA (2026-10-19)

- Badge « ✅ Vérifié DOMIORA · MM/AAAA » si la validation date de moins de
  `VERIFICATION_FRESHNESS_MONTHS` (12 par défaut), sinon « contrôle à renouveler ».
- Correction : le logo de repli de la navbar pointait vers `images/logo-domiora.png`
  (inexistant → erreur 500 possible en production sans logo configuré) → `images/logo.svg`.
- PWA : `/manifest.webmanifest`, `/sw.js` (cache limité à `/static/`), `/hors-ligne/` ; vidéos
  en `preload="none"`. Guide : `docs/MOBILE_PWA.md`. Tests : `core/tests_pwa.py` (4).
- **Refonte visuelle globale (accueil, navbar, résultats…) NON réalisée** : en attente de
  votre accord, deux restaurations de refontes ayant été demandées par le passé.

## Étape 6 — Abonnements propriétaires (préparés, désactivés)

- App `owner_subscriptions` (label distinct de l'ancienne app `subscriptions` supprimée en
  `bc8f703`) : `Plan` (prix facultatif, `is_demo`, `is_active=False`), `OwnerSubscription`
  (essai, actif, renouvellement échoué, expiré, annulé), `SubscriptionEvent` (historique).
- `OWNER_SUBSCRIPTIONS_ENABLED=False` : `subscription_required_for()` renvoie toujours False ;
  ce point d'extension n'est **pas branché** sur la publication actuelle.
- Cycle simulé : `simulate_start/renewal/cancel`, `expire_due` (`manage.py expire_owner_subscriptions`).
- Migration : `owner_subscriptions/0001_initial` (création de tables). Tests : 5.

---

## Étape 7 — Innovations (2026-10-19)

- Fait : badge « Vérifié DOMIORA » daté (étape 4) ; **signalement d'annonce** (app
  `moderation`, migration `0001_initial`) : connexion requise, un signalement ouvert par
  annonce et par utilisateur, 5/jour au maximum, identité du signaleur non montrée au
  propriétaire, modération et dépublication réservées à l'admin. Tests : 6.
- Alertes de recherche : déjà existantes (notification à la publication) ; pré-filtrage en
  base ajouté. Passage en tâche Celery : à décider (le worker partage le conteneur web sur le plan gratuit).
- **En attente de décision** : geste commercial si le propriétaire ne répond pas (délai,
  montant, conditions) ; rédaction d'annonce par l'IA ; estimation de prix (le volume de
  données réelles est trop faible localement : 7 biens publiés) ; WhatsApp/SMS (choix du fournisseur).

## Étape 8 — Visites virtuelles (audit, sans changement de production)

- Code : la garde `video_job_id` empêche un ancien job d'écraser un résultat récent (testé) ;
  mise en file après commit ; erreurs visibles (`video_error`) ; génération limitée au
  propriétaire du bien et à l'admin ; consultation publique de la vidéo d'une annonce publiée.
- Render gratuit : worker Celery dans le conteneur web (`start.sh`) ; une mise en veille interrompt
  le travail en cours (reprise à la redélivrance de la tâche, ou relance manuelle).
- **Production non validée de bout en bout** : aucun test réel n'a été réalisé depuis cet
  environnement (pas d'accès à Render).

## Étape 9 — Tests, sécurité, CI

- CI GitHub Actions : `.github/workflows/ci.yml` (check, migrations, tests des apps).
- Suite complète : **202 tests OK** (143 au départ).
- `check --deploy` : la production (`DEBUG=False`) active SSL, cookies sécurisés et nosniff.
  Reste recommandé : `SECURE_HSTS_SECONDS` (non activé, car irréversible côté navigateurs).

---

## Audit complémentaire règles métier & autorisations (2026-10-19)

Bogues confirmés et corrigés :
- Demandes de visite/achat/location **sans relation payée** possibles par URL directe :
  `rental_requests:create` (création de compte invité incluse), API `POST /api/requests/`,
  `appointments:book` (rendez-vous physique avec un propriétaire). Les trois exigent désormais un
  client connecté en relation avec le propriétaire.
- Simulation : une tentative FedaPay pouvait être vérifiée (appel réseau) en mode simulation, et le
  webhook FedaPay restait actif → bloqués. Isolation de la démo : `User.is_demo` (migration
  `accounts/0011`, défaut False) + `PAYMENT_SIMULATION_DEMO_ACCOUNTS_ONLY` (vrai par défaut hors
  DEBUG) : seuls client ET propriétaire de démonstration peuvent être mis en relation par simulation ;
  défense en profondeur à la confirmation ; bandeau « MODE DÉMONSTRATION » sur tout le site public.
- Verrou sur le client lors d'une confirmation (double relation en cas de confirmations concurrentes).
- API : `address` retirée de l'API publique et de ses champs de recherche (adresse devinable).
- Vérificateur : ne peut plus noter un propriétaire ; mot de passe des comptes vérificateurs soumis
  aux validateurs Django.
- `audit_verification --fix` aurait accordé la publication à 7 comptes « approuvés » **sans aucune
  preuve** → la commande ne donne plus jamais de droit à une approbation non justifiée et exige `--confirm`.
- Montant : 9 réponses de l'assistant IA et sa base de connaissances lisent `CONTACT_FEE_AMOUNT`.
- E-mails retirés des journaux (`services/email_service.py`).

Tests : `payments/tests_audit.py` (18). Total : 220 tests, identiques avec ou sans étiquettes
d'applications (les scripts de `scripts/legacy/` ne sont pas découverts).

---

## Phase « fonctionnalités de bout en bout » (2026-10-19)

Détail : `docs/ABONNEMENTS_CLASSEMENT_MESSAGERIE.md`.
- Incident signalé : lors de l'audit précédent, la commande prévue sur une copie a appliqué les
  migrations additives à `db.sqlite3` (14:19). Aucune donnée n'a été modifiée par cette opération
  (vérifié par comparaison avec la sauvegarde initiale). Les mesures utilisent désormais un script
  qui force explicitement la base visée.
- 7 comptes approuvés sans preuve (79, 93, 95, 97, 99, 101, 103) → « non vérifié » en local
  (`reset_unproven_approvals --apply`, journal de retour arrière dans `../domiora_backups/`).
- Validation d'annonce par l'admin : POST uniquement et propriétaire vérifié obligatoire.
- Abonnements simulés complets, classement « Recommandés » + « Sponsorisé », messagerie quasi temps
  réel par interrogation, avis vérifiés, stockage privé des fichiers sensibles, défilé unique sur
  l'accueil, N+1 supprimé sur la liste (17 → 3 requêtes SQL).
- Migrations : `owner_subscriptions/0002`, `ratings/0002`, `accounts/0012`, `field_verification/0002`,
  `properties/0014` (appliquées en local après sauvegarde `../domiora_backups/2026-10-19-phase2/`).

---

## Finalisation locale (2026-10-19, soir)

- Frais de mise en relation confirmés à 500 FCFA (source unique `CONTACT_FEE_AMOUNT`) ; aucun
  « 700 FCFA » n'existe (seul « 700 » : une distance en mètres).
- Essai 30 jours préparé, inactif, réservé aux comptes inscrits après une date à fixer ; retour
  automatique au plan Gratuit à l'échéance.
- Quotas Sponsorisé 1/3/5 vérifiés (serveur, rotation quotidienne, expiration).
- Questions avant mise en relation (`messaging.ListingInquiry`, migration `0007`), anti-spam et
  coordonnées bloquées.
- Annonce 256 du compte 93 : diffusion suspendue en local (`suspend_unverified_owner_listings`,
  journal de retour arrière) ; annonce, médias, relations et conversations conservés.
- Tâche Celery `owner_subscriptions.process_due` ; documentation de planification Render.
- 275 tests OK.

---

## Liste de tâches

- [x] Étape 0 — audit, sauvegarde, branche
- [x] Étape 1 — failles critiques, décorateur, API, relations gratuites
- [x] Étape 2 — paiements simulés + tests
- [x] Étape 3 — missions de vérification de terrain (rôle VERIFIER)
- [~] Étape 4 — UX ciblée faite ; refonte globale en attente de validation
- [x] Étape 5 — mobile (PWA)
- [x] Étape 6 — abonnements propriétaires (désactivés)
- [~] Étape 7 — badge + signalement faits ; autres en attente de décision
- [~] Étape 8 — audit du code fait ; validation production à faire par vous
- [x] Étape 9 — CI GitHub Actions, sécurité, performance
