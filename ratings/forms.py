from django import forms
from .models import Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'title', 'comment', 'communication_rating', 'professionalism_rating', 'responsiveness_rating']
        widgets = {
            'rating': forms.RadioSelect,
            'communication_rating': forms.RadioSelect,
            'professionalism_rating': forms.RadioSelect,
            'responsiveness_rating': forms.RadioSelect,
            'comment': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rating'].label = "Note globale"
        self.fields['title'].label = "Titre de votre avis"
        self.fields['comment'].label = "Votre expérience"
        self.fields['communication_rating'].label = "Communication"
        self.fields['professionalism_rating'].label = "Professionnalisme"
        self.fields['responsiveness_rating'].label = "Réactivité"