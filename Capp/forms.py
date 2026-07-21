from django import forms
from django.forms import modelform_factory

from .registry import AUDIT_FIELDS, REGISTRY

# Map: related model class -> its own direct company_lookup (only entries
# with a direct, non-dotted lookup can be used to scope a FK dropdown).
_MODEL_COMPANY_LOOKUP = {
    e.model: e.company_lookup for e in REGISTRY if '__' not in e.company_lookup
}


def build_form_class(entry):
    """
    ModelForm for `entry.model`, excluding the company field and audit
    fields (those are stamped server-side). FK fields pointing at another
    company-scoped model get their queryset narrowed in __init__.
    """
    exclude = set(AUDIT_FIELDS)
    if '__' not in entry.company_lookup:
        exclude.add(entry.company_lookup)
    base_form = modelform_factory(entry.model, form=forms.ModelForm, exclude=list(exclude))

    class ScopedForm(base_form):
        def __init__(self, *args, company=None, **kwargs):
            super().__init__(*args, **kwargs)
            self._owned_company = company
            if company is None:
                return
            for field in self.fields.values():
                if isinstance(field, forms.ModelChoiceField):
                    related_model = field.queryset.model
                    lookup = _MODEL_COMPANY_LOOKUP.get(related_model)
                    if lookup:
                        field.queryset = field.queryset.filter(**{lookup: company})

    ScopedForm.__name__ = f'{entry.model.__name__}ScopedForm'
    return ScopedForm
