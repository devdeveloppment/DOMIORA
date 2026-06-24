from django import forms
from .models import Message

INPUT_CLASSES = "mt-1 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary-500 outline-none"


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 2, "placeholder": "Écrivez votre message...", "class": INPUT_CLASSES})}
