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

## Liste de tâches

- [x] Étape 0 — audit, sauvegarde, branche
- [x] Étape 1 — failles critiques, décorateur, API, relations gratuites
- [x] Étape 2 — paiements simulés + tests
- [ ] Étape 3 — missions de vérification de terrain (rôle VERIFIER)
- [ ] Étape 4 — système visuel / UX
- [ ] Étape 5 — mobile (PWA)
- [ ] Étape 6 — abonnements propriétaires (désactivés)
- [ ] Étape 7 — innovations (badge, signalement, alertes…)
- [ ] Étape 8 — audit vidéo / Render
- [ ] Étape 9 — CI GitHub Actions, sécurité, performance
