import random
from datetime import timedelta, datetime

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction as db_transaction

from accounts.models import User
from agents.models import Agent, Specialty, AgentReview
from properties.models import Property, Amenity
from favorites.models import Favorite
from rental_requests.models import PropertyRequest
from transactions.models import Transaction
from notifications.models import Notification
from site_settings.models import SiteSettings
from core.models import Testimonial
from messaging.models import Conversation, Message
from appointments.models import Appointment


AMENITIES = [
    "Piscine", "Parking privé", "Climatisation", "Ascenseur", "Sécurité 24/7",
    "Salle de sport", "Balcon", "Jardin privatif", "Cheminée", "Vue panoramique",
    "Cuisine équipée", "Wifi haut débit", "Terrasse sur le toit", "Buanderie",
    "Système domotique", "Cave à vin", "Dressing", "Garage double",
]

SPECIALTIES = ["Résidentiel", "Luxe", "Investissement", "Location", "Vente", "Neuf", "Commercial", "Rénovation & estimation", "Gestion de location", "Vente en VEFA"]

# city -> (country, lat, lng)
CITIES = {
    "Brooklyn": ("US", 40.6782, -73.9442),
    "New York City": ("US", 40.7128, -74.0060),
    "Henderson": ("US", 36.0395, -114.9817),
    "Bronx": ("US", 40.8448, -73.8648),
    "Las Vegas": ("US", 36.1699, -115.1398),
    "Hoboken": ("US", 40.7440, -74.0324),
    "Beverly Hills": ("US", 34.0736, -118.4004),
    "Westport": ("US", 41.1415, -73.3579),
    "Queens": ("US", 40.7282, -73.7949),
    "Dallas": ("US", 32.7767, -96.7970),
    "Jersey City": ("US", 40.7178, -74.0431),
    "Naples": ("US", 26.1420, -81.7948),
    "Paris": ("FR", 48.8566, 2.3522),
    "Lyon": ("FR", 45.7640, 4.8357),
    "Lomé": ("TG", 6.1725, 1.2314),
}

STREET_NAMES = [
    "India Street", "Emerald Valley Drive", "North 7th Street", "Decatur Street",
    "Hudson Street", "Carla Ridge", "Central Park West", "Beachside Avenue",
    "Grove Street", "Uptown Lane", "Waterfront Loft", "Battery Park Vista",
    "Golf & Beach Club Drive", "Tribeca Terrace", "High Roller Sky Suite",
    "Third Avenue", "Long Island City Tower", "Skyline Boulevard",
]

