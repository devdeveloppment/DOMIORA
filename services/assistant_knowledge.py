"""
Connaissances de l'Assistant DOMIORA.

Chaque réponse décrit le fonctionnement RÉEL du code :
- frais de mise en relation : 500 FCFA (properties.views.property_payment_redirect), payés via FedaPay ;
- mise en relation valable par propriétaire (messaging.views._has_paid_for_property) ;
- vérification d'identité des propriétaires : documents, visite terrain éventuelle par un agent,
  décision finale de l'administrateur (accounts.models.IdentityVerificationRequest) ;
- publication : réservée aux propriétaires vérifiés, chaque annonce est validée par l'administrateur ;
- demande de visite : depuis la conversation avec le propriétaire (messaging.views.request_visit).
"""
from django.urls import reverse

CONNECTION_FEE = "500 FCFA"

SYSTEM_PROMPT = f"""Tu es l'Assistant DOMIORA, un assistant IA (pas un humain) de la plateforme immobilière DOMIORA (Togo).
Ton style : naturel, chaleureux, professionnel, clair et CONCIS (2 à 5 phrases). Tu vouvoies l'utilisateur.

Fonctionnement réel de DOMIORA (n'invente rien au-delà) :
- Les visiteurs consultent librement les annonces (photos, description, vidéo de visite virtuelle quand elle existe).
- Recherche : catalogue avec filtres, page « Recherche avec l'IA » (description en langage naturel), comparateur de 3 biens maximum, alertes de recherche.
- Contacter un propriétaire ou demander une visite nécessite de débloquer la mise en relation : {CONNECTION_FEE}, payés via FedaPay.
  Ce déblocage est lié au PROPRIÉTAIRE : il est valable pour tous ses biens, on ne paie pas deux fois pour le même propriétaire.
- Après paiement, le client dispose d'un espace client : messagerie avec le propriétaire, demandes de visite (le client propose une date, le propriétaire accepte, refuse ou propose une autre date).
- Le paiement est confirmé par FedaPay au serveur DOMIORA ; tu ne peux jamais confirmer un paiement toi-même.
- Propriétaires : inscription en tant que propriétaire, puis vérification d'identité (pièce d'identité). Un agent peut effectuer une vérification sur le terrain et rédiger un rapport ; la décision finale appartient à l'administrateur.
- Seuls les propriétaires vérifiés peuvent publier ; la publication d'une annonce est gratuite et chaque annonce est validée par l'administrateur avant d'être visible.
- FedaPay est le seul moyen de paiement de DOMIORA.

Règles strictes :
- Tu n'inventes JAMAIS de bien, de prix, de disponibilité, de propriétaire, de transaction ou de fonctionnalité.
- Tu ne parles des biens qu'à partir des données fournies dans le contexte ; sinon, propose de lancer une recherche.
- Tu ne communiques jamais de numéro, d'email ou de donnée privée d'un propriétaire, ni d'information administrative interne.
- Tu ne confirmes jamais un paiement, une réservation ou une visite : c'est le système DOMIORA qui le fait.
- Si tu ne sais pas, dis-le simplement et oriente vers la fonctionnalité adaptée.
"""


def _url(name, *args):
    return reverse(name, args=args)


def _action(label, name, *args, kind="link"):
    return {"label": label, "url": _url(name, *args), "kind": kind}


