# Nouvelles Fonctionnalités - Guide d'Implémentation

## Vue d'ensemble

Quatre modules innovants ont été ajoutés à la plateforme DOMIORA pour enrichir l'expérience immobilière :

1. **Visites Virtuelles en Direct (WebRTC)**
2. **Visualisation AR de Mobilier 3D**
3. **Analyse et Estimation de Prix**
4. **Système de Boost d'Annonces**

---

## 1. Visites Virtuelles en Direct (WebRTC)

### Modèles de Données

**VirtualTourSession**
- Sessions WebRTC pour visites virtuelles
- Statuts: programmée, en cours, terminée, annulée
- Options: partage d'écran, audio, vidéo, chat
- Enregistrement des sessions

**TourChatMessage**
- Messages de chat pendant les visites
- Horodatage et expéditeur

### Interface Frontend

**Fichier**: `templates/partials/webrtc_video_chat.html`

**Fonctionnalités**:
- Appel vidéo/audio bidirectionnel
- Partage d'écran
- Chat en temps réel
- Contrôles: mute audio, mute vidéo, partage écran
- Timer d'appel
- Indicateurs de statut de connexion

**Intégration**:
```html
{% include "partials/webrtc_video_chat.html" %}
```

### Infrastructure Requise (À Implémenter)

**Serveur de Signalisation WebSocket**:
- Nécessaire pour l'échange de signaux WebRTC
- Peut utiliser Django Channels ou un service externe (Pusher, Ably)
- Gestion des ICE candidates et SDP offers/answers

**Exemple avec Django Channels**:
```python
# routing.py
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path
from .consumers import WebRTCConsumer

websocket_urlpatterns = [
    path('ws/webrtc/<str:session_id>/', WebRTCConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    'websocket': URLRouter(websocket_urlpatterns),
})
```

---

## 2. Visualisation AR de Mobilier 3D

### Modèles de Données

**FurnitureModel**
- Modèles 3D de mobilier (GLB/GLTF)
- Catégories: salon, chambre, cuisine, bureau, etc.
- Dimensions en mètres
- Prix et métadonnées

**ARConfiguration**
- Configuration AR par propriété
- Dimensions des pièces
- Mobilier recommandé

### Interface Frontend

**Fichier**: `templates/partials/ar_furniture_viewer.html`

**Fonctionnalités**:
- Accès à la caméra de l'utilisateur
- Superposition de modèles 3D sur la vue caméra
- Sélection de mobilier depuis une bibliothèque
- Contrôles: rotation, échelle, suppression
- Affichage des dimensions et prix

**Intégration**:
```html
{% include "partials/ar_furniture_viewer.html" %}
```

### Améliorations Futures

- Intégration avec AR.js ou Three.js pour rendu 3D réel
- Détection de surface plane pour placement précis
- Bibliothèque de modèles 3D plus étendue
- Export de configurations AR

---

## 3. Analyse et Estimation de Prix

### Modèles de Données

**RecentSale**
- Ventes récentes pour comparaison
- Localisation, caractéristiques, prix
- Date de vente et source

**PriceEstimation**
- Estimation de valeur par propriété
- Fourchette de prix (min, max, moyenne)
- Comparaison avec prix de l'annonce
- Position sur le marché
- Score de confiance

**GeographicPriceAnalysis**
- Analyse par zone géographique
- Prix au m² (moyenne, min, max)
- Tendances du marché
- Activité du marché

### Interface Frontend

**Fichier**: `templates/partials/price_estimation_display.html`

**Fonctionnalités**:
- Affichage de la fourchette de prix estimée
- Indicateur de position sur le marché
- Barre de comparaison visuelle
- Liste des ventes comparables
- Analyse géographique
- Badge de prix équitable

**Intégration**:
```html
{% include "partials/price_estimation_display.html" %}
```

### Algorithme d'Estimation