TYPE_CATALOG = {
    "studio": {
        "titles": ["Studio lumineux au cœur de la ville", "Studio moderne meublé", "Studio cosy proche des commerces"],
        "images": [
            "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=1200&q=80",
            "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=1200&q=80",
            "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=1200&q=80",
            "https://images.unsplash.com/photo-1554995207-c18c203602cb?w=1200&q=80",
        ],
    },
    "villa": {
        "titles": ["Villa moderne avec piscine privée", "Villa de luxe avec jardin paysager", "Villa contemporaine vue mer"],
        "images": [
            "https://images.unsplash.com/photo-1613977257363-707ba9348227?w=1200&q=80",
            "https://images.unsplash.com/photo-1613490493576-7fde63acd811?w=1200&q=80",
            "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=1200&q=80",
            "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=1200&q=80",
            "https://images.unsplash.com/photo-1505843513577-22bb7d21e455?w=1200&q=80",
        ],
    },
    "penthouse": {
        "titles": ["Penthouse panoramique avec terrasse", "Penthouse de standing vue skyline", "Penthouse design dernier étage"],
        "images": [
            "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=1200&q=80",
            "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=1200&q=80",
            "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?w=1200&q=80",
            "https://images.unsplash.com/photo-1582268611958-ebfd161ef9cf?w=1200&q=80",
        ],
    },
    "maison_de_ville": {
        "titles": ["Maison de ville familiale", "Maison de ville rénovée avec charme", "Maison de ville sur 3 niveaux"],
        "images": [
            "https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=1200&q=80",
            "https://images.unsplash.com/photo-1572120360610-d971b9d7767c?w=1200&q=80",
            "https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=1200&q=80",
            "https://images.unsplash.com/photo-1605276373954-0c4a0dac5b12?w=1200&q=80",
        ],
    },
    "commercial": {
        "titles": ["Local commercial bien situé", "Espace commercial à fort passage", "Local commercial rénové"],
        "images": [
            "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1200&q=80",
            "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=1200&q=80",
            "https://images.unsplash.com/photo-1556761175-5973dc0f32e7?w=1200&q=80",
        ],
    },
    "terrain": {
        "titles": ["Terrain constructible bien exposé", "Terrain viabilisé proche commodités", "Grand terrain arboré"],
        "images": ["https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=1200&q=80"],
    },
    "ferme": {
        "titles": ["Ferme rénovée avec dépendances", "Ferme paisible en pleine campagne", "Ferme avec grange aménageable"],
        "images": [
            "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=1200&q=80",
            "https://images.unsplash.com/photo-1505691938895-1758d7feb511?w=1200&q=80",
            "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?w=1200&q=80",
        ],
    },
    "cottage": {
        "titles": ["Cottage paisible en périphérie", "Cottage chaleureux en bord de forêt", "Cottage rénové avec jardin"],
        "images": [
            "https://images.unsplash.com/photo-1449844908441-8829872d2607?w=1200&q=80",
            "https://images.unsplash.com/photo-1518780664697-55e3ad937233?w=1200&q=80",
            "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?w=1200&q=80",
        ],
    },
    "loft": {
        "titles": ["Loft industriel rénové", "Loft créatif dans ancien entrepôt", "Loft new-yorkais authentique"],
        "images": [
            "https://images.unsplash.com/photo-1502005229762-cf1b2da7c5d6?w=1200&q=80",
            "https://images.unsplash.com/photo-1560185007-c5ca9d2c014d?w=1200&q=80",
            "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=1200&q=80",
            "https://images.unsplash.com/photo-1556228453-efd6c1ff04f6?w=1200&q=80",
        ],
    },
    "duplex": {
        "titles": ["Duplex contemporain avec vue", "Duplex lumineux sur deux niveaux", "Duplex rénové avec terrasse"],
        "images": [
            "https://images.unsplash.com/photo-1484154218962-a197022b5858?w=1200&q=80",
            "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=1200&q=80",
            "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=1200&q=80",
        ],
    },
    "triplex": {
        "titles": ["Triplex de standing", "Triplex familial spacieux", "Triplex avec rooftop privé"],
        "images": [
            "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=1200&q=80",
            "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=1200&q=80",
            "https://images.unsplash.com/photo-1484154218962-a197022b5858?w=1200&q=80",
        ],
    },
    "ranch": {
        "titles": ["Ranch spacieux avec terrain", "Ranch authentique rénové", "Ranch avec écuries"],
        "images": [
            "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=1200&q=80",
            "https://images.unsplash.com/photo-1505691938895-1758d7feb511?w=1200&q=80",
            "https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=1200&q=80",
        ],
    },
    "mobile_home": {
        "titles": ["Mobile home tout équipé", "Mobile home proche plage", "Mobile home récent"],
        "images": [
            "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?w=1200&q=80",
            "https://images.unsplash.com/photo-1449844908441-8829872d2607?w=1200&q=80",
        ],
    },
    "copropriete": {
        "titles": ["Appartement en copropriété sécurisée", "Copropriété avec services hôteliers", "Copropriété calme et arborée"],
        "images": [
            "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=1200&q=80",
            "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=1200&q=80",
            "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=1200&q=80",
        ],
    },
    "bungalow": {
        "titles": ["Bungalow chaleureux en bord de mer", "Bungalow de plain-pied rénové", "Bungalow avec véranda"],
        "images": [
            "https://images.unsplash.com/photo-1449844908441-8829872d2607?w=1200&q=80",
            "https://images.unsplash.com/photo-1518780664697-55e3ad937233?w=1200&q=80",
            "https://images.unsplash.com/photo-1505691938895-1758d7feb511?w=1200&q=80",
        ],
    },
    "chateau": {
        "titles": ["Château historique restauré", "Château avec parc arboré", "Château de caractère"],
        "images": [
            "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=1200&q=80",
            "https://images.unsplash.com/photo-1505843513577-22bb7d21e455?w=1200&q=80",
            "https://images.unsplash.com/photo-1613977257363-707ba9348227?w=1200&q=80",
        ],
    },
    "appartement": {
        "titles": ["Appartement cosy proche des commerces", "Appartement lumineux entièrement rénové", "Appartement vue sur Manhattan", "Appartement familial avec balcon"],
        "images": [
            "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=1200&q=80",
            "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=1200&q=80",
            "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=1200&q=80",
            "https://images.unsplash.com/photo-1484154218962-a197022b5858?w=1200&q=80",
            "https://images.unsplash.com/photo-1484101403633-562f891dc89a?w=1200&q=80",
        ],
    },
}

