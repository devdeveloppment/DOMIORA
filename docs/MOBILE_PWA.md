# DOMIORA mobile — application web installable (PWA)

## Choix

Le dépôt ne contient aucune base mobile native et toute l'interface est déjà en Tailwind
responsive. Une PWA permet donc de livrer vite une expérience mobile complète, **sans
dupliquer les règles métier** : chaque écran est servi par Django, avec les mêmes
permissions côté serveur (rôles, relation payée, contrôle objet). Une application native
(Flutter / React Native) ne se justifierait que pour un besoin précis : notifications push
hors navigateur, prise de vue avancée ou fonctionnement long hors ligne. Elle consommerait
alors l'API REST existante (`/api/`).

## Couverture par rôle (mêmes pages que le web, adaptées au mobile)

| Rôle | Parcours |
|---|---|
| Client | inscription au paiement, connexion, recherche et filtres, recherche IA, détail du bien, favoris, comparaison, mise en relation (paiement), messagerie, demandes de visite, historique des paiements |
| Propriétaire | profil, dépôt des pièces d'identité, création et gestion des annonces, photos, visite virtuelle, messages, demandes de visite |
| Vérificateur | `/dashboard/verificateur/` : missions, planification, checklist, photos depuis l'appareil photo (`capture`), GPS facultatif, rapport |
| Administrateur | tableau de bord web (pas d'interface mobile dédiée) |

## Confidentialité et données

- Le service worker (`static/pwa/sw.js`, servi en `/sw.js`) ne met en cache **que** `/static/`.
- Les pages HTML, l'API, la messagerie, les pièces d'identité, les preuves et les coordonnées
  ne sont jamais stockées sur l'appareil. Hors connexion : page `/hors-ligne/`.
- L'application ne contient aucun secret : toutes les clés restent côté serveur.

## Faible consommation de données

- Images des annonces en `loading="lazy"`.
- Vidéos de visite virtuelle en `preload="none"` : rien n'est téléchargé avant l'appui sur lecture.
- Fichiers statiques compressés (WhiteNoise) et mis en cache après la première visite.

## Installer et tester

1. `python manage.py runserver`, puis ouvrir `http://localhost:8000` (le service worker exige
   HTTPS, sauf sur `localhost`).
2. Chrome Android : menu ⋮ → « Installer l'application ». iOS Safari : Partager → « Sur l'écran d'accueil ».
3. Vérification : Chrome DevTools → Application → Manifest / Service Workers. Pour le test hors
   ligne : Network → Offline, puis recharger (la page « hors connexion » s'affiche).
4. Tests automatisés : `python manage.py test core.tests_pwa`.

En production (Render, HTTPS), l'installation fonctionne sans aucune configuration supplémentaire.
