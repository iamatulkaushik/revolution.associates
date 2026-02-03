from django.db import models
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.forms import ModelForm
from django.core.validators import RegexValidator, EmailValidator, MinValueValidator, MaxValueValidator
from django.forms import forms
from django.forms import widgets, TextInput


class bank_name(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
    class Meta:
        db_table = "banks"
        verbose_name = "Bank Name"
        verbose_name_plural = "Bank Names"

class bank_form(ModelForm):
    class Meta:
        model = bank_name
        fields = ['name']
        widgets = {
            'name': TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Bank Name'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise forms.ValidationError("Bank name cannot be empty.")
        return name
    
    def save(self, commit=True):
        bank_instance = super().save(commit=False)
        if commit:
            bank_instance.save()
        return bank_instance
    
    @receiver(post_migrate)
    def create_indian_banks(sender, app_config, **kwargs):
        try:
            Bank = app_config.get_model('bank_name')
        except LookupError:
            return

        banks = [
            "State Bank of India",
            "HDFC Bank",
            "ICICI Bank",
            "Axis Bank",
            "Kotak Mahindra Bank",
            "IndusInd Bank",
            "Punjab National Bank",
            "Bank of Baroda",
            "Canara Bank",
            "Union Bank of India",
            "IDBI Bank",
            "Indian Bank",
            "Central Bank of India",
            "Bank of India",
            "UCO Bank",
            "Punjab & Sind Bank",
            "RBL Bank",
            "Federal Bank",
            "South Indian Bank",
            "Karur Vysya Bank",
            "DCB Bank",
            "Karnataka Bank",
            "Jammu & Kashmir Bank",
            "AU Small Finance Bank",
            "Equitas Small Finance Bank",
            "Ujjivan Small Finance Bank",
            "ESAF Small Finance Bank",
            "IDFC First Bank",
            "Yes Bank",
            "Nainital Bank",
            "Bank of Maharashtra",
            "Indian Overseas Bank",
            "Bandhan Bank",
            "Jana Small Finance Bank",
        ]

        for name in banks:
            if name:
                Bank.objects.get_or_create(name=name)