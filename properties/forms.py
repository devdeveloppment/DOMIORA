from django import forms
from django.forms import inlineformset_factory
from .models import Property, PropertyImage, PropertyDocument
from accounts.models import User

INPUT_CLASSES = "mt-1 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            "title", "description", "property_type", "transaction_type", "price", "currency",
            "country", "city", "neighborhood", "address", "latitude", "longitude",
            "bedrooms", "bathrooms", "surface_area", "floors", "year_built",
            "status", "is_featured", "amenities", "virtual_tour_url", "uploaded_tour_video",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "amenities": forms.CheckboxSelectMultiple,
            "uploaded_tour_video": forms.FileInput(attrs={"accept": "video/mp4,video/webm,video/ogg"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                continue
            field.widget.attrs["class"] = INPUT_CLASSES


class PropertyDocumentForm(forms.ModelForm):
    class Meta:
        model = PropertyDocument
        fields = ['file', 'document_type', 'title', 'description', 'order']
        widgets = {
            'file': forms.FileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                continue
            field.widget.attrs["class"] = INPUT_CLASSES


class AdminPropertyForm(PropertyForm):
    class Meta(PropertyForm.Meta):
        fields = ["owner", "is_validated"] + PropertyForm.Meta.fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].required = True
        self.fields["owner"].queryset = User.objects.filter(role=User.Role.OWNER, is_active=True)
        self.fields["owner"].widget.attrs["class"] = INPUT_CLASSES

    def clean_owner(self):
        owner = self.cleaned_data.get("owner")
        if not owner or owner.role != User.Role.OWNER:
            raise forms.ValidationError("Chaque bien doit être lié à un propriétaire valide.")
        return owner


class PropertyImageForm(forms.ModelForm):
    class Meta:
        model = PropertyImage
        fields = ["image", "is_primary", "order"]


PropertyImageFormSet = inlineformset_factory(
    Property, PropertyImage, form=PropertyImageForm, extra=4, can_delete=True
)

PropertyDocumentFormSet = inlineformset_factory(
    Property, PropertyDocument, form=PropertyDocumentForm, extra=0, can_delete=True
)
