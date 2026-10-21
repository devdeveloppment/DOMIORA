from django import forms
from django.forms import inlineformset_factory
from .models import Property, PropertyImage, PropertyDocument
from accounts.models import User

INPUT_CLASSES = "mt-1 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"


MAX_IMAGES_PER_UPLOAD = 20
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_TOUR_VIDEO_BYTES = 100 * 1024 * 1024
_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF", "MPO"}

PROPERTY_LABELS = {
    "title": "Titre de l'annonce *",
    "description": "Description",
    "property_type": "Type de bien *",
    "transaction_type": "Transaction *",
    "price": "Prix *",
    "currency": "Devise",
    "country": "Pays",
    "city": "Ville *",
    "neighborhood": "Quartier",
    "address": "Adresse",
    "latitude": "Latitude (facultatif)",
    "longitude": "Longitude (facultatif)",
    "bedrooms": "Chambres",
    "bathrooms": "Salles de bain",
    "surface_area": "Surface (m²)",
    "floors": "Niveaux",
    "year_built": "Année de construction",
    "status": "Disponibilité",
    "is_featured": "Mettre en avant sur l'accueil",
    "amenities": "Équipements",
    "virtual_tour_url": "Lien de visite virtuelle",
    "uploaded_tour_video": "Vidéo de visite filmée",
}

PROPERTY_PLACEHOLDERS = {
    "title": "Ex. : Villa 4 chambres avec piscine à Lomé",
    "description": "Décrivez le bien : pièces, état, environnement, conditions de location ou de vente…",
    "price": "Ex. : 150000",
    "city": "Ex. : Lomé",
    "neighborhood": "Ex. : Agoè",
    "address": "Rue, repère… (non affichée avant la mise en relation)",
    "latitude": "Ex. : 6.1319",
    "longitude": "Ex. : 1.2228",
    "year_built": "Ex. : 2018",
    "virtual_tour_url": "https://…",
}


def validate_property_images(files):
    """
    Vérifie les photos envoyées (nombre, taille, contenu réel d'image) avant tout enregistrement.
    Retourne la liste des messages d'erreur (vide si tout est valide).
    """
    from PIL import Image, UnidentifiedImageError

    errors = []
    if len(files) > MAX_IMAGES_PER_UPLOAD:
        errors.append(f"Vous pouvez envoyer au maximum {MAX_IMAGES_PER_UPLOAD} photos à la fois.")
        return errors
    for f in files:
        if f.size > MAX_IMAGE_BYTES:
            errors.append(f"« {f.name} » dépasse 10 Mo.")
            continue
        try:
            with Image.open(f) as img:
                fmt = img.format
                img.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
            errors.append(f"« {f.name} » n'est pas une image lisible (JPEG, PNG ou WebP).")
            continue
        finally:
            f.seek(0)
        if fmt not in _IMAGE_FORMATS:
            errors.append(f"« {f.name} » : format non accepté (JPEG, PNG ou WebP).")
    return errors


