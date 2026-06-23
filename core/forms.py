from django import forms
from .models import ContactMessage

INPUT_CLASSES = "mt-1 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "phone", "subject", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Votre nom", "class": INPUT_CLASSES}),
            "email": forms.EmailInput(attrs={"placeholder": "Votre e-mail", "class": INPUT_CLASSES}),
            "phone": forms.TextInput(attrs={"placeholder": "Votre téléphone (optionnel)", "class": INPUT_CLASSES}),
            "subject": forms.TextInput(attrs={"placeholder": "Sujet", "class": INPUT_CLASSES}),
            "message": forms.Textarea(attrs={"placeholder": "Votre message", "rows": 5, "class": INPUT_CLASSES}),
        }
