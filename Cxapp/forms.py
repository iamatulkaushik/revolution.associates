"""
Cxapp/forms.py
===============
Main forms: company signup only. Sub-user and designation forms
live in their respective Cxapp/app/ modules.
"""

from django import forms
from django.contrib.auth.models import User
from Sapp.app.company import Company
from Sapp.app.state_district import State, District


class CxSignupForm(forms.Form):
    """
    Fresh-start company signup. Creates a User + Company + CxOwnerProfile.
    Fields listed here become LOCKED on the company after creation:
    company_name, start_date, pan, email1, mobile.
    """
    username        = forms.CharField(max_length=150)
    password        = forms.CharField(widget=forms.PasswordInput, min_length=8)
    password_confirm = forms.CharField(widget=forms.PasswordInput, min_length=8)

    company_name    = forms.CharField(max_length=255)
    start_date      = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    pan             = forms.CharField(max_length=10, min_length=10)
    email1          = forms.EmailField()
    mobile          = forms.CharField(max_length=10, min_length=10)

    state_id        = forms.ModelChoiceField(queryset=State.objects.all(), label='State')
    district_id     = forms.ModelChoiceField(queryset=District.objects.none(), label='District')
    address1        = forms.CharField(max_length=155, required=False)
    pin             = forms.CharField(max_length=6, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Scope district choices to whatever state was posted/selected,
        # same reasoning as CxEmployeeAddressForm — server-side guard
        # against a stale full district list round-tripping as valid.
        state_id = self.data.get(self.add_prefix('state_id')) if self.is_bound else None
        if state_id:
            self.fields['district_id'].queryset = District.objects.filter(state_id=state_id).order_by('name')

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username already taken.')
        return username

    def clean_pan(self):
        pan = self.cleaned_data['pan'].upper()
        if len(pan) != 10:
            raise forms.ValidationError('PAN must be exactly 10 characters.')
        return pan

    def clean_company_name(self):
        name = self.cleaned_data['company_name']
        if Company.objects.filter(company_name=name).exists():
            raise forms.ValidationError('A company with this name already exists.')
        return name

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get('password')
        pw2 = cleaned.get('password_confirm')
        if pw and pw2 and pw != pw2:
            raise forms.ValidationError('Passwords do not match.')
        return cleaned
