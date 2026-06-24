from django import forms
from .models import AgentReview

INPUT_CLASSES = "mt-1 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary-500 outline-none"


class AgentReviewForm(forms.ModelForm):
    class Meta:
        model = AgentReview
        fields = ["rating", "comment"]
        widgets = {
            "rating": forms.Select(choices=[(i, f"{i} ★") for i in range(5, 0, -1)], attrs={"class": INPUT_CLASSES}),
            "comment": forms.Textarea(attrs={"rows": 3, "placeholder": "Partagez votre expérience avec cet agent...", "class": INPUT_CLASSES}),
        }