**À implémenter dans `price_analysis/services.py`**:
```python
from django.db.models import Avg, Count
from .models import RecentSale, PriceEstimation, GeographicPriceAnalysis

def estimate_property_price(property):
    """Estime le prix d'une propriété basé sur les ventes comparables"""
    
    # Récupérer les ventes comparables
    comparable_sales = RecentSale.objects.filter(
        city=property.city,
        neighborhood=property.neighborhood,
        property_type=property.property_type,
        transaction_type=property.transaction_type,
        sale_date__gte=timezone.now() - timedelta(days=365)
    ).annotate(
        price_per_sqm=F('sale_price') / F('surface_area')
    )
    
    if comparable_sales.count() < 3:
        return None  # Pas assez de données
    
    # Calculer les statistiques
    avg_price_per_sqm = comparable_sales.aggregate(
        avg=Avg('price_per_sqm')
    )['avg']
    
    # Ajuster selon les caractéristiques
    adjustment_factor = calculate_adjustment_factor(property, comparable_sales)
    
    estimated_price = property.surface_area * avg_price_per_sqm * adjustment_factor
    
    # Créer l'estimation
    estimation = PriceEstimation.objects.create(
        property=property,
        listing_price=property.price,
        estimated_min_price=estimated_price * 0.85,
        estimated_max_price=estimated_price * 1.15,
        estimated_avg_price=estimated_price,
        comparable_sales_count=comparable_sales.count(),
        confidence_score=min(100, comparable_sales.count() * 10)
    )
    
    estimation.calculate_price_difference()
    estimation.save()
    
    return estimation
```

---

## 4. Système de Boost d'Annonces

### Modèles de Données

**BoostPackage**
- Packages de boost disponibles
- Durée, prix, multiplicateur
- Fonctionnalités: vedette, top recherche, badge, support prioritaire

**PropertyBoost**
- Boost actif pour une propriété
- Statut, dates, paiement
- Métriques de performance
- Score de boost calculé

**BoostAnalytics**
- Analytics quotidiennes pour les boosts
- Vues, visiteurs, demandes, favoris
- Taux de conversion
- Comparaison avec période non boostée

### Interface Frontend

**Fichier**: `templates/partials/property_boost_manager.html`

**Fonctionnalités**:
- Affichage du boost actif avec progression
- Sélection de packages de boost
- Statistiques de performance
- Historique des boosts
- Interface d'achat

**Intégration**:
```html
{% include "partials/property_boost_manager.html" %}
```

### Algorithme de Boost

**Déjà implémenté dans `property_boost/models.py`**:
```python
def calculate_boost_score(self):
    """Calcule le score de boost basé sur le package et le temps restant"""
    if not self.is_active_boost():
        self.boost_score = 0
        return
    
    base_score = self.package.boost_multiplier * 100
    
    # Facteur temps restant
    time_remaining = (self.end_date - timezone.now()).total_seconds() / 86400
    time_factor = min(time_remaining / 30, 1) * 20
    
    # Fonctionnalités du package
    feature_score = 0
    if self.package.featured_placement:
        feature_score += 30
    if self.package.top_of_search:
        feature_score += 25
    if self.package.badge_highlight:
        feature_score += 15
    if self.package.priority_support:
        feature_score += 10
    
    self.boost_score = int(base_score + time_factor + feature_score)
    self.priority_level = min(self.boost_score // 50, 10)
    self.save(update_fields=['boost_score', 'priority_level'])
```

### Intégration dans la Recherche

**Modifier le queryset de recherche pour inclure les boosts**:
```python
# properties/views.py ou services.py
from property_boost.models import PropertyBoost

def search_properties(queryset):
    """Modifie le queryset pour tenir compte des boosts"""
    
    # Récupérer les boosts actifs
    active_boosts = PropertyBoost.objects.filter(
        status='active',
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    ).select_related('property')
    
    # Trier par score de boost puis par autres critères
    boosted_properties = [boost.property.id for boost in active_boosts]
    
    # Annoter avec le score de boost
    queryset = queryset.annotate(
        boost_score=Case(
            When(id__in=boosted_properties, then=Value(1000)),
            default=Value(0),
            output_field=IntegerField()
        )
    ).order_by('-boost_score', '-created_at')
    
    return queryset
```

