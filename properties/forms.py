from django import forms
from django.forms import inlineformset_factory
from .models import Property, PropertyImage

INPUT_CLASSES = "mt-1 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            "title", "description", "property_type", "transaction_type", "price", "currency",
            "country", "city", "address", "latitude", "longitude",
            "bedrooms", "bathrooms", "surface_area", "floors", "year_built",
            "status", "is_featured", "is_published", "amenities",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "amenities": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                continue
            field.widget.attrs["class"] = INPUT_CLASSES


class AdminPropertyForm(PropertyForm):
    class Meta(PropertyForm.Meta):
        fields = ["agent", "is_validated"] + PropertyForm.Meta.fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["agent"].widget.attrs["class"] = INPUT_CLASSES


class PropertyImageForm(forms.ModelForm):
    class Meta:
        model = PropertyImage
        fields = ["image", "is_primary", "order"]


PropertyImageFormSet = inlineformset_factory(
    Property, PropertyImage, form=PropertyImageForm, extra=4, can_delete=True
)
