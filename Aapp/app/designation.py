from django.db import models
from django.forms import forms
from django.contrib.auth.models import User
from Sapp.app.company import Company
from Sapp.app.user import associateuser
# Designation model to store job titles and descriptions

class designation(models.model):
    designationid = models.AutoField(primary_key=True)
    designationname = models.CharField(max_length=255, unique=True)
    #allowance fields
    is_dailywage = models.BooleanField(default=False)
    dailywage = models.DecimalField(max_digits=10, decimal_places=2)
    basicpay = models.DecimalField(max_digits=10, decimal_places=2)
    hra = models.DecimalField(max_digits=10, decimal_places=2)
    da = models.DecimalField(max_digits=10, decimal_places=2)
    medicalallowance = models.DecimalField(max_digits=10, decimal_places=2)
    conveyance = models.DecimalField(max_digits=10, decimal_places=2)
    lunchallowance = models.DecimalField(max_digits=10, decimal_places=2)
    cca = models.DecimalField(max_digits=10, decimal_places=2)
    specialallowance = models.DecimalField(max_digits=10, decimal_places=2)
    travelallowance = models.DecimalField(max_digits=10, decimal_places=2)
    washingallowance = models.DecimalField(max_digits=10, decimal_places=2)
    cycleallowance = models.DecimalField(max_digits=10, decimal_places=2)
    other1 = models.DecimalField(max_digits=10, decimal_places=2)
    other2 = models.DecimalField(max_digits=10, decimal_places=2)
    #Employee deduction fields
    ed_epf_per = models.DecimalField(max_digits=5, decimal_places=2)
    ed_esi_per = models.DecimalField(max_digits=5, decimal_places=2)
    ed_labourwelfare_per = models.DecimalField(max_digits=5, decimal_places=2)
    ed_epf_amount = models.DecimalField(max_digits=10, decimal_places=2)
    ed_esi_amount = models.DecimalField(max_digits=10, decimal_places=2)
    ed_labourwelfare_amount = models.DecimalField(max_digits=10, decimal_places=2)
    ed_professionaltax = models.DecimalField(max_digits=5, decimal_places=2)
    ed_income_tax = models.DecimalField(max_digits=5, decimal_places=2)
    #employer contribution fields
    er_epf_per = models.DecimalField(max_digits=5, decimal_places=2)
    er_esi_per = models.DecimalField(max_digits=5, decimal_places=2)
    er_labourwelfare_per = models.DecimalField(max_digits=5, decimal_places=2)
    er_epf_amount = models.DecimalField(max_digits=10, decimal_places=2)
    er_esi_amount = models.DecimalField(max_digits=10, decimal_places=2)
    er_labourwelfare_amount = models.DecimalField(max_digits=10, decimal_places=2)
    #other fields
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='CompanyID')
    created_by = models.CharField(User, max_length=255)
    updated_by = models.CharField(User, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.designationname
    
    class Meta:
        db_table = 'Designation'
        ordering = ['designationname']
        verbose_name = 'Designation'
        verbose_name_plural = 'Designations'
    
    def save(self, *args, **kwargs):
        if not self.pk:
            self.created_by = self.created_by.username
        else:
            self.updated_by = self.updated_by.username
        super(designation, self).save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()

class createDesignationForm(forms.Form):
    designationname = forms.CharField(max_length=255)
    is_dailywage = forms.BooleanField(required=False)
    dailywage = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    basicpay = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    hra = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    da = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    medicalallowance = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    conveyance = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    lunchallowance = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    cca = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    specialallowance = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    travelallowance = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    washingallowance = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    cycleallowance = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    other1 = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    other2 = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    ed_epf_per = forms.DecimalField(max_digits=5, decimal_places=2, required=False, default=12.00)
    ed_esi_per = forms.DecimalField(max_digits=5, decimal_places=2, required=False, default=0.75)
    ed_labourwelfare_per = forms.DecimalField(max_digits=5, decimal_places=2, required=False, default=0.50)
    ed_epf_amount = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    ed_esi_amount = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    ed_labourwelfare_amount = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    ed_professionaltax = forms.DecimalField(max_digits=5, decimal_places=2, required=False)
    ed_income_tax = forms.DecimalField(max_digits=5, decimal_places=2, required=False)
    er_epf_per = forms.DecimalField(max_digits=5, decimal_places=2, required=False, default=13.00)
    er_esi_per = forms.DecimalField(max_digits=5, decimal_places=2, required=False, default=3.25)
    er_labourwelfare_per = forms.DecimalField(max_digits=5, decimal_places=2, required=False, default=0.50)
    er_epf_amount = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    er_esi_amount = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    er_labourwelfare_amount = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    company = forms.ModelChoiceField(queryset=Company.objects.all())
    created_by = forms.CharField(max_length=255)
    updated_by = forms.CharField(max_length=255)
    is_active = forms.BooleanField()
    is_deleted = forms.BooleanField()

    def clean_designationname(self):
        designationname = self.cleaned_data.get('designationname')
        if designation.objects.filter(designationname=designationname).exists():
            raise forms.ValidationError('Designation name already exists.')
        return designationname
    def clean(self):
        cleaned_data = super().clean()
        is_dailywage = cleaned_data.get('is_dailywage')
        dailywage = cleaned_data.get('dailywage')
        if is_dailywage and not dailywage:
            self.add_error('dailywage', 'Daily wage is required when is_dailywage is checked.')
        return cleaned_data
    def save(self, commit=True):
        designation_instance = designation(
            designationname=self.cleaned_data['designationname'],
            is_dailywage=self.cleaned_data['is_dailywage'],
            dailywage=self.cleaned_data['dailywage'],
            basicpay=self.cleaned_data['basicpay'],
            hra=self.cleaned_data['hra'],
            da=self.cleaned_data['da'],
            medicalallowance=self.cleaned_data['medicalallowance'],
            conveyance=self.cleaned_data['conveyance'],
            lunchallowance=self.cleaned_data['lunchallowance'],
            cca=self.cleaned_data['cca'],
            specialallowance=self.cleaned_data['specialallowance'],
            travelallowance=self.cleaned_data['travelallowance'],
            washingallowance=self.cleaned_data['washingallowance'],
            cycleallowance=self.cleaned_data['cycleallowance'],
            other1=self.cleaned_data['other1'],
            other2=self.cleaned_data['other2'],
            ed_epf_per=self.cleaned_data['ed_epf_per'],
            ed_esi_per=self.cleaned_data['ed_esi_per'],
            ed_labourwelfare_per=self.cleaned_data['ed_labourwelfare_per'],
            ed_epf_amount=self.cleaned_data['ed_epf_amount'],
            ed_esi_amount=self.cleaned_data['ed_esi_amount'],
            ed_labourwelfare_amount=self.cleaned_data['ed_labourwelfare_amount'],
            er_epf_per=self.cleaned_data['er_epf_per'],
            er_esi_per=self.cleaned_data['er_esi_per'],
            er_labourwelfare_per=self.cleaned_data['er_labourwelfare_per'],
            er_epf_amount=self.cleaned_data['er_epf_amount'],
            er_esi_amount=self.cleaned_data['er_esi_amount'],
            er_labourwelfare_amount=self.cleaned_data['er_labourwelfare_amount'],
            company=self.cleaned_data['company'],
            created_by=self.cleaned_data['created_by'],
            updated_by=self.cleaned_data['updated_by'],
            is_active=self.cleaned_data['is_active'],
            is_deleted=self.cleaned_data['is_deleted']
        )
        if commit:
            designation_instance.save()
        return designation_instance
    
    def update(self, instance, commit=True):
        for field, value in self.cleaned_data.items():
            setattr(instance, field, value)
        if commit:
            instance.save()
        return instance
    
    def delete(self, instance, commit=True):
        instance.is_deleted = True
        if commit:
            instance.save()
        return instance
    
    def restore(self, instance, commit=True):
        instance.is_deleted = False
        if commit:
            instance.save()
        return instance
    
    def __str__(self):
        return self.designationname
    
    class Meta:
        model = designation
        fields = '__all__'
        widgets = {
            'designationname': forms.TextInput(attrs={'class': 'form-control'}),
            'is_dailywage': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'dailywage': forms.NumberInput(attrs={'class': 'form-control'}),
            'basicpay': forms.NumberInput(attrs={'class': 'form-control'}),
            'hra': forms.NumberInput(attrs={'class': 'form-control'}),
            'da': forms.NumberInput(attrs={'class': 'form-control'}),
            'medicalallowance': forms.NumberInput(attrs={'class': 'form-control'}),
            'conveyance': forms.NumberInput(attrs={'class': 'form-control'}),
            'lunchallowance': forms.NumberInput(attrs={'class': 'form-control'}),
            'cca': forms.NumberInput(attrs={'class': 'form-control'}),
            'specialallowance': forms.NumberInput(attrs={'class': 'form-control'}),
            'travelallowance': forms.NumberInput(attrs={'class': 'form-control'}),
            'washingallowance': forms.NumberInput(attrs={'class': 'form-control'}),
            'cycleallowance': forms.NumberInput(attrs={'class': 'form-control'}),
            'other1': forms.NumberInput(attrs={'class': 'form-control'}),
            'other2': forms.NumberInput(attrs={'class': 'form-control'}),
            'ed_epf_per': forms.NumberInput(attrs={'class': 'form-control'}),
            'ed_esi_per': forms.NumberInput(attrs={'class': 'form-control'}),
            'ed_labourwelfare_per': forms.NumberInput(attrs={'class': 'form-control'}),
            'ed_epf_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'ed_esi_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'ed_labourwelfare_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'ed_professionaltax': forms.NumberInput(attrs={'class': 'form-control'}),
            'ed_income_tax': forms.NumberInput(attrs={'class': 'form-control'}),
            'er_epf_per': forms.NumberInput(attrs={'class': 'form-control'}),
            'er_esi_per': forms.NumberInput(attrs={'class': 'form-control'}),
            'er_labourwelfare_per': forms.NumberInput(attrs={'class': 'form-control'}),
            'er_epf_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'er_esi_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'er_labourwelfare_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'company': forms.Select(attrs={'class': 'form-control'}),
            'created_by': forms.TextInput(attrs={'class': 'form-control'}),
            'updated_by': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_deleted': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            }
        