FIRST_NAMES_AGENTS = ["Sophie", "Thomas", "Marie", "Lucas", "Camille", "Hugo", "Eben-Ezer", "Peniel", "Claire", "Antoine",
                      "Léa", "Romain", "Inès", "Maxime", "Nora", "Julien", "Amandine", "Bastien", "Chloé", "David"]
LAST_NAMES_AGENTS = ["Martin", "Dubois", "Laurent", "Bernard", "Petit", "Moreau", "SISSOU", "LOLIVIER", "Girard", "Rousseau",
                     "Fontaine", "Lefevre", "Mercier", "Blanc", "Garnier", "Faure", "Rolland", "Henry", "Caron", "Perrin"]

FIRST_NAMES_BUYERS = ["Julie", "Antoine", "Claire", "Nicolas", "Emma", "Maxime", "Léa", "Paul", "Chloé", "Romain",
                      "Manon", "Hugo", "Camille", "Lucas", "Sarah", "Adam", "Inès", "Louis", "Jade", "Ethan",
                      "Lina", "Noah", "Anna", "Gabriel", "Zoe", "Tom", "Lucie", "Nathan", "Eva", "Théo",
                      "Mathilde", "Arthur", "Louise", "Raphaël", "Alice", "Victor", "Margaux", "Léo", "Juliette", "Sacha",
                      "Charlotte", "Mathis", "Élise", "Enzo", "Pauline", "Yanis", "Camélia", "Aaron", "Roxane", "Imran"]
LAST_NAMES_BUYERS = ["Girard", "Roux", "Fontaine", "Lefevre", "Mercier", "Blanc", "Garnier", "Faure", "Rolland", "Henry",
                     "Caron", "Perrin", "Morin", "Marchand", "Dumont", "Lambert", "Bonnet", "François", "Gauthier", "Aubert",
                     "Robin", "Schmitt", "Renard", "Masson", "Vidal", "Riviere", "Brun", "Dupuis", "Joly", "Picard",
                     "Lemoine", "Meunier", "Boyer", "Guerin", "Muller", "Le Roy", "Charpentier", "Roger", "Renaud", "Roussel",
                     "Colin", "Vasseur", "Noel", "Nicolas", "Aubry", "Hubert", "Dupont", "Leroux", "Barbier", "Arnaud"]

