# Abonnements, classement, messagerie, avis et médias privés

> Évolution produit postérieure au mémoire (ne pas reporter dans le mémoire).
> Tout est fonctionnel **en local** ; rien n'est déployé, aucun paiement réel n'existe.

## 1. Tableau tarifaire (audit — aucun tarif n'est validé)

| Élément | Valeur trouvée | Où | Statut |
|---|---|---|---|
| Frais de mise en relation client ↔ propriétaire | 500 FCFA | `CONTACT_FEE_AMOUNT` (settings/env) — UI, assistant IA, paiements | Appliqué depuis l'origine ; à confirmer |
| `PAYMENT_AMOUNT` | 2000 FCFA | `config/settings.py` | **Inutilisé**, contradictoire, conservé « obsolète » |
| Don : minimum / défaut | 100 / 2000 FCFA | `core/views.py` (dons FedaPay, désactivés en démo) | Hors abonnements |
| Plan Gratuit | 0 | `SUBSCRIPTION_PLAN_PROPOSALS` → table `Plan` | Proposition |
| Plan Intermédiaire | 1 000 FCFA / 30 j | idem | **Proposition** |
| Plan Supérieur | 2 000 FCFA / 30 j | idem | **Proposition** |
| Plan Premium | 5 000 FCFA / 30 j | idem | **Proposition** |
| 4e niveau « Entreprise » | non défini | idem (`is_active=False`, non souscriptible) | À définir |
| 700 | seule occurrence métier : `("Marché", 700)` = **distance en mètres** (services de proximité par défaut, `properties/views.py`) | — | Aucun lien avec un tarif ; aucune référence à 700 FCFA à supprimer |
| `property_boost.BoostPackage` | modèle en USD, 0 ligne | app non branchée | Concept concurrent dormant (boost par annonce) |

Transactions enregistrées en local : 1 `PaymentAttempt` simulé (500 FCFA, approuvé, compte de test
créé par vous le 19/10), 0 `Transaction`, 0 boost. Les montants enregistrés sont figés : la
synchronisation des plans ne modifie jamais `SubscriptionPayment.amount`.

Frais de mise en relation (correction officielle) : **500 FCFA par client**, payés une fois par
propriétaire avant toute mise en relation. Source unique : `CONTACT_FEE_AMOUNT` ; affichés via le
context processor `contact_fee_amount` et `services/assistant_knowledge.CONNECTION_FEE` ; montant
figé dans `PaymentAttempt.amount`. Strictement séparés des abonnements (`SubscriptionPayment`).

**Décisions requises** : prix définitifs des plans ; activation et date d'éligibilité de l'essai ;
avantages du niveau Entreprise ; limite éventuelle d'annonces du plan gratuit (aucune aujourd'hui).

### Audit `property_boost`
Modèles `BoostPackage`/`PropertyBoost` (prix en USD), migration `0001`, aucune vue, aucune URL,
aucune donnée (0 ligne), gabarit `partials/property_boost_manager.html` jamais inclus et dont les
appels d'API sont commentés. **Non utilisé.** Couvert par les abonnements : mise en avant en tête
de recherche, badge. **Non couvert** : boost ponctuel par annonce (1 à 30 jours) et statistiques
vues/demandes avant/pendant. Conservé tant que ce besoin n'est pas tranché.

### Autres constats (non corrigés, décision requise)
- `_default_nearby_services` affiche des distances **inventées** (École 250 m, Marché 700 m…) quand
  un bien n'a pas de services renseignés : données fictives présentées comme réelles.
