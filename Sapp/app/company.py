from django import forms
from django.db import models
from django.forms import ModelForm
from Sapp.app.state_district import State, District
from Sapp.app.bank import bank_name
from django.db.models import TextField
from django.forms.widgets import DateInput, EmailInput, TextInput, URLInput


class Company(models.Model):
    company_id = models.AutoField(primary_key=True)
    company_name = models.CharField(max_length=255, null=False, unique=True, blank=False)
    start_date = models.DateField()
    shut_date = models.DateField(null=True, blank=True)
    tagline1 = models.CharField(max_length=255, null=True, blank=True)
    address1 = models.CharField(max_length=155, null=True, blank=True)
    address2 = models.CharField(max_length=155, null=True, blank=True)
    address3 = models.CharField(max_length=155, null=True, blank=True)
    state_id = models.ForeignKey(State, related_name="companystate", db_column="StateID", on_delete=models.CASCADE)
    district_id = models.ForeignKey(District, related_name="companydistrict", db_column="DistrictID", on_delete=models.CASCADE)
    pin = models.CharField(max_length=6, null=True, blank=True)
    phone = models.CharField(max_length=10, null=True, blank=True)
    phone2 = models.CharField(max_length=10, null=True, blank=True)
    mobile = models.CharField(max_length=10)
    mobile2 = models.CharField(max_length=10, null=True, blank=True)
    email1 = models.EmailField()
    email2 = models.EmailField(null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    pan = models.CharField(max_length=10, unique=True, default="AAAAA0000A")
    tan = models.CharField(max_length=10, null=True, blank=True)
    cin = models.CharField(max_length=21, null=True, blank=True)
    bank_id = models.ForeignKey(bank_name, related_name="companybank", db_column="BankID", on_delete=models.CASCADE, null=True, blank=True)
    account = models.CharField(max_length=20, null=True, blank=True)
    ifsc = models.CharField(max_length=11, null=True, blank=True)
    branch_address = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.company_name

    class Meta:
        db_table = 'Company'

    @property
    def full_address(self):
        address_parts = [self.address1, self.address2, self.address3, 
                         f"{self.district_id.district_name}, {self.state_id.state_name}", 
                         self.pin]
        return ', '.join(part for part in address_parts if part)

    def get_contact_info(self):
        contacts = []
        if self.phone:
            contacts.append(f"Phone: {self.phone}")
        if self.phone2:
            contacts.append(f"Phone2: {self.phone2}")
        if self.mobile:
            contacts.append(f"Mobile: {self.mobile}")
        if self.mobile2:
            contacts.append(f"Mobile2: {self.mobile2}")
        if self.email1:
            contacts.append(f"Email: {self.email1}")
        if self.email2:
            contacts.append(f"Email2: {self.email2}")
        return ' | '.join(contacts)

class company_statury(models.Model):
    statutry_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(Company, related_name="company_statutry_company", db_column="CompanyID", on_delete=models.CASCADE)
    epfo = models.CharField(max_length=15, null=True, blank=True)
    epfo_date = models.DateField(null=True, blank=True)
    esic = models.CharField(max_length=15, null=True, blank=True)
    esic_date = models.DateField(null=True, blank=True)
    gst = models.CharField(max_length=15, null=True, blank=True)
    gst_date = models.DateField(null=True, blank=True)
    shop_act = models.CharField(max_length=15, null=True, blank=True)
    shop_act_date = models.DateField(null=True, blank=True)
    labour = models.CharField(max_length=15, null=True, blank=True)
    labour_from = models.DateField(null=True, blank=True)
    labour_to = models.DateField(null=True, blank=True)
    psara = models.CharField(max_length=15, null=True, blank=True)
    psara_from = models.DateField(null=True, blank=True)
    psara_to = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Statutory Info for {self.company.company_name}"

    class Meta:
        db_table = 'company_statury'
        unique_together = ('company','epfo','esic','gst','shop_act','labour','psara')
        ordering = ['company']

    def is_valid_statutory(self):
        # Example validation: Check if EPFO and ESIC numbers are of valid length
        if self.epfo and len(self.epfo) != 15:
            return False
        if self.esic and len(self.esic) != 15:
            return False
        return True
    
class create_company_form_superadmin(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['company_name', 'start_date', 'shut_date', 'tagline1', 'address1', 'address2', 'address3',
                  'state_id', 'district_id', 'pin', 'phone', 'phone2', 'mobile', 'mobile2', 'email1', 'email2',
                  'website', 'pan', 'tan', 'cin', 'bank_id', 'account', 'ifsc', 'branch_address']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Name'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'shut_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'tagline1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tagline'}),
            'address1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address Line 1'}),
            'address2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address Line 2'}),
            'address3': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address Line 3'}),
            'pin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Pin Code'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'phone2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Alternate Phone Number'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mobile Number'}),
            'mobile2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Alternate Mobile Number'}),
            'email1': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'email2': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Alternate Email Address'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Website URL'}),
            'pan': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'PAN Number'}),
            'tan': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'TAN Number'}),
            'cin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'CIN Number'}),
            'account': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bank Account Number'}),
            'ifsc': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'IFSC Code'}),
            'branch_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bank Branch Address'}),
        }

    def clean_pan(self):
        pan = self.cleaned_data.get('pan')
        if len(pan) != 10:
            raise forms.ValidationError("PAN number must be exactly 10 characters.")
        return pan
    def clean_ifsc(self):
        ifsc = self.cleaned_data.get('ifsc')
        if ifsc and len(ifsc) != 11:
            raise forms.ValidationError("IFSC code must be exactly 11 characters.")
        return ifsc
    def save(self, commit=True):
        company_instance = super().save(commit=False)
        if commit:
            company_instance.save()
        return company_instance
    
    class quick_company_form(forms.Form):
        company_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Name'}))
        start_date = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
        mobile = forms.CharField(max_length=10, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mobile Number'}))
        email1 = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}))
        pan = forms.CharField(max_length=10, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'PAN Number'}))
        def clean_pan(self):
            pan = self.cleaned_data.get('pan')
            if len(pan) != 10:
                raise forms.ValidationError("PAN number must be exactly 10 characters.")
            return pan
        def save(self, commit=True):
            data = self.cleaned_data
            # Get default state and district (first available)
            default_state = State.objects.first()
            default_district = District.objects.filter(state=default_state).first() if default_state else None
            
            company_instance = Company(
                company_name=data['company_name'],
                start_date=data['start_date'],
                mobile=data['mobile'],
                email1=data['email1'],
                pan=data['pan'],
                state_id=default_state,
                district_id=default_district
            )
            if commit:
                company_instance.save()
            return company_instance
        
    class statuaryForm(forms.ModelForm):
        class Meta:
            model = company_statury
            fields = ['company', 'epfo', 'epfo_date', 'esic', 'esic_date', 'gst', 'gst_date',
                      'shop_act', 'shop_act_date', 'labour', 'labour_from', 'labour_to',
                      'psara', 'psara_from', 'psara_to']
            widgets = {
                'company': forms.Select(attrs={'class': 'form-control'}),
                'epfo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'EPFO Number'}),
                'epfo_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
                'esic': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ESIC Number'}),
                'esic_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
                'gst': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'GST Number'}),
                'gst_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
                'shop_act': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Shop Act Number'}),
                'shop_act_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
                'labour': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Labour License Number'}),
                'labour_from': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
                'labour_to': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
                'psara': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'PSARA License Number'}),
                'psara_from': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
                'psara_to': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            }
        def clean_epfo(self):
            epfo = self.cleaned_data.get('epfo')
            if epfo and len(epfo) != 15:
                raise forms.ValidationError("EPFO number must be exactly 15 characters.")
            return epfo
        def clean_esic(self):
            esic = self.cleaned_data.get('esic')
            if esic and len(esic) != 15:
                raise forms.ValidationError("ESIC number must be exactly 15 characters.")
            return esic
        def save(self, commit=True):
            statutry_instance = super().save(commit=False)
            if commit:
                statutry_instance.save()
            return statutry_instance