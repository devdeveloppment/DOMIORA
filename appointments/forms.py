from django import forms
from .models import Appointment

INPUT_CLASSES = "mt-1 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"


class AppointmentForm(forms.ModelForm):
    # Guest fields (for non-logged-in users)
    guest_name = forms.CharField(max_length=200, required=False, label="Votre nom complet")
    guest_email = forms.EmailField(required=False, label="Votre email")
    guest_phone = forms.CharField(max_length=30, required=False, label="Votre numéro de téléphone")
    
    class Meta:
        model = Appointment
        fields = ["scheduled_at", "notes"]
        widgets = {
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": INPUT_CLASSES}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Précisions sur votre demande de rendez-vous...", "class": INPUT_CLASSES}),
        }
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        
        # Make guest fields required if user is not authenticated
        if not user or not user.is_authenticated:
            self.fields['guest_name'].required = True
            self.fields['guest_email'].required = True
            self.fields['guest_phone'].required = True
        
        # Add styling to guest fields
        for field in ['guest_name', 'guest_email', 'guest_phone']:
            self.fields[field].widget.attrs['class'] = INPUT_CLASSES