- `partials/price_estimation_display.html` (fiche d'un bien) appelle
  `/api/properties/<id>/price-estimation/`, route inexistante : fonctionnalité inopérante.

## 2. Abonnements (app `owner_subscriptions`)

- Source de vérité unique : table `Plan` (chargée par `python manage.py sync_subscription_plans`,
  idempotent). Le web, l'API (`/api/subscriptions/plans/`, `/api/subscriptions/me/`, lecture seule)
  et la PWA lisent la même base.
- Statuts : `pending` (paiement simulé attendu), `trial`, `active`, `expired`, `canceled`,
  `superseded` (remplacé par un autre plan). Contraintes en base : un seul abonnement en cours et
  une seule demande en attente par propriétaire.
- Règles : gratuit immédiat ; payant → `pending` + transaction fictive, activé **uniquement**
  après la décision « réussi » du simulateur traitée côté serveur ; essai (`SUBSCRIPTION_TRIAL_DAYS`,
  0 par défaut) une seule fois par propriétaire ; montée de plan immédiate après paiement (pas de
  prorata) ; descente programmée à l'échéance ; annulation = avantages jusqu'à l'échéance ;
  renouvellement simulé = +1 période. Avantages retirés dès l'échéance, même avant le traitement.
- Échéances : `python manage.py process_owner_subscriptions` (idempotent) — à planifier (cron Render
  « Cron Job », ou tâche Celery beat) toutes les heures. Non planifié actuellement.
- Activation : `OWNER_SUBSCRIPTIONS_ENABLED` (défaut = `DEBUG`). Aucun abonnement n'est exigé pour publier.

### Passage au paiement réel (non activé)
1. Valider prix, essai, quotas ; mettre `is_proposal=False`.
2. Ajouter un fournisseur d'abonnement (FedaPay) sur le modèle de `payments/providers.py` :
   création de transaction, vérification serveur par API, webhook signé et idempotent.
3. Remplacer `decide_payment` (simulateur) par la confirmation fournisseur ; garder
   `environment="live"` et `is_simulated=False` pour les vraies transactions.
4. Tests sandbox FedaPay, puis activation progressive.

### Essai gratuit
Durée préparée : 30 jours (`SUBSCRIPTION_TRIAL_DAYS`). Inactif (`SUBSCRIPTION_TRIAL_ENABLED=False`).
Éligibilité : propriétaire inscrit à partir de `SUBSCRIPTION_TRIAL_ELIGIBLE_FROM`, sans essai déjà
utilisé, sans abonnement en cours. Échéance = début + 30 × 24 h (UTC = heure de Lomé) ; avantages
retirés à l'instant exact de l'échéance ; `process_owner_subscriptions` passe l'essai en « expiré » et
crée un abonnement Gratuit sans échéance. L'essai n'est pas renouvelable.

### Planification de `process_owner_subscriptions`
Idempotente (testée : relancer à l'identique ne traite rien). Options :
1. **Render Cron Job** (service séparé, payant sur Render) : commande
   `python manage.py process_owner_subscriptions`, planification `0 * * * *` (toutes les heures),
   mêmes variables d'environnement et même base que le service web.
2. **Celery beat** : tâche `owner_subscriptions.process_due` (`owner_subscriptions/tasks.py`) ; exige
   un processus beat (non lancé par `start.sh` aujourd'hui).
3. À défaut : exécution manuelle ou cron système. Les avantages sont de toute façon retirés à
   l'échéance même si la commande n'a pas tourné (calcul à la lecture).
Aucun service Render n'a été créé ni modifié.

## 3. Classement et mise en avant (`properties/ranking.py`)

Tri par défaut « Recommandés » sur `/proprietes/` (les tris Récents / Prix / Popularité restent
disponibles et ne sont **pas** influencés par les abonnements).

| Critère | Poids (configurable `RANKING_WEIGHTS`) |
|---|---|
| Fraîcheur (décroît sur 60 jours) | 30 |
| Qualité : photos (≤5), description ≥ 200 car., surface, coordonnées | 30 |
| Propriétaire vérifié | 10 |
| Abonnement : 6 par niveau (1/2/3), **plafonné à 18** | ≤ 18 |

Le plafond garantit qu'une annonce payante ancienne et incomplète reste derrière une annonce
gratuite récente et complète (test `test_bonus_is_capped_and_relevance_wins`). La pertinence de
recherche est assurée par le filtrage : le score ne classe que les résultats de la recherche.

Emplacements « Sponsorisé » : au plus `RANKING_SPONSORED_SLOTS` (2), première page uniquement,
choisis parmi les résultats de la recherche courante, rotation quotidienne pondérée par le
niveau, libellés « Sponsorisé » dans un bloc distinct. Éligibilité : abonnement en cours non échu,
propriétaire actif et vérifié, annonce publiée et validée, quota du plan (meilleures annonces du
propriétaire), moins de 2 signalements ouverts. Aucune diffusion externe n'est réalisée.

## 4. Messagerie et notifications

### Question avant mise en relation (premier contact)
Un client connecté peut poser **une question** depuis une annonce (`/proprietes/<slug>/question/`) :
10 à 500 caractères ; numéros, e-mails, liens et messageries externes bloqués dans la question et
la réponse ; une question ouverte par propriétaire ; 3 questions par jour ; une seule réponse du
propriétaire (`/dashboard/proprietaire/questions/`), notifiée au client (`/dashboard/client/questions/`).
Elle ne crée **aucune** relation et ne donne ni coordonnées, ni conversation, ni visite, ni avis :
la mise en relation reste à 500 FCFA.

- Le contact exige une relation payée (règle métier) : un visiteur sans relation est redirigé
  vers la mise en relation. *(La demande « un visiteur peut écrire depuis une annonce » contredit
  cette règle ; non implémentée.)*
- Message → notification du destinataire (une par message) ; ouverture → messages marqués lus ;
  contrôle d'accès 404 sur tout identifiant de conversation d'autrui.
- **Temps réel** : pas de WebSocket (Django Channels absent ; Render gratuit en WSGI/gunicorn).
  Repli réel et documenté : `GET /messagerie/<id>/etat/` toutes les 5 s (onglet visible), la zone
  des messages n'est rechargée que s'il y a du nouveau ; compteur `GET /notifications/non-lues/`
  toutes les 30 s. Pas de notification push externe (aucune clé de service configurée).

Limites de l'interrogation : délai jusqu'à 5 s (messages) / 30 s (compteur) ; une requête par
onglet ouvert et par intervalle (charge proportionnelle aux utilisateurs connectés) ; arrêt quand
l'onglet est masqué ; aucune notification si l'application est fermée.

Option future (non active) : Django Channels + serveur ASGI (Daphne/Uvicorn) + Redis (déjà prévu
pour Celery), groupes par conversation, événements émis par `transaction.on_commit` après
l'enregistrement ; push mobile via Web Push (clés VAPID) ou Firebase Cloud Messaging ; le repli
par interrogation resterait en secours.

## 5. Avis vérifiés (`ratings/eligibility.py`)

Un avis par relation client ↔ propriétaire, réservé au **client** ayant : un `PaymentAttempt`
approuvé (FedaPay ; simulé seulement entre comptes de démonstration) **et** une visite acceptée
dont la date est passée (« relation achevée » — définition à valider). Les relations
historiques sans enregistrement de paiement ne sont pas éligibles.

## 6. Médias privés

Pièces d'identité (profil et dossiers), preuves de terrain et documents de bien utilisent
`core/private_storage.py` : jamais d'URL publique, lecture via vues protégées
(`/dashboard/fichiers/...`, `/dashboard/preuves/...`). Médias publics (photos d'annonces,
vidéos, avatars, logo) inchangés.

Migration des fichiers existants : `python manage.py migrate_private_media` (simulation) puis
`--apply [--limit N]`. Exécutée **en local uniquement** : 4 fichiers copiés et vérifiés (SHA-256),
7 références sans fichier local (probablement hébergés sur Cloudinary en production), 0 doublon ;
originaux conservés. Backend Cloudinary « authenticated » écrit mais **non testé** contre un
compte réel. Retour arrière : les champs gardent les mêmes noms et `open_private()` relit
l'ancien stockage ; supprimer les copies privées suffit. Les originaux publics ne seront
supprimés qu'après validation et autorisation explicite. Coûts Cloudinary : le type
« authenticated » consomme le même quota de stockage ; chaque lecture passe par le serveur.

### Les 7 fichiers sensibles absents en local
`accounts.User` pk 1 (`id_document`) et `IdentityVerificationRequest` pk 1, 2, 3 (recto et verso).
Leurs noms commencent par `media/`, préfixe ajouté par `django-cloudinary-storage` : ce sont très
probablement des fichiers stockés sur le Cloudinary de **production**, jamais présents sur ce poste.
Réconciliation (avec accès production, non effectuée) : 1) lister ces ressources dans Cloudinary
(type upload) ; 2) `migrate_private_media` en simulation sur la production ; 3) `--apply --limit 1`,
contrôle d'affichage admin ; 4) le reste ; 5) suppression des originaux publics seulement après
autorisation. Aucun identifiant Cloudinary n'est présent dans `.env` local : le stockage privé
Cloudinary n'a été testé qu'avec un SDK simulé (signature et type « authenticated » vérifiés hors ligne).

## 7. Plan de déploiement futur (NON exécuté)

1. Sauvegarde Render PostgreSQL (`pg_dump`) + export Cloudinary ; vérifier la restauration sur une base de test.
2. Variables : `OWNER_SUBSCRIPTIONS_ENABLED=False` (tant que les prix ne sont pas validés),
   `PAYMENT_MODE=fedapay` ou démo isolée, `PRIVATE_MEDIA_BACKEND=cloudinary`.
3. `python manage.py migrate` — migrations additives, sauf `owner_subscriptions/0002` (retire
   `Plan.trial_days`, table vide car jamais déployée) et les `AlterField` de stockage (sans effet SQL).
4. `sync_subscription_plans` ; `migrate_private_media` en simulation, puis `--apply --limit 5`,
   contrôle, puis le reste.
5. `reset_unproven_approvals` en simulation sur la production, décision, puis `--apply`
   (journal JSON de retour arrière) ; puis `suspend_unverified_owner_listings` en simulation,
   décision, `--apply` (journal ; `--rollback` pour republier).
6. Migration `messaging/0007` (nouvelle table des questions).
7. Retour arrière : redéployer le commit précédent ; restaurer la base ; `--rollback` du journal.