TESTIMONIALS = [
    {"name": "Sarah Martin", "role": "Acheteuse · Paris", "content": "Une expérience exceptionnelle ! L'équipe m'a aidé à trouver la maison parfaite pour ma famille. Service professionnel et très attentif.", "rating": 5},
    {"name": "Thomas Dubois", "role": "Investisseur · Lyon", "content": "Processus d'achat fluide et transparent. Les agents sont compétents et réactifs. Je recommande vivement à tous ceux qui cherchent un bien !", "rating": 5},
    {"name": "Marie Laurent", "role": "Locataire · Bordeaux", "content": "Plateforme intuitive et catalogue impressionnant. J'ai trouvé mon appartement de rêve en quelques semaines seulement. Merci à toute l'équipe.", "rating": 4},
    {"name": "Karim Benali", "role": "Acheteur · Lomé", "content": "L'assistant et le comparateur m'ont fait gagner un temps fou. J'ai pu visiter, comparer et signer en moins d'un mois.", "rating": 5},
    {"name": "Élodie Faure", "role": "Investisseuse · Marseille", "content": "Le dashboard agent est très complet pour suivre mes biens et mes revenus. Une vraie plateforme professionnelle.", "rating": 5},
]

REVIEW_COMMENTS = [
    "Agent très réactif et de bon conseil tout au long du processus.",
    "Excellente connaissance du marché local, je recommande !",
    "Communication fluide, visites bien organisées.",
    "A su comprendre exactement ce que je cherchais.",
    "Professionnel, ponctuel et transparent sur les prix.",
    "Process un peu long mais résultat à la hauteur.",
]


