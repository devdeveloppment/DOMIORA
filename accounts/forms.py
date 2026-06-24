from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User

INPUT_CLASSES = "mt-1 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"


class StyledFormMixin:
    def style_fields(self):
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.RadioSelect, forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                continue
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " " + INPUT_CLASSES).strip()


class RegisterForm(StyledFormMixin, UserCreationForm):
    first_name = forms.CharField(max_length=150, required=True, label="Prénom")
    last_name = forms.CharField(max_length=150, required=True, label="Nom")
    email = forms.EmailField(required=True, label="Adresse e-mail")
    phone = forms.CharField(max_length=30, required=False, label="Téléphone")
    role = forms.ChoiceField(
        choices=[(User.Role.BUYER, "Acheteur / Locataire"), (User.Role.AGENT, "Agent immobilier")],
        label="Je suis un",
        widget=forms.RadioSelect,
        initial=User.Role.BUYER,
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email", "phone", "role", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data.get("phone", "")
        user.role = self.cleaned_data["role"]
        if commit:
            user.save()
        return user


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "bio", "avatar"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
