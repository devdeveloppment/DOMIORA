import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

_PHONE = re.compile(r"^\+?[0-9][0-9 .\-]{6,22}$")


def clean_phone_value(value, required=False):
    """Téléphone lisible : chiffres, espaces, points, tirets, « + » initial ; 8 à 15 chiffres."""
    value = (value or "").strip()
    if not value:
        if required:
            raise forms.ValidationError("Ce numéro est obligatoire.")
        return ""
    digits = re.sub(r"\D", "", value)
    if not _PHONE.match(value) or not 8 <= len(digits) <= 15:
        raise forms.ValidationError("Numéro invalide : saisissez 8 à 15 chiffres, par exemple +228 90 00 00 00.")
    return value


class UniqueEmailMixin:
    """Une adresse e-mail ne peut servir qu'à un seul compte (comparaison sans casse)."""
    email_required = True

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            if self.email_required:
                raise forms.ValidationError("L'adresse e-mail est obligatoire.")
            return ""
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cette adresse e-mail. Connectez-vous ou utilisez « Mot de passe oublié ».")
        return email

INPUT_CLASSES = (
    "mt-1 w-full rounded-xl border border-gray-200 px-4 py-3 text-sm "
    "focus:ring-2 focus:ring-[#71212d]/20 focus:border-[#71212d] outline-none bg-gray-50 hover:bg-white transition"
)


class StyledFormMixin:
    def style_fields(self):
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.RadioSelect, forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                continue
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " " + INPUT_CLASSES).strip()
        # Clavier mobile adapté et remplissage automatique.
        hints = {"phone": "tel", "whatsapp_number": "tel", "email": "email", "username": "username",
                 "first_name": "given-name", "last_name": "family-name", "password1": "new-password", "password2": "new-password"}
        for name, hint in hints.items():
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault("autocomplete", hint)
                if hint == "tel":
                    self.fields[name].widget.input_type = "tel"
                    self.fields[name].widget.attrs.setdefault("inputmode", "tel")


class RegisterForm(StyledFormMixin, UserCreationForm):
    """Original form — kept for admin/legacy use."""
    first_name = forms.CharField(max_length=150, required=True, label="Prénom *")
    last_name = forms.CharField(max_length=150, required=True, label="Nom *")
    email = forms.EmailField(required=True, label="Adresse e-mail *")
    phone = forms.CharField(max_length=30, required=False, label="Téléphone")
    whatsapp_number = forms.CharField(max_length=30, required=False, label="Numéro WhatsApp (Obligatoire pour propriétaire)")
    role = forms.ChoiceField(
        choices=[(User.Role.CLIENT, "Client (Acheteur / Locataire)"), (User.Role.OWNER, "Propriétaire")],
        label="Je suis un *",
        widget=forms.RadioSelect,
        initial=User.Role.CLIENT,
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email", "phone", "whatsapp_number", "role"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = "Nom d'utilisateur *"
        if 'password1' in self.fields:
            self.fields['password1'].label = "Mot de passe *"
        if 'password2' in self.fields:
            self.fields['password2'].label = "Confirmation du mot de passe *"
        self.style_fields()

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        whatsapp_number = cleaned_data.get("whatsapp_number")
        if role == User.Role.OWNER and not whatsapp_number:
            self.add_error("whatsapp_number", "Le numéro WhatsApp est obligatoire pour les propriétaires.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data.get("phone", "")
        user.whatsapp_number = self.cleaned_data.get("whatsapp_number", "")
        user.role = self.cleaned_data["role"]
        if user.role == User.Role.OWNER:
            user.verification_status = User.VerificationStatus.UNVERIFIED
        if commit:
            user.save()
        return user


class OwnerRegisterForm(UniqueEmailMixin, StyledFormMixin, UserCreationForm):
    """Dedicated registration form for property owners only."""
    first_name = forms.CharField(max_length=150, required=True, label="Prénom *")
    last_name = forms.CharField(max_length=150, required=True, label="Nom *")
    email = forms.EmailField(required=True, label="Adresse e-mail *")
    phone = forms.CharField(max_length=30, required=False, label="Téléphone")
    whatsapp_number = forms.CharField(max_length=30, required=True, label="Numéro WhatsApp *")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email", "phone", "whatsapp_number"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = "Nom d'utilisateur *"
        if 'password1' in self.fields:
            self.fields['password1'].label = "Mot de passe *"
        if 'password2' in self.fields:
            self.fields['password2'].label = "Confirmer le mot de passe *"
        self.fields['username'].help_text = "Lettres, chiffres et @ . + - _ uniquement (150 caractères maximum)."
        self.style_fields()

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data.get("phone"))

    def clean_whatsapp_number(self):
        return clean_phone_value(self.cleaned_data.get("whatsapp_number"), required=True)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data.get("phone", "")
        user.whatsapp_number = self.cleaned_data["whatsapp_number"]
        user.role = User.Role.OWNER
        user.verification_status = User.VerificationStatus.UNVERIFIED
        if commit:
            user.save()
        return user


class ClientPostPaymentForm(UniqueEmailMixin, StyledFormMixin, UserCreationForm):
    """Minimal registration form for clients after payment."""
    first_name = forms.CharField(max_length=150, required=True, label="Prénom *")
    last_name = forms.CharField(max_length=150, required=True, label="Nom *")
    phone = forms.CharField(max_length=30, required=True, label="Numéro de téléphone *")
    email = forms.EmailField(required=False, label="Adresse e-mail (facultative)")

    email_required = False

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email", "phone"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = "Nom d'utilisateur *"
        if 'password1' in self.fields:
            self.fields['password1'].label = "Mot de passe *"
        if 'password2' in self.fields:
            self.fields['password2'].label = "Confirmer *"
        self.style_fields()

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data.get("phone"), required=True)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data.get("email", "")
        user.phone = self.cleaned_data["phone"]
        user.role = User.Role.CLIENT
        if commit:
            user.save()
        return user


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "whatsapp_number", "bio", "avatar"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