class PropertyForm(forms.ModelForm):
    """Formulaire propriétaire : la mise en avant et la validation restent réservées à l'administration."""

    class Meta:
        model = Property
        fields = [
            "title", "description", "property_type", "transaction_type", "price", "currency",
            "country", "city", "neighborhood", "address", "latitude", "longitude",
            "bedrooms", "bathrooms", "surface_area", "floors", "year_built",
            "status", "amenities", "virtual_tour_url", "uploaded_tour_video",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "amenities": forms.CheckboxSelectMultiple,
            "uploaded_tour_video": forms.FileInput(attrs={"accept": "video/mp4,video/webm,video/ogg"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial.setdefault("currency", "XOF")
            self.initial.setdefault("country", "Togo")
        for name, field in self.fields.items():
            if name in PROPERTY_LABELS:
                field.label = PROPERTY_LABELS[name]
            if name in PROPERTY_PLACEHOLDERS:
                field.widget.attrs.setdefault("placeholder", PROPERTY_PLACEHOLDERS[name])
            if isinstance(field.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                continue
            field.widget.attrs["class"] = INPUT_CLASSES
        for name in ("price", "surface_area", "latitude", "longitude"):
            if name in self.fields:
                self.fields[name].widget.attrs.update({"inputmode": "decimal", "step": "any"})
        for name in ("bedrooms", "bathrooms", "floors", "year_built"):
            if name in self.fields:
                self.fields[name].widget.attrs.update({"inputmode": "numeric", "min": "0"})
        self.fields["price"].widget.attrs["min"] = "1"
        self.fields["title"].widget.attrs["maxlength"] = "200"

    def clean_title(self):
        title = " ".join((self.cleaned_data.get("title") or "").split())
        if len(title) < 5:
            raise forms.ValidationError("Le titre doit contenir au moins 5 caractères.")
        return title

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price is None or price <= 0:
            raise forms.ValidationError("Indiquez un prix supérieur à 0.")
        return price

    def clean_currency(self):
        return (self.cleaned_data.get("currency") or "XOF").strip().upper()[:5]

    def clean_latitude(self):
        value = self.cleaned_data.get("latitude")
        if value is not None and not -90 <= value <= 90:
            raise forms.ValidationError("La latitude doit être comprise entre -90 et 90.")
        return value

    def clean_longitude(self):
        value = self.cleaned_data.get("longitude")
        if value is not None and not -180 <= value <= 180:
            raise forms.ValidationError("La longitude doit être comprise entre -180 et 180.")
        return value

    def clean_surface_area(self):
        value = self.cleaned_data.get("surface_area")
        if value is not None and value < 0:
            raise forms.ValidationError("La surface ne peut pas être négative.")
        return value

    def clean_year_built(self):
        from django.utils import timezone

        value = self.cleaned_data.get("year_built")
        if value and not 1800 <= value <= timezone.now().year + 5:
            raise forms.ValidationError("Année de construction invalide.")
        return value

    def clean_uploaded_tour_video(self):
        video = self.cleaned_data.get("uploaded_tour_video")
        if video and hasattr(video, "content_type"):  # nouveau fichier envoyé
            if video.size > MAX_TOUR_VIDEO_BYTES:
                raise forms.ValidationError("La vidéo dépasse 100 Mo.")
            name = video.name.lower()
            if not name.endswith((".mp4", ".webm", ".ogg", ".mov")):
                raise forms.ValidationError("Format vidéo non accepté (MP4, WebM, OGG ou MOV).")
        return video


class PropertyDocumentForm(forms.ModelForm):
    class Meta:
        model = PropertyDocument
        fields = ['file', 'document_type', 'title', 'description', 'order']
        widgets = {
            'file': forms.FileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                continue
            field.widget.attrs["class"] = INPUT_CLASSES


class AdminPropertyForm(PropertyForm):
    class Meta(PropertyForm.Meta):
        fields = ["owner", "is_validated", "is_featured"] + PropertyForm.Meta.fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].required = True
        self.fields["owner"].queryset = User.objects.filter(role=User.Role.OWNER, is_active=True)
        self.fields["owner"].widget.attrs["class"] = INPUT_CLASSES

    def clean_owner(self):
        owner = self.cleaned_data.get("owner")
        if not owner or owner.role != User.Role.OWNER:
            raise forms.ValidationError("Chaque bien doit être lié à un propriétaire valide.")
        return owner


class PropertyImageForm(forms.ModelForm):
    class Meta:
        model = PropertyImage
        fields = ["image", "is_primary", "order"]


PropertyImageFormSet = inlineformset_factory(
    Property, PropertyImage, form=PropertyImageForm, extra=4, can_delete=True
)

PropertyDocumentFormSet = inlineformset_factory(
    Property, PropertyDocument, form=PropertyDocumentForm, extra=0, can_delete=True
)
