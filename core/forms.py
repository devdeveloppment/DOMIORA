from django import forms
from django.core.validators import RegexValidator
from .models import ContactMessage

INPUT_CLASSES = "mt-1 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "phone", "subject", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Votre nom complet", "class": INPUT_CLASSES}),
            "email": forms.EmailInput(attrs={"placeholder": "votre@email.com", "class": INPUT_CLASSES}),
            "phone": forms.TextInput(attrs={"placeholder": "+229 XX XX XX XX", "class": INPUT_CLASSES}),
            "subject": forms.TextInput(attrs={"placeholder": "Sujet de votre message", "class": INPUT_CLASSES}),
            "message": forms.Textarea(attrs={"placeholder": "Décrivez votre demande en détail...", "rows": 5, "class": INPUT_CLASSES}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = True
        self.fields['email'].required = True
        self.fields['message'].required = True
        self.fields['phone'].required = False
        self.fields['subject'].required = False
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if len(name) < 2:
            raise forms.ValidationError("Le nom doit contenir au moins 2 caractères.")
        return name
    
    def clean_message(self):
        message = self.cleaned_data.get('message')
        if len(message) < 10:
            raise forms.ValidationError("Le message doit contenir au moins 10 caractères.")
        return message
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # Basic phone validation
            phone = phone.strip()
            if not phone.replace('+', '').replace(' ', '').replace('-', '').isdigit():
                raise forms.ValidationError("Numéro de téléphone invalide.")
        return phone
