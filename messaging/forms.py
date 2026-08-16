from django import forms
from .models import Message, VisitRequest, RendezvousRequest

INPUT_CLASSES = (
    "w-full resize-none rounded-xl border border-gray-200 px-4 py-2.5 text-sm "
    "focus:ring-2 focus:ring-[#71212d]/30 focus:border-[#71212d] outline-none transition"
)


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": "Écrivez votre message...",
                    "class": INPUT_CLASSES,
                }
            )
        }


class VisitRequestForm(forms.ModelForm):
    class Meta:
        model = VisitRequest
        fields = ["proposed_date", "message"]
        widgets = {
            "proposed_date": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": INPUT_CLASSES,
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Précisez votre demande (ex: horaires préférés, questions...)",
                    "class": INPUT_CLASSES,
                }
            )
        }


class RendezvousRequestForm(forms.ModelForm):
    class Meta:
        model = RendezvousRequest
        fields = ["proposed_date", "message"]
        widgets = {
            "proposed_date": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": INPUT_CLASSES,
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Précisez votre demande (ex: sujet du rendez-vous, disponibilités...)",
                    "class": INPUT_CLASSES,
                }
            )
        }


class VisitResponseForm(forms.Form):
    response_message = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Votre réponse au client...",
                "class": INPUT_CLASSES,
            }
        ),
        required=False
    )
    proposed_date = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": INPUT_CLASSES,
            }
        ),
        required=False
    )


class RendezvousResponseForm(forms.Form):
    response_message = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Votre réponse au client...",
                "class": INPUT_CLASSES,
            }
        ),
        required=False
    )
    proposed_date = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": INPUT_CLASSES,
            }
        ),
        required=False
    )
