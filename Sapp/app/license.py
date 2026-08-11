from datetime import date, timedelta
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
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('revoked', 'Revoked'),
        ('expired', 'Expired'),
    ]

    license_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='licenses')
    associate = models.ForeignKey('Sapp.associateuser', on_delete=models.CASCADE, related_name='licenses', null=True, blank=True)
    license_key = models.CharField(max_length=100, unique=True)
    license_type = models.CharField(max_length=20, choices=LICENSE_TYPES, default='trial')
    issue_date = models.DateField()
    expiry_date = models.DateField()
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    max_users = models.PositiveIntegerField(default=5)
    suspension_reason = models.TextField(blank=True, null=True)
    revoke_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.expiry_date:
            from datetime import timedelta
            if self.license_type == 'trial':
                self.max_users = 1
                if self.issue_date:
                    self.expiry_date = self.issue_date + timedelta(days=7)
            elif self.license_type == 'basic':
                self.max_users = 5
                if self.issue_date:
                    self.expiry_date = self.issue_date + timedelta(days=365)
            elif self.license_type == 'premium':
                self.max_users = 10
                if self.issue_date:
                    self.expiry_date = self.issue_date + timedelta(days=365 * 3)
            elif self.license_type == 'enterprise':
                self.max_users = 999999
                if self.issue_date:
                    self.expiry_date = self.issue_date + timedelta(days=365 * 10)
        
        super().save(*args, **kwargs)

    @classmethod
    def has_valid_license(cls, company):
        """Check if a company has any active, non-expired license."""
        return cls.objects.filter(
            company=company,
            is_active=True,
            status='active',
            expiry_date__gte=date.today()
        ).exists()

    def __str__(self):
        return f"{self.company.company_name} - {self.license_type} ({self.license_key})"

    class Meta:
        app_label = 'Sapp'
        db_table = 'sa_licenses'
        verbose_name = 'License'
        verbose_name_plural = 'Licenses'
        ordering = ['-expiry_date']

    def is_expired(self):
        return self.expiry_date < date.today()
    
    def suspend(self, reason=""):
        self.status = 'suspended'
        self.is_active = False
        self.suspension_reason = reason
        self.save()
    
    def revoke(self, reason=""):
        self.status = 'revoked'
        self.is_active = False
        self.revoke_reason = reason
        self.save()
    
    def activate(self):
        if not self.is_expired():
            self.status = 'active'
            self.is_active = True
            self.suspension_reason = None
            self.save()

class LicenseForm(ModelForm):
    class Meta:
        model = License
        fields = ['company', 'associate', 'license_key', 'license_type', 'issue_date', 'max_users']
        widgets = {
            'company': forms.Select(attrs={'class': 'form-control'}),
            'associate': forms.Select(attrs={'class': 'form-control'}),
            'license_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Auto-generated if empty'}),
            'license_type': forms.Select(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'max_users': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['license_key'].required = False
        self.fields['associate'].required = False