class Command(BaseCommand):
    help = "Seed the database with rich, consistent demo data for DOMIORA"

    def add_arguments(self, parser):
        parser.add_argument("--properties", type=int, default=120)
        parser.add_argument("--agents", type=int, default=20)
        parser.add_argument("--buyers", type=int, default=50)

    @db_transaction.atomic
    def handle(self, *args, **options):
        n_properties = options["properties"]
        n_agents = min(options["agents"], len(FIRST_NAMES_AGENTS))
        n_buyers = min(options["buyers"], len(FIRST_NAMES_BUYERS))

        self.stdout.write("Seeding DOMIORA demo data (v2 - rich & consistent)...")

        settings_obj = SiteSettings.load()
        settings_obj.site_name = "DOMIORA"
        settings_obj.tagline = "Find. Rent. Own. Effortlessly."
        settings_obj.contact_email = "contact@domiora.com"
        settings_obj.contact_phone = "+1 (212) 000-0001"
        settings_obj.address = "157 West 57th Street, New York, NY 10019"
        settings_obj.opening_hours_weekdays = "Lun - Ven: 9h - 18h"
        settings_obj.opening_hours_weekend = "Sam: 10h - 16h"
        settings_obj.save()

        amenities = [Amenity.objects.get_or_create(name=name)[0] for name in AMENITIES]
        specialties = [Specialty.objects.get_or_create(name=name)[0] for name in SPECIALTIES]

        if not User.objects.filter(username="admin").exists():
            admin = User.objects.create_superuser(
                username="admin", email="admin@domiora.com", password="Admin1234!",
                first_name="Admin", last_name="DOMIORA",
            )
            admin.role = User.Role.ADMIN
            admin.save()
            self.stdout.write(self.style.SUCCESS("Created admin user: admin / Admin1234!"))

        agents = []
        for i in range(n_agents):
            first, last = FIRST_NAMES_AGENTS[i], LAST_NAMES_AGENTS[i]
            username = f"agent_{first.lower().replace('-', '')}"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@domiora.com", "first_name": first, "last_name": last,
                    "role": User.Role.AGENT, "phone": f"+1-212-000-{1000+i}",
                },
            )
            if created:
                user.set_password("Agent1234!")
                user.save()
            agent, _ = Agent.objects.get_or_create(
                user=user,
                defaults={
                    "agency_name": random.choice(["Mitchell Realty Group", "Eco Bank Solutions", "Media Contact Realty", "DOMIORA Premium", "Urban Nest Realty", "Skyline Properties"]),
                    "license_number": f"YTH-23-{2000+i}-UYTEGS",
                    "bio": "Agent immobilier passionné, accompagnant ses clients à chaque étape de leur projet avec expertise et transparence.",
                    "commission_rate": random.choice([3.0, 4.0, 5.0, 6.0]),
                    "years_experience": random.choice([1, 2, 5, 8, 12, 15, 20]),
                    "rating": round(random.uniform(4.0, 5.0), 1),
                    "is_verified": random.random() > 0.15,
                    "response_time_hours": random.choice([2, 6, 12, 24]),
                },
            )
            agent.specialties.set(random.sample(specialties, 3))
            agents.append(agent)

        buyers = []
        for i in range(n_buyers):
            first, last = FIRST_NAMES_BUYERS[i], LAST_NAMES_BUYERS[i]
            username = f"buyer_{first.lower().replace('é','e').replace('è','e')}"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.com", "first_name": first, "last_name": last,
                    "role": User.Role.BUYER, "phone": f"+1-212-000-{2000+i}",
                },
            )
            if created:
                user.set_password("Buyer1234!")
                user.save()
            buyers.append(user)

        transaction_types = ["vente", "vente", "vente", "location"]
        property_types = list(TYPE_CATALOG.keys())
        properties = []
        for i in range(n_properties):
            ptype = random.choice(property_types)
            catalog = TYPE_CATALOG[ptype]
            title = random.choice(catalog["titles"])
            city = random.choice(list(CITIES.keys()))
            country, lat, lng = CITIES[city]
            transaction_type = random.choice(transaction_types)
            bedrooms = 0 if ptype in ("terrain", "commercial") else random.randint(1, 6)
            bathrooms = 0 if ptype in ("terrain",) else random.randint(1, 5)
            surface = random.choice([45, 60, 85, 120, 180, 250, 320, 450, 600, 900, 1500, 2900, 4100])
            status = random.choices(["disponible", "vendu", "loue"], weights=[68, 22, 10])[0]

            if transaction_type == "location":
                price = random.choice([1290, 1899, 2100, 2500, 2900, 3200, 3400, 3895, 4600, 5200])
                status = "loue" if status == "vendu" else status
            else:
                price = random.choice([180000, 295000, 450000, 899000, 1290000, 1899000, 2295000, 2499000, 3895000, 5490000, 9800000, 24950000])

            jitter_lat = lat + random.uniform(-0.03, 0.03)
            jitter_lng = lng + random.uniform(-0.03, 0.03)

            available_images = catalog["images"]
            sample_size = min(len(available_images), random.choice([2, 3, len(available_images)]))

            prop = Property.objects.create(
                agent=random.choice(agents),
                title=f"{title} #{i+1}",
                description=(
                    f"Un {title.lower()} d'exception offrant un cadre de vie raffiné, alliant confort moderne et "
                    "emplacement privilégié. Idéal pour une famille ou un investisseur à la recherche "
                    "d'une propriété de qualité, proche des commodités et des transports."
                ),
                property_type=ptype,
                transaction_type=transaction_type,
                price=price,
                currency="USD",
                country=country,
                city=city,
                address=f"{random.randint(10,3999)} {random.choice(STREET_NAMES)}",
                latitude=round(jitter_lat, 6),
                longitude=round(jitter_lng, 6),
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                surface_area=surface,
                floors=random.randint(1, 4),
                year_built=random.randint(1995, 2024),
                status=status,
                is_featured=(i < 8),
                is_exclusive=(random.random() < 0.12),
                is_published=True,
                is_validated=(i % 11 != 0),
                views_count=random.randint(5, 800),
                stock_image_urls=random.sample(available_images, k=sample_size),
                virtual_tour_url="https://www.youtube.com/embed/dQw4w9WgXcQ" if random.random() < 0.08 else "",
            )
            prop.amenities.set(random.sample(amenities, random.randint(3, 7)))
            properties.append(prop)

        self.stdout.write(self.style.SUCCESS(f"Created {len(properties)} properties (title/type/images consistent)"))

        for buyer in buyers:
            for prop in random.sample(properties, min(random.randint(1, 6), len(properties))):
                Favorite.objects.get_or_create(user=buyer, property=prop)

        request_types = ["visite", "location", "achat"]
        for _ in range(70):
            buyer = random.choice(buyers)
            prop = random.choice(properties)
            PropertyRequest.objects.get_or_create(
                user=buyer, property=prop,
                defaults={
                    "agent": prop.agent,
                    "request_type": random.choice(request_types),
                    "message": "Bonjour, je suis intéressé(e) par ce bien, serait-il possible d'organiser une visite ?",
                    "status": random.choices(["en_attente", "acceptee", "rejetee"], weights=[50, 35, 15])[0],
                },
            )

        sold_or_rented = [p for p in properties if p.status in ("vendu", "loue")]
        for prop in sold_or_rented:
            amount = prop.price
            commission_rate = prop.agent.commission_rate if prop.agent else 5
            Transaction.objects.get_or_create(
                property=prop,
                defaults={
                    "agent": prop.agent,
                    "client": random.choice(buyers),
                    "transaction_type": "location" if prop.status == "loue" else "vente",
                    "amount": amount,
                    "commission_amount": round(float(amount) * float(commission_rate) / 100, 2),
                    "status": "terminee",
                    "transaction_date": timezone.now().date() - timedelta(days=random.randint(1, 300)),
                },
            )

        for agent in agents:
            reviewers = random.sample(buyers, min(random.randint(2, 8), len(buyers)))
            for buyer in reviewers:
                AgentReview.objects.get_or_create(
                    agent=agent, user=buyer,
                    defaults={"rating": random.choices([5, 4, 3], weights=[60, 30, 10])[0], "comment": random.choice(REVIEW_COMMENTS)},
                )

        for _ in range(30):
            buyer = random.choice(buyers)
            prop = random.choice(properties)
            Appointment.objects.create(
                user=buyer, agent=prop.agent, property=prop,
                scheduled_at=timezone.now() + timedelta(days=random.randint(-10, 20), hours=random.randint(8, 18)),
                status=random.choices(["en_attente", "confirme", "annule", "termine"], weights=[35, 35, 10, 20])[0],
                notes="Disponible en journée de préférence.",
            )

        for _ in range(25):
            buyer = random.choice(buyers)
            prop = random.choice(properties)
            conversation, _ = Conversation.objects.get_or_create(buyer=buyer, agent=prop.agent, property=prop)
            if not conversation.messages.exists():
                Message.objects.create(conversation=conversation, sender=buyer, body=f"Bonjour, je suis intéressé(e) par « {prop.title} ». Est-il encore disponible ?")
                if random.random() > 0.3:
                    Message.objects.create(conversation=conversation, sender=prop.agent.user, body="Bonjour ! Oui, le bien est toujours disponible. Souhaitez-vous organiser une visite ?")
                if random.random() > 0.6:
                    Message.objects.create(conversation=conversation, sender=buyer, body="Avec plaisir, quelles sont vos disponibilités cette semaine ?")

        for buyer in buyers[:15]:
            Notification.objects.get_or_create(
                user=buyer, title="Bienvenue sur DOMIORA",
                defaults={"message": "Découvrez notre sélection exclusive de biens immobiliers.", "notification_type": "systeme"},
            )

        for t in TESTIMONIALS:
            Testimonial.objects.get_or_create(name=t["name"], defaults=t)

        self.stdout.write(self.style.SUCCESS("DOMIORA demo data seeded successfully!"))
        self.stdout.write(f"-> {len(agents)} agents, {len(buyers)} buyers, {len(properties)} properties")
        self.stdout.write("Admin login -> username: admin / password: Admin1234!")
        self.stdout.write("Agent login -> username: agent_sophie / password: Agent1234!")
        self.stdout.write("Buyer login -> username: buyer_julie / password: Buyer1234!")