---

## Intégration dans les Pages Existantes

### Page de Détail de Propriété

**Ajouter dans `templates/properties/detail.html`**:
```html
<!-- Après la galerie d'images -->
{% include "partials/price_estimation_display.html" %}

<!-- Section AR -->
{% if property.ar_config.enable_ar %}
<div class="mt-6">
  <h3 class="text-lg font-bold text-gray-900 mb-4">Visualisation AR</h3>
  {% include "partials/ar_furniture_viewer.html" %}
</div>
{% endif %}

<!-- Section Visite Virtuelle -->
{% if property.virtual_tours.exists %}
<div class="mt-6">
  <h3 class="text-lg font-bold text-gray-900 mb-4">Visite Virtuelle en Direct</h3>
  {% include "partials/webrtc_video_chat.html" %}
</div>
{% endif %}
```

### Dashboard Propriétaire

**Ajouter dans `templates/dashboard/owner/property_detail.html`**:
```html
<!-- Section Boost -->
<div class="mt-6">
  <h3 class="text-lg font-bold text-gray-900 mb-4">Booster la visibilité</h3>
  {% include "partials/property_boost_manager.html" %}
</div>
```

---

## Configuration Admin

### Enregistrer les nouveaux modèles dans l'admin

**`virtual_tours/admin.py`**:
```python
from django.contrib import admin
from .models import VirtualTourSession, TourChatMessage

@admin.register(VirtualTourSession)
class VirtualTourSessionAdmin(admin.ModelAdmin):
    list_display = ['property', 'agent', 'buyer', 'status', 'scheduled_at']
    list_filter = ['status', 'scheduled_at']
    search_fields = ['property__title', 'agent__username']

@admin.register(TourChatMessage)
class TourChatMessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'sender', 'timestamp']
    list_filter = ['timestamp']
```

**`ar_furniture/admin.py`**:
```python
from django.contrib import admin
from .models import FurnitureModel, ARConfiguration

@admin.register(FurnitureModel)
class FurnitureModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'is_active']
    list_filter = ['category', 'is_active']

@admin.register(ARConfiguration)
class ARConfigurationAdmin(admin.ModelAdmin):
    list_display = ['property', 'enable_ar']
```

**`price_analysis/admin.py`**:
```python
from django.contrib import admin
from .models import RecentSale, PriceEstimation, GeographicPriceAnalysis

@admin.register(RecentSale)
class RecentSaleAdmin(admin.ModelAdmin):
    list_display = ['city', 'neighborhood', 'sale_price', 'sale_date']
    list_filter = ['city', 'sale_date']

@admin.register(PriceEstimation)
class PriceEstimationAdmin(admin.ModelAdmin):
    list_display = ['property', 'estimated_avg_price', 'market_position']
    list_filter = ['market_position', 'analysis_date']

@admin.register(GeographicPriceAnalysis)
class GeographicPriceAnalysisAdmin(admin.ModelAdmin):
    list_display = ['city', 'neighborhood', 'avg_price_per_sqm', 'price_trend']
    list_filter = ['city', 'price_trend']
```

**`property_boost/admin.py`**:
```python
from django.contrib import admin
from .models import BoostPackage, PropertyBoost, BoostAnalytics

@admin.register(BoostPackage)
class BoostPackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'duration_days', 'price', 'boost_multiplier']
    list_filter = ['duration_days']

@admin.register(PropertyBoost)
class PropertyBoostAdmin(admin.ModelAdmin):
    list_display = ['property', 'package', 'status', 'start_date', 'end_date']
    list_filter = ['status', 'start_date']

@admin.register(BoostAnalytics)
class BoostAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['boost', 'date', 'views', 'inquiries']
    list_filter = ['date']
```

---

## URL Patterns

