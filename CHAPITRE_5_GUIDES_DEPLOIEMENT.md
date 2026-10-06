# CHAPITRE 5 : GUIDES DE DÉPLOIEMENT ET D'EXPLOITATION

## 5.1. Configurations matérielles et logicielles

### 5.1.1 Configuration matérielle requise

#### Configuration minimale (Développement)

- **Processeur** : Intel Core i3 ou équivalent (2 cœurs minimum)
- **Mémoire vive (RAM)** : 4 Go minimum, 8 Go recommandé
- **Espace disque** : 20 Go minimum (espace pour le système, le code et les données)
- **Système d'exploitation** : Windows 10/11, macOS 10.14+, ou Linux (Ubuntu 18.04+)
- **Connexion internet** : Nécessaire pour l'installation des dépendances et les services externes

#### Configuration recommandée (Production)

- **Processeur** : Intel Core i5/i7 ou équivalent (4 cœurs minimum)
- **Mémoire vive (RAM)** : 8 Go minimum, 16 Go recommandé
- **Espace disque** : 100 Go minimum (incluant le système, le code, les médias et les sauvegardes)
- **Système d'exploitation** : Ubuntu 20.04 LTS ou CentOS 8+
- **Connexion internet** : Haut débit stable requis pour les services web et API

#### Configuration serveur (Hébergement cloud)

- **Processeur** : 2-4 vCPUs (Amazon EC2 t3.medium ou équivalent)
- **Mémoire vive (RAM)** : 4-8 Go
- **Espace disque** : 50-100 Go SSD
- **Bande passante** : Minimum 1 Gbps
- **Base de données** : PostgreSQL managé (AWS RDS, Google Cloud SQL) avec 10 Go minimum

### 5.1.2 Configuration logicielle requise

#### Stack technique principale

| Composant | Version minimum | Version recommandée | Notes |
|-----------|-----------------|---------------------|-------|
| **Python** | 3.8+ | 3.11+ | Langage principal |
| **Django** | 4.2+ | 5.0+ | Framework web |
| **Django REST Framework** | 3.14+ | 3.15+ | API REST |
| **PostgreSQL** | 12+ | 15+ | Base de données production |
| **Node.js** | 16+ | 18+ | Pour les outils frontend |
| **Git** | 2.20+ | 2.40+ | Gestion de version |

#### Dépendances Python principales

- `django==5.0.0`
- `djangorestframework==3.15.0`
- `psycopg2-binary==2.9.9`
- `Pillow==10.2.0`
- `django-cors-headers==4.3.1`
- `django-filter==23.5`
- `python-decouple==3.8`
- `celery==5.3.6`
- `redis==5.0.1`
- `cloudinary==1.40.0`
- `stripe==7.10.0`
- `google-cloud-aiplatform==1.49.0`

#### Frontend et assets

- **Tailwind CSS** : 3.4.0 (via CDN pour production)
- **Alpine.js** : 3.13.0 (interactivité légère)
- **Chart.js** : 4.4.0 (graphiques)
- **Leaflet** : 1.9.4 (cartes interactives)
- **Font Awesome** : 6.4.0 (icônes)

#### Services externes requis

- **SMTP** : Serveur de messagerie (Gmail, SendGrid, Mailgun)
- **Stockage cloud** : Cloudinary (images et médias)
- **API d'IA** : Mistral API (assistant conversationnel)
- **Automatisation** : n8n Cloud (workflows de vérification)
- **Tunnel sécurisé** : ngrok (développement uniquement)

#### Outils de développement

- **Éditeur de code** : VS Code, PyCharm, ou équivalent
- **Client PostgreSQL** : pgAdmin, DBeaver
- **Outil de gestion API** : Postman, Insomnia
- **Contrôle de version** : Git/GitHub
- **Conteneurisation** : Docker (optionnel pour production)

### 5.1.3 Configuration réseau et sécurité

#### Ports requis

