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
| 700 FCFA | **aucune occurrence** dans le code, la configuration ni l'historique Git | — | Origine inconnue : à préciser |
| `property_boost.BoostPackage` | modèle en USD, 0 ligne | app non branchée | Concept concurrent dormant (boost par annonce) |

Transactions enregistrées en local : 1 `PaymentAttempt` simulé (500 FCFA, approuvé, compte de test
créé par vous le 19/10), 0 `Transaction`, 0 boost. Les montants enregistrés sont figés : la
synchronisation des plans ne modifie jamais `SubscriptionPayment.amount`.

**Décisions requises** : prix définitifs ; sort du 700 FCFA ; durée de l'essai ; quotas
`max_promoted_listings` (1/3/5 proposés) ; avantages du 4e niveau ; conservation ou retrait de
`property_boost` ; limite éventuelle d'annonces du plan gratuit (aucune limite imposée aujourd'hui).

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

- Le contact exige une relation payée (règle métier) : un visiteur sans relation est redirigé
  vers la mise en relation. *(La demande « un visiteur peut écrire depuis une annonce » contredit
  cette règle ; non implémentée.)*
- Message → notification du destinataire (une par message) ; ouverture → messages marqués lus ;
  contrôle d'accès 404 sur tout identifiant de conversation d'autrui.
- **Temps réel** : pas de WebSocket (Django Channels absent ; Render gratuit en WSGI/gunicorn).
  Repli réel et documenté : `GET /messagerie/<id>/etat/` toutes les 5 s (onglet visible), la zone
  des messages n'est rechargée que s'il y a du nouveau ; compteur `GET /notifications/non-lues/`
  toutes les 30 s. Pas de notification push externe (aucune clé de service configurée).

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

## 7. Plan de déploiement futur (NON exécuté)

1. Sauvegarde Render PostgreSQL (`pg_dump`) + export Cloudinary ; vérifier la restauration sur une base de test.
2. Variables : `OWNER_SUBSCRIPTIONS_ENABLED=False` (tant que les prix ne sont pas validés),
   `PAYMENT_MODE=fedapay` ou démo isolée, `PRIVATE_MEDIA_BACKEND=cloudinary`.
3. `python manage.py migrate` — migrations additives, sauf `owner_subscriptions/0002` (retire
   `Plan.trial_days`, table vide car jamais déployée) et les `AlterField` de stockage (sans effet SQL).
4. `sync_subscription_plans` ; `migrate_private_media` en simulation, puis `--apply --limit 5`,
   contrôle, puis le reste.
5. `reset_unproven_approvals` en simulation sur la production, décision, puis `--apply`
   (journal JSON de retour arrière).
6. Retour arrière : redéployer le commit précédent ; restaurer la base ; `--rollback` du journal.
