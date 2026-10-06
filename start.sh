#!/usr/bin/env bash
# Démarrage du service web DOMIORA sur Render (offre gratuite).
#
# Les Background Workers Render n'ont pas d'offre gratuite : le worker Celery qui génère
# les visites virtuelles tourne donc dans ce même conteneur, en arrière-plan.
#   --pool=solo : un seul processus (mémoire limitée à 512 Mo sur l'offre gratuite).
# Limites connues : si l'instance se met en veille pendant une génération, la tâche est
# reprise au redémarrage (ou relancée depuis le tableau de bord).
set -o errexit

celery -A config worker --pool=solo --concurrency=1 --loglevel=info &

exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
