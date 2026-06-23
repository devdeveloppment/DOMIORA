from django import forms
from .models import Appointment

INPUT_CLASSES = "mt-1 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ["scheduled_at", "notes"]
        widgets = {
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": INPUT_CLASSES}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Précisions sur votre demande de rendez-vous...", "class": INPUT_CLASSES}),
        }