- **80** : HTTP (redirection vers HTTPS en production)
- **443** : HTTPS (principal)
- **8000** : Django dev server (développement uniquement)
- **5432** : PostgreSQL (local ou interne)
- **6379** : Redis ( tâches asynchrones)

#### Configuration firewall

```
# Ports à ouvrir en production
80/tcp   - HTTP (redirect)
443/tcp  - HTTPS
22/tcp   - SSH (restrictif, clé publique uniquement)

# Ports internes (fermés depuis l'extérieur)
5432/tcp - PostgreSQL
6379/tcp - Redis
```

#### Certificats SSL/TLS

- **Développement** : Pas requis (HTTP uniquement)
- **Production** : Certificat SSL/TLS obligatoire (Let's Encrypt gratuit recommandé)
- **Type** : RSA 2048 bits ou ECDSA P-256
- **Renouvellement** : Automatique via Certbot

---

## 5.2. Guide de déploiement

### 5.2.1 Préparation de l'environnement

#### Étape 1 : Installation des dépendances système

**Ubuntu/Debian :**
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv postgresql postgresql-contrib nginx redis-server git
```

**CentOS/RHEL :**
```bash
sudo yum update
sudo yum install -y python3-pip python3-venv postgresql-server nginx redis git
```

**Windows :**
```powershell
# Installer Python depuis python.org
# Installer PostgreSQL depuis postgresql.org
# Installer Git depuis git-scm.com
```

#### Étape 2 : Clonage du projet

```bash
git clone https://github.com/votre-organisation/domiora.git
cd domiora
```

#### Étape 3 : Création de l'environnement virtuel

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

#### Étape 4 : Installation des dépendances Python

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5.2.2 Configuration de la base de données

#### Configuration PostgreSQL locale

```bash
# Créer la base de données
sudo -u postgres psql
CREATE DATABASE domiora;
CREATE USER domiora WITH PASSWORD 'mot_de_passe_securise';
GRANT ALL PRIVILEGES ON DATABASE domiora TO domiora;
\q
```

#### Configuration PostgreSQL cloud (AWS RDS)

1. Créer une instance PostgreSQL dans AWS RDS
2. Configurer les groupes de sécurité (autoriser l'accès depuis le serveur)
3. Notez l'endpoint, le port, l'utilisateur et le mot de passe
4. Mettre à jour le fichier `.env` avec ces informations

### 5.2.3 Configuration des variables d'environnement

#### Création du fichier `.env`

```bash
cp .env.example .env
```

#### Variables d'environnement obligatoires

```bash
# Configuration Django
SECRET_KEY=votre_cle_secrete_aleatoire_ici
DEBUG=False
ALLOWED_HOSTS=votre-domaine.com,www.votre-domaine.com

# Base de données
DATABASE_URL=postgres://domiora:mot_de_passe@localhost:5432/domiora

# Sécurité
CSRF_TRUSTED_ORIGINS=https://votre-domaine.com,https://www.votre-domaine.com

# Configuration SMTP
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=votre-email@gmail.com
EMAIL_HOST_PASSWORD=votre_mot_de_passe_application
DEFAULT_FROM_EMAIL=DOMIORA <denistchil@gmail.com>

# Cloudinary (stockage images)
CLOUDINARY_CLOUD_NAME=votre_cloud_name
CLOUDINARY_API_KEY=votre_api_key
CLOUDINARY_API_SECRET=votre_api_secret

# Mistral API (assistant IA)
MISTRAL_API_KEY=votre_mistral_api_key
MISTRAL_MODEL=mistral-small-latest

# n8n (automatisation)
N8N_IDENTITY_VERIFICATION_WEBHOOK=https://votre-workflow.n8n.cloud/webhook/domiora
N8N_ADMIN_NOTIFICATION_WEBHOOK=https://votre-domaine.com/api/admin/notifications/

# Redis (tâches asynchrones)
REDIS_URL=redis://localhost:6379/0

# Base URL pour webhooks
BASE_URL=https://votre-domaine.com
```

#### Génération d'une clé secrète sécurisée

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5.2.4 Initialisation de la base de données

```bash
# Appliquer les migrations
python manage.py migrate

# Créer le super-utilisateur
python manage.py createsuperuser

# Charger les données de démonstration (optionnel)
python manage.py seed_demo_data

# Collecter les fichiers statiques
python manage.py collectstatic --noinput
```

### 5.2.5 Configuration de Nginx

#### Installation de Nginx

```bash
sudo apt install nginx  # Ubuntu/Debian
sudo yum install nginx  # CentOS/RHEL
```

#### Configuration du fichier `/etc/nginx/sites-available/domiora`

```nginx
server {
    listen 80;
    server_name votre-domaine.com www.votre-domaine.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /chemin/vers/domiora/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /chemin/vers/domiora/media/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

#### Activation du site

```bash
sudo ln -s /etc/nginx/sites-available/domiora /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 5.2.6 Configuration SSL avec Let's Encrypt

```bash
# Installer Certbot
sudo apt install certbot python3-certbot-nginx

# Obtenir et configurer le certificat
sudo certbot --nginx -d votre-domaine.com -d www.votre-domaine.com

# Renouvellement automatique (déjà configuré par Certbot)
sudo certbot renew --dry-run
```

### 5.2.7 Configuration de Gunicorn

#### Installation de Gunicorn

```bash
pip install gunicorn
```

#### Création du service systemd `/etc/systemd/system/domiora.service`

```ini
[Unit]
Description=DOMIORA Django Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/chemin/vers/domiora
Environment="PATH=/chemin/vers/domiora/venv/bin"
ExecStart=/chemin/vers/domiora/venv/bin/gunicorn \
          --workers 3 \
          --bind unix:/chemin/vers/domiora/domiora.sock \
          config.wsgi:application

[Install]
WantedBy=multi-user.target
```

#### Activation du service

```bash
sudo systemctl start domiora
sudo systemctl enable domiora
sudo systemctl status domiora
```

### 5.2.8 Configuration de Celery (tâches asynchrones)

#### Installation et configuration Redis

```bash
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

#### Configuration du service Celery `/etc/systemd/system/domiora-celery.service`

```ini
[Unit]
Description=DOMIORA Celery Worker
After=network.target redis.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/chemin/vers/domiora
Environment="PATH=/chemin/vers/domiora/venv/bin"
ExecStart=/chemin/vers/domiora/venv/bin/celery -A config worker -l INFO

[Install]
WantedBy=multi-user.target
```

#### Activation du service Celery

```bash
sudo systemctl start domiora-celery
sudo systemctl enable domiora-celery
```

### 5.2.9 Vérification du déploiement

#### Tests de fonctionnement

```bash
# Vérifier le statut des services
sudo systemctl status domiora
sudo systemctl status domiora-celery
sudo systemctl status nginx
sudo systemctl status redis

# Vérifier les logs
sudo journalctl -u domiora -f
sudo journalctl -u domiora-celery -f

# Test de l'application
curl https://votre-domaine.com
curl https://votre-domaine.com/admin/
```

#### Liste de vérification finale

- [ ] Base de données PostgreSQL configurée et accessible
- [ ] Variables d'environnement `.env` correctement remplies
- [ ] Migrations appliquées avec succès
- [ ] Fichiers statiques collectés
- [ ] Nginx configuré et fonctionnel
- [ ] Certificat SSL installé et valide
- [ ] Gunicorn service actif
- [ ] Celery service actif
- [ ] Redis service actif
- [ ] Application accessible via HTTPS
- [ ] Interface d'administration accessible
- [ ] Tests fonctionnels passés

---

## 5.3. Guide d'exploitation

### 5.3.1 Surveillance et monitoring

#### Surveillance des services

```bash
# Script de surveillance des services (cron toutes les 5 minutes)
*/5 * * * * /chemin/vers/check_services.sh
```

#### Fichier `check_services.sh`

```bash
#!/bin/bash
SERVICES=("domiora" "domiora-celery" "nginx" "redis" "postgresql")

for service in "${SERVICES[@]}"; do
    if ! systemctl is-active --quiet "$service"; then
        echo "Alerte: $service n'est pas actif" | mail -s "Alerte Service DOMIORA" admin@domiora.com
        systemctl restart "$service"
    fi
done
```

#### Surveillance des logs

```bash
# Logs Django/Gunicorn
sudo journalctl -u domiora -f

# Logs Celery
sudo journalctl -u domiora-celery -f

# Logs Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Logs PostgreSQL
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

#### Outils de monitoring recommandés

- **Sentry** : Suivi des erreurs et exceptions
- **New Relic** : Monitoring des performances applicatives
- **Prometheus + Grafana** : Métriques et dashboards
- **Uptime Robot** : Surveillance de disponibilité

### 5.3.2 Sauvegardes et restauration

#### Stratégie de sauvegarde

**Fréquence des sauvegardes :**
- Base de données : Quotidienne (à 2h du matin)
- Fichiers médias : Hebdomadaire
- Configuration : À chaque changement

#### Script de sauvegarde PostgreSQL

```bash
#!/bin/bash
# backup_database.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/postgresql"
DB_NAME="domiora"
DB_USER="domiora"

mkdir -p $BACKUP_DIR

pg_dump -U $DB_USER $DB_NAME | gzip > $BACKUP_DIR/domiora_$DATE.sql.gz

# Garder les 30 derniers jours
find $BACKUP_DIR -name "domiora_*.sql.gz" -mtime +30 -delete
```

#### Script de sauvegarde des médias

```bash
#!/bin/bash
# backup_media.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/media"
MEDIA_DIR="/chemin/vers/domiora/media"

mkdir -p $BACKUP_DIR

tar -czf $BACKUP_DIR/media_$DATE.tar.gz $MEDIA_DIR

# Garder les 4 dernières semaines
find $BACKUP_DIR -name "media_*.tar.gz" -mtime +28 -delete
```

#### Configuration des tâches cron

```bash
# Sauvegarde de la base de données (quotidienne à 2h du matin)
0 2 * * * /chemin/vers/backup_database.sh

# Sauvegarde des médias (hebdomadaire le dimanche à 3h du matin)
0 3 * * 0 /chemin/vers/backup_media.sh

# Nettoyage des logs (mensuel)
0 0 1 * * /chemin/vers/cleanup_logs.sh
```

#### Restauration de la base de données

```bash
# Décompresser et restaurer
gunzip < /backups/postgresql/domiora_20240912_020000.sql.gz | psql -U domiora domiora
```

### 5.3.3 Mises à jour et maintenance

#### Procédure de mise à jour du code

```bash
# 1. Sauvegarder la base de données
./backup_database.sh

# 2. Récupérer les dernières modifications
git pull origin main

# 3. Mettre à jour les dépendances
pip install -r requirements.txt

# 4. Appliquer les migrations
python manage.py migrate

# 5. Collecter les fichiers statiques
python manage.py collectstatic --noinput

# 6. Redémarrer les services
sudo systemctl restart domiora
sudo systemctl restart domiora-celery
```

#### Maintenance de la base de données

```bash
# Optimisation de la base de données
sudo -u postgres psql -d domiora -c "VACUUM ANALYZE;"

# Réindexation
sudo -u postgres psql -d domiora -c "REINDEX DATABASE domiora;"

# Nettoyage des données obsolètes
python manage.py cleanup_old_data --days 90
```

#### Maintenance des fichiers statiques

```bash
# Nettoyage des fichiers statiques obsolètes
find staticfiles/ -type f -mtime +365 -delete

# Optimisation des images
python manage.py optimize_images
```

### 5.3.4 Gestion des incidents

#### Procédure en cas d'arrêt de service

**1. Diagnostic rapide**
```bash
# Vérifier l'état des services
sudo systemctl status domiora domiora-celery nginx redis postgresql

# Vérifier l'espace disque
df -h

# Vérifier la mémoire
free -h

# Vérifier les processus
ps aux | grep gunicorn
```

**2. Actions correctives**
```bash
# Redémarrer les services si nécessaire
sudo systemctl restart domiora
sudo systemctl restart domiora-celery
sudo systemctl restart nginx

# Vérifier les logs pour identifier la cause
sudo journalctl -u domiora -n 50
```

**3. Communication**
- Informer les utilisateurs si l'incident dure plus de 15 minutes
- Mettre à jour le statut sur les réseaux sociaux
- Documenter l'incident pour analyse post-mortem

#### Scénarios d'incidents courants

**Base de données inaccessible**
```bash
# Vérifier PostgreSQL
sudo systemctl status postgresql

# Redémarrer PostgreSQL
sudo systemctl restart postgresql

# Vérifier la connexion
psql -U domiora -d domiora -c "SELECT 1;"
```

**Espace disque insuffisant**
```bash
# Identifier les fichiers volumineux
du -h /chemin/vers/domiora/media | sort -h | tail -20

# Nettoyer les anciens médias
find /chemin/vers/domiora/media -name "*.jpg" -mtime +365 -delete

# Nettoyer les logs
sudo journalctl --vacuum-time=30d
```

**Performance dégradée**
```bash
# Vérifier la charge système
top
htop

# Vérifier les connexions actives
netstat -an | grep :443 | wc -l

# Optimiser la base de données
sudo -u postgres psql -d domiora -c "VACUUM ANALYZE;"
```

### 5.3.5 Sécurité opérationnelle

#### Mises à jour de sécurité

```bash
# Mises à jour système
sudo apt update && sudo apt upgrade -y

# Mises à jour des dépendances Python
pip list --outdated
pip install --upgrade <package_name>
```

#### Gestion des permissions

```bash
# Vérifier les permissions des fichiers sensibles
ls -la .env
chmod 600 .env

# Vérifier les permissions des répertoires
chmod 755 /chemin/vers/domiora
chmod 755 /chemin/vers/domiora/media
```

#### Audit de sécurité

```bash
# Scanner les vulnérabilités des dépendances
pip install safety
safety check

# Vérifier les clés API exposées
grep -r "api_key" --exclude-dir=venv --exclude-dir=.git .
```

### 5.3.6 Documentation et support

#### Documentation opérationnelle

Maintenir à jour :
- Procédures d'urgence
- Contacts des fournisseurs (AWS, n8n, Cloudinary)
- Configurations système
- Historique des modifications

#### Support technique

**Contacts internes :**
- Administrateur système : admin@domiora.com
- Développeur principal : dev@domiora.com

**Contacts externes :**
- Support AWS : +1-800-554-7701
- Support n8n : support@n8n.io
- Support Cloudinary : support@cloudinary.com

#### Formation des utilisateurs

Organiser des sessions de formation pour :
- Utilisation de l'interface d'administration
- Gestion des incidents
- Procédures de sauvegarde
- Surveillance et monitoring

---

## Résumé du chapitre

Ce chapitre a présenté les guides complets de déploiement et d'exploitation de la plateforme DOMIORA :

**Configurations matérielles et logicielles** : Nous avons défini les configurations minimales et recommandées pour le développement et la production, incluant les spécifications matérielles, la stack technique complète, et les services externes requis.

**Guide de déploiement** : Une procédure détaillée a été fournie pour la mise en production, depuis la préparation de l'environnement jusqu'à la vérification finale, incluant la configuration de la base de données, des services web, de la sécurité SSL, et des tâches asynchrones.

**Guide d'exploitation** : Les procédures de surveillance, maintenance, sauvegarde, et gestion des incidents ont été documentées pour assurer le bon fonctionnement continu de la plateforme en production.

Ces guides permettent un déploiement structuré et une exploitation professionnelle de DOMIORA, garantissant la fiabilité, la sécurité et la performance de la plateforme immobilière.