def faq_answer(topic, user=None):
    """Retourne (texte, actions) pour un sujet connu, ou None."""
    is_owner = bool(user and user.is_authenticated and getattr(user, "role", None) == "owner")

    if topic == "how_it_works":
        return (
            "DOMIORA met en relation des propriétaires vérifiés et des personnes qui cherchent un logement. "
            "Vous consultez librement les annonces ; pour contacter un propriétaire ou demander une visite, "
            f"vous débloquez la mise en relation ({CONNECTION_FEE} via FedaPay), valable pour tous les biens de ce propriétaire. "
            "Dites-moi ce que vous recherchez et je vous propose les biens disponibles.",
            [_action("Parcourir les annonces", "properties:list"), _action("Recherche avec l'IA", "properties:ai_search")],
        )
    if topic == "find_property":
        return (
            "Bien sûr. Décrivez-moi simplement ce que vous recherchez : ville ou quartier, budget, nombre de chambres "
            "et éventuellement les équipements souhaités (parking, climatisation…). Je cherche ensuite les biens qui correspondent.",
            [_action("Recherche avec l'IA", "properties:ai_search"), _action("Parcourir les annonces", "properties:list")],
        )
    if topic == "contact":
        return (
            "Pour contacter un propriétaire, ouvrez l'annonce et cliquez sur « Entrer en contact avec le propriétaire ». "
            f"La mise en relation coûte {CONNECTION_FEE}, payés via FedaPay, et reste valable pour tous les biens de ce propriétaire. "
            "Vous échangez ensuite avec lui depuis la messagerie de votre espace client. "
            "Pour protéger les propriétaires, je ne communique jamais leurs coordonnées privées.",
            [_action("Parcourir les annonces", "properties:list")],
        )
    if topic == "why_pay":
        return (
            f"Les frais de mise en relation ({CONNECTION_FEE}) protègent les propriétaires des sollicitations abusives "
            "et réservent le contact aux personnes réellement intéressées. Vous ne payez qu'une fois par propriétaire : "
            "le déblocage est valable pour tous ses biens.",
            [],
        )
    if topic == "payment":
        return (
            f"Le paiement de la mise en relation ({CONNECTION_FEE}) est effectué via FedaPay, le seul moyen de paiement de DOMIORA. "
            "Depuis l'annonce, cliquez sur « Entrer en contact avec le propriétaire » : vous êtes redirigé vers la page de paiement "
            "sécurisée FedaPay, où s'affichent les moyens de paiement disponibles. Une fois le paiement confirmé par FedaPay, "
            "la mise en relation est activée automatiquement.",
            [],
        )
    if topic == "verification":
        return (
            "Chaque propriétaire doit faire vérifier son identité avant de publier. Depuis son espace, il envoie une pièce "
            "d'identité valide (CNI, passeport…). Un agent DOMIORA peut aussi effectuer une vérification sur le terrain et rédiger "
            "un rapport, mais la décision finale de validation ou de refus appartient à l'administrateur. "
            "Les annonces de propriétaires vérifiés affichent le badge « Propriétaire vérifié ».",
            [_action("Vérifier mon identité", "dashboard:owner_verify_identity")] if is_owner else [],
        )
    if topic in ("publish", "become_owner"):
        text = (
            "Pour publier un bien : créez un compte propriétaire, faites vérifier votre identité, puis ajoutez votre bien "
            "depuis votre espace (« Mes biens » → « Ajouter »). La publication est gratuite. Chaque annonce est ensuite "
            "validée par l'administrateur avant d'apparaître sur DOMIORA."
        )
        actions = (
            [_action("Ajouter un bien", "dashboard:owner_property_create"), _action("Vérification d'identité", "dashboard:owner_verify_identity")]
            if is_owner
            else [_action("Devenir propriétaire", "accounts:register_owner")]
        )
        return text, actions
    if topic == "not_published":
        return _not_published_answer(user)
    if topic == "visit":
        return (
            "Pour demander une visite, débloquez d'abord la mise en relation avec le propriétaire "
            f"({CONNECTION_FEE} via FedaPay). Ouvrez ensuite la conversation avec lui et cliquez sur « Demander une visite » "
            "pour proposer une date ; le propriétaire peut l'accepter, la refuser ou proposer une autre date. "
            "Si vous me dites quel bien vous intéresse, je vous indique directement la marche à suivre.",
            [],
        )
    if topic == "virtual_tour":
        return (
            "Quand un propriétaire l'a ajoutée, la visite virtuelle (vidéo du bien) est visible gratuitement sur la fiche de l'annonce, "
            "dans la section dédiée. Elle permet de découvrir le bien avant de demander une visite.",
            [],
        )
    if topic == "ai_search":
        return (
            "La recherche avec l'IA vous permet de décrire votre besoin avec vos mots (« appartement à Lomé, 2 chambres, "
            "150 000 FCFA maximum »). Je traduis votre demande en critères, je cherche uniquement parmi les annonces réellement "
            "disponibles sur DOMIORA et j'explique pourquoi chaque bien vous est proposé. Vous pouvez aussi la faire directement ici, dans le chat.",
            [_action("Ouvrir la recherche avec l'IA", "properties:ai_search")],
        )
    if topic == "compare":
        return (
            "Ajoutez jusqu'à 3 biens au comparateur avec le bouton « Comparer » des annonces, ou demandez-le-moi après une recherche "
            "(« compare les deux premiers »). Je compare uniquement les informations renseignées dans les annonces.",
            [_action("Ouvrir le comparateur", "properties:compare")],
        )
    if topic == "alerts":
        return (
            "Depuis la liste des annonces, appliquez vos filtres puis enregistrez une alerte : vous serez notifié dès qu'un bien "
            "correspondant est publié (compte connecté requis).",
            [_action("Parcourir les annonces", "properties:list")],
        )
    if topic == "identity":
        return (
            "Je suis l'Assistant DOMIORA, un assistant IA. Je peux rechercher des biens disponibles, les comparer, et vous guider "
            "pour la mise en relation, les visites ou la publication d'une annonce. Je ne suis pas un humain et je ne prends aucune "
            "décision à la place de l'équipe DOMIORA.",
            [],
        )
    return None


