#!/usr/bin/env bash
# Démarrage du service web DOMIORA sur Render (offre gratuite).
#
# Les Background Workers Render n'ont pas d'offre gratuite : le worker Celery qui génère
# les visites virtuelles tourne donc dans ce même conteneur, en arrière-plan.
#   --pool=solo : un seul processus (mémoire limitée à 512 Mo sur l'offre gratuite).
# Limites connues : si l'instance se met en veille pendant une génération, la tâche est
# reprise au redémarrage (ou relancée depuis le tableau de bord).
set -o errexit

# Dossiers du broker filesystem (sans Redis) : absents d'un conteneur neuf.
mkdir -p .celery/broker/out .celery/broker/processed

celery -A config worker --pool=solo --concurrency=1 --loglevel=info &

# --timeout 120 : sur l'instance gratuite (CPU partagé), la première requête après un réveil peut
# dépasser les 30 s par défaut ; gunicorn tuait alors le processus (erreur 500 au premier chargement).
exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --timeout 120
