from django.db import models
from django import forms
from django.forms import ModelForm
from Sapp.app.company import Company

class License(models.Model):
    LICENSE_TYPES = [
        ('trial', 'Trial'),
        ('basic', 'Basic'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise'),
    ]

    license_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='licenses')
    license_key = models.CharField(max_length=100, unique=True)
    license_type = models.CharField(max_length=20, choices=LICENSE_TYPES, default='trial')
    issue_date = models.DateField()
    expiry_date = models.DateField()
    is_active = models.BooleanField(default=True)
    max_users = models.PositiveIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def has_valid_license(cls, company):
        """Check if a company has any active, non-expired license."""
        from datetime import date
        return cls.objects.filter(
            company=company,
            is_active=True,
            expiry_date__gte=date.today()
        ).exists()

    def __str__(self):
        return f"{self.company.company_name} - {self.license_type} ({self.license_key})"

    class Meta:
        db_table = 'licenses'
        ordering = ['-expiry_date']

    def is_expired(self):
        from datetime import date
        return self.expiry_date < date.today()

class LicenseForm(ModelForm):
    class Meta:
        model = License
        fields = ['company', 'license_key', 'license_type', 'issue_date', 'expiry_date', 'max_users', 'is_active']
        widgets = {
            'company': forms.Select(attrs={'class': 'form-control'}),
            'license_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter License Key'}),
            'license_type': forms.Select(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'max_users': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter Max Users'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
