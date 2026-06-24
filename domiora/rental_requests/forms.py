from django import forms
from .models import PropertyRequest

INPUT_CLASSES = "mt-1 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"


class PropertyRequestForm(forms.ModelForm):
    class Meta:
        model = PropertyRequest
        fields = ["request_type", "message", "move_in_date"]
        widgets = {
            "request_type": forms.Select(attrs={"class": INPUT_CLASSES}),
            "message": forms.Textarea(attrs={"rows": 4, "placeholder": "Bonjour, je suis intéressé(e) par ce bien...", "class": INPUT_CLASSES}),
            "move_in_date": forms.DateInput(attrs={"type": "date", "class": INPUT_CLASSES}),
        }