**`virtual_tours/urls.py`**:
```python
from django.urls import path
from . import views

urlpatterns = [
    path('schedule/<int:property_id>/', views.schedule_tour, name='schedule'),
    path('session/<str:session_id>/', views.tour_session, name='session'),
    path('api/signal/<str:session_id>/', views.webrtc_signal, name='signal'),
]
```

**`ar_furniture/urls.py`**:
```python
from django.urls import path
from . import views

urlpatterns = [
    path('furniture/', views.furniture_list, name='furniture_list'),
    path('furniture/<int:furniture_id>/', views.furniture_detail, name='furniture_detail'),
]
```

**`price_analysis/urls.py`**:
```python
from django.urls import path
from . import views

urlpatterns = [
    path('estimate/<int:property_id>/', views.estimate_price, name='estimate'),
    path('analysis/<str:city>/', views.geographic_analysis, name='geo_analysis'),
]
```

**`property_boost/urls.py`**:
```python
from django.urls import path
from . import views

urlpatterns = [
    path('packages/', views.boost_packages, name='packages'),
    path('purchase/<int:property_id>/', views.purchase_boost, name='purchase'),
    path('analytics/<int:boost_id>/', views.boost_analytics, name='analytics'),
]
```

---

## Tests Recommandés

### Tests Unitaires

```python
# tests/test_price_analysis.py
from django.test import TestCase
from price_analysis.models import RecentSale, PriceEstimation
from properties.models import Property

class PriceEstimationTest(TestCase):
    def test_price_estimation_calculation(self):
        # Créer des ventes comparables
        RecentSale.objects.create(
            city='Lomé',
            property_type='appartement',
            sale_price=150000000,
            surface_area=100,
            sale_date='2024-01-01'
        )
        
        # Tester l'estimation
        property = Property.objects.create(
            title='Test',
            city='Lomé',
            property_type='appartement',
            surface_area=100,
            price=160000000
        )
        
        estimation = estimate_property_price(property)
        self.assertIsNotNone(estimation)
        self.assertEqual(estimation.market_position, 'at_market')
```

### Tests d'Intégration

```python
# tests/test_webrtc.py
from django.test import TestCase
from virtual_tours.models import VirtualTourSession

class WebRTCTest(TestCase):
    def test_session_creation(self):
        session = VirtualTourSession.objects.create(
            property=self.property,
            agent=self.agent,
            scheduled_at=timezone.now() + timedelta(days=1)
        )
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.status, 'scheduled')
```

---

## Déploiement

### Configuration Production

1. **WebRTC**: Utiliser un serveur STUN/TURN dédié (ex: Twilio, coturn)
2. **AR**: Héberger les modèles 3D sur CDN pour chargement rapide
3. **Price Analysis**: Configurer des tâches cron pour mettre à jour les analyses
4. **Boost**: Intégrer avec passerelle de paiement (CinetPay existante)

### Permissions

Ajouter les permissions nécessaires dans `settings.py`:
```python
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'

# Pour l'accès caméra (HTTPS requis en production)
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

---

## Maintenance

### Tâches Planifiées

```python
# management/commands/update_price_analysis.py
from django.core.management.base import BaseCommand
from price_analysis.services import update_geographic_analysis

class Command(BaseCommand):
    def handle(self, *args, **options):
        update_geographic_analysis()
        self.stdout.write('Price analysis updated')
```

**Cron job**:
```
0 2 * * * python manage.py update_price_analysis
```

---

## Support et Documentation

Pour toute question ou problème, consultez:
- Documentation Django: https://docs.djangoproject.com/
- WebRTC API: https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API
- AR.js: https://ar-js-org.github.io/AR.js-Doc/
- Three.js: https://threejs.org/docs/

---

## Résumé

Les quatre modules sont maintenant intégrés de manière modulaire dans la plateforme DOMIORA. Chaque module peut être utilisé indépendamment ou en combinaison avec les autres. L'architecture actuelle est préservée et les nouvelles fonctionnalités s'intègrent harmonieusement avec le design existant.