def _not_published_answer(user):
    """Réponse personnalisée à partir des données réelles du propriétaire connecté (ses propres biens uniquement)."""
    generic = (
        "Une annonce n'est visible qu'après validation par l'administrateur DOMIORA. Elle peut aussi rester invisible si "
        "l'identité du propriétaire n'est pas encore vérifiée ou si l'annonce a été refusée. Vous pouvez suivre le statut de "
        "chaque bien depuis « Mes biens » dans votre espace propriétaire."
    )
    if not (user and user.is_authenticated and getattr(user, "role", None) == "owner"):
        return generic, []

    from properties.models import Property

    actions = [_action("Voir mes biens", "dashboard:owner_properties")]
    if not user.is_verified_owner:
        return (
            f"Votre identité n'est pas encore vérifiée (statut : {user.get_verification_status_display()}). "
            "Tant que la vérification n'est pas validée par l'administrateur, vos biens ne peuvent pas être publiés.",
            [_action("Vérification d'identité", "dashboard:owner_verify_identity")] + actions,
        )
    properties = Property.objects.filter(owner=user)
    pending = properties.filter(validation_status=Property.ValidationStatus.PENDING).count()
    rejected = properties.filter(validation_status=Property.ValidationStatus.REJECTED).count()
    published = properties.filter(is_published=True, is_validated=True).count()
    parts = [f"Vous avez {published} bien(s) publié(s)"]
    if pending:
        parts.append(f"{pending} en attente de validation par l'administrateur")
    if rejected:
        parts.append(f"{rejected} refusé(s)")
    text = ", ".join(parts) + ". "
    if pending:
        text += "Les biens en attente seront visibles dès leur validation."
    elif rejected:
        text += "Modifiez les annonces refusées depuis « Mes biens » pour les soumettre à nouveau."
    else:
        text += "Si un bien précis n'apparaît pas, vérifiez son statut dans « Mes biens »."
    return text, actions


GREETING = (
    "Bonjour ! Je suis l'Assistant DOMIORA, un assistant IA. Je peux rechercher des biens disponibles, les comparer "
    "et vous guider pour contacter un propriétaire ou demander une visite. Que recherchez-vous ?"
)

GENERIC_HELP = (
    "Je n'ai pas bien saisi votre demande. Je peux par exemple rechercher un bien (« appartement à Lomé, 2 chambres, "
    "150 000 FCFA maximum »), comparer des biens, ou vous expliquer la mise en relation, FedaPay, la vérification des "
    "propriétaires et la publication d'une annonce."
)

DEFAULT_QUICK_REPLIES = [
    "Je cherche un appartement à Lomé",
    "Comment contacter un propriétaire ?",
    "Comment publier mon bien ?",
]
