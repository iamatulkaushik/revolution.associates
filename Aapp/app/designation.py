from django.db import models
from django import forms
from django.contrib.auth.models import User
from django.db import migrations
from Sapp.app.company import Company
from Sapp.app.user import associateuser
from django.shortcuts import get_object_or_404, redirect, render
# Designation model to store job titles and descriptions

class designation(models.Model):
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
    ed_epf_per = forms.DecimalField(max_digits=5, decimal_places=2, required=False, initial=12.00)
    ed_esi_per = forms.DecimalField(max_digits=5, decimal_places=2, required=False, initial=0.75)
    ed_labourwelfare_per = forms.DecimalField(max_digits=5, decimal_places=2, required=False, initial=0.50)
    ed_epf_amount = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    ed_esi_amount = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    ed_labourwelfare_amount = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    ed_professionaltax = forms.DecimalField(max_digits=5, decimal_places=2, required=False)
    ed_income_tax = forms.DecimalField(max_digits=5, decimal_places=2, required=False)
    er_epf_per = forms.DecimalField(max_digits=5, decimal_places=2, required=False, initial=13.00)
    er_esi_per = forms.DecimalField(max_digits=5, decimal_places=2, required=False, initial=3.25)
    er_labourwelfare_per = forms.DecimalField(max_digits=5, decimal_places=2, required=False, initial=0.50)
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

def list_designation(request):
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return render(request, 'Aapp/works/list_designation.html', {'designations': []})
    
    selected_company = Company.objects.get(company_id=selected_company_id)
    designations = designation.objects.filter(company=selected_company, is_deleted=False)
    return render(request, 'Aapp/works/list_designation.html', {'designations': designations})

def create_designation(request):
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return render(request, 'Aapp/works/create_designation.html', {})
    
    selected_company = Company.objects.get(company_id=selected_company_id)
    
    if request.method == 'POST':
        designationname = request.POST.get('designationname')
        
        if not designationname:
            from django.contrib import messages
            messages.error(request, "Designation name is required.")
        elif designation.objects.filter(company=selected_company, designationname=designationname).exists():
            from django.contrib import messages
            messages.error(request, f"Designation '{designationname}' already exists in this company.")
        else:
            designation.objects.create(
                designationname=designationname,
                is_dailywage=request.POST.get('is_dailywage') == 'on',
                dailywage=request.POST.get('dailywage', 0) or 0,
                basicpay=request.POST.get('basicpay', 0) or 0,
                hra=request.POST.get('hra', 0) or 0,
                da=request.POST.get('da', 0) or 0,
                medicalallowance=request.POST.get('medicalallowance', 0) or 0,
                conveyance=request.POST.get('conveyance', 0) or 0,
                lunchallowance=request.POST.get('lunchallowance', 0) or 0,
                cca=request.POST.get('cca', 0) or 0,
                specialallowance=request.POST.get('specialallowance', 0) or 0,
                travelallowance=request.POST.get('travelallowance', 0) or 0,
                washingallowance=request.POST.get('washingallowance', 0) or 0,
                cycleallowance=request.POST.get('cycleallowance', 0) or 0,
                other1=request.POST.get('other1', 0) or 0,
                other2=request.POST.get('other2', 0) or 0,
                ed_epf_per=request.POST.get('ed_epf_per', 12.00),
                ed_esi_per=request.POST.get('ed_esi_per', 0.75),
                ed_labourwelfare_per=request.POST.get('ed_labourwelfare_per', 0.50),
                ed_epf_amount=request.POST.get('ed_epf_amount', 0) or 0,
                ed_esi_amount=request.POST.get('ed_esi_amount', 0) or 0,
                ed_labourwelfare_amount=request.POST.get('ed_labourwelfare_amount', 0) or 0,
                ed_professionaltax=request.POST.get('ed_professionaltax', 0) or 0,
                ed_income_tax=request.POST.get('ed_income_tax', 0) or 0,
                er_epf_per=request.POST.get('er_epf_per', 13.00),
                er_esi_per=request.POST.get('er_esi_per', 3.25),
                er_labourwelfare_per=request.POST.get('er_labourwelfare_per', 0.50),
                er_epf_amount=request.POST.get('er_epf_amount', 0) or 0,
                er_esi_amount=request.POST.get('er_esi_amount', 0) or 0,
                er_labourwelfare_amount=request.POST.get('er_labourwelfare_amount', 0) or 0,
                company=selected_company,
                created_by=request.user.username,
                updated_by=request.user.username
            )
            from django.contrib import messages
            messages.success(request, f"Designation '{designationname}' created successfully.")
            return redirect('list_designation')
    
    return render(request, 'Aapp/works/create_designation.html', {})

def alter_designation(request, designation_id):
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return render(request, 'Aapp/works/alter_designation.html', {'designation': None})
    
    designation_instance = get_object_or_404(designation, designationid=designation_id, company__company_id=selected_company_id)
    
    if request.method == 'POST':
        designation_instance.designationname = request.POST.get('designationname')
        designation_instance.is_dailywage = request.POST.get('is_dailywage') == 'on'
        designation_instance.dailywage = request.POST.get('dailywage', 0) or 0
        designation_instance.basicpay = request.POST.get('basicpay', 0) or 0
        designation_instance.updated_by = request.user.username
        designation_instance.save()
        from django.contrib import messages
        messages.success(request, f"Designation '{designation_instance.designationname}' updated successfully.")
        return redirect('list_designation')
    
    return render(request, 'Aapp/works/alter_designation.html', {'designation': designation_instance})

def disable_designation(request, designation_id):
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return render(request, 'Aapp/works/disable_designation.html', {'designation': None})
    
    designation_instance = get_object_or_404(designation, designationid=designation_id, company__company_id=selected_company_id)
    
    if request.method == 'POST':
        designation_name = designation_instance.designationname
        designation_instance.is_active = False
        designation_instance.save()
        from django.contrib import messages
        messages.success(request, f"Designation '{designation_name}' disabled successfully.")
        return redirect('list_designation')
    
    return render(request, 'Aapp/works/disable_designation.html', {'designation': designation_instance})


#post migration code to create initial designation for testing purposes.
#insert minimum wages posts into designation as daily wages.
#some of Minimum Wages posts are inserted directly into database like Unskilled(433.64), Semi-Skilled(a)(455.32), Semi-Skilled(b)(478.08),
# Skilled(a)(501.99), Skilled(b)(527.09), Highely-Skilled(553.44)

def create_initial_designation(apps, schema_editor):
    Designation = apps.get_model('Aapp', 'designation')
    Designation.objects.create(
        designationname='Manager',
        is_dailywage=False,
        dailywage=0,
        basicpay=20000,
        hra=8000,
        da=10000,
        medicalallowance=2000,
        conveyance=1000,
        lunchallowance=1000,
        cca=0,
        specialallowance=0,
        travelallowance=0,
        washingallowance=0,
        cycleallowance=0,
        other1=0,
        other2=0,
        ed_epf_per=12.00,
        ed_esi_per=0.75,
        ed_labourwelfare_per=0.50,
        ed_epf_amount=0,
        ed_esi_amount=0,
        ed_labourwelfare_amount=0,
        ed_professionaltax=0,
        ed_income_tax=0,
        er_epf_per=13.00,
        er_esi_per=3.25,
        er_labourwelfare_per=0.50,
        er_epf_amount=0,
        er_esi_amount=0,
        er_labourwelfare_amount=0,
        company=None,
        created_by='admin',
        updated_by='admin',
        is_active=True,
        is_deleted=False
    )
    Designation.objects.create(
        designationname='peon',
        is_dailywage=True,
        dailywage=433.64,
        basicpay=0,
        hra=0,
        da=0,
        medicalallowance=0,
        conveyance=0,
        lunchallowance=0,
        cca=0,
        specialallowance=0,
        travelallowance=0,
        washingallowance=0,
        cycleallowance=0,
        other1=0,
        other2=0,
        ed_epf_per=0,
        ed_esi_per=0,
        ed_labourwelfare_per=0,
        ed_epf_amount=0,
        ed_esi_amount=0,
        ed_labourwelfare_amount=0,
        ed_professionaltax=0,
        ed_income_tax=0,
        er_epf_per=0,
        er_esi_per=0,
        er_labourwelfare_per=0,
        er_epf_amount=0,
        er_esi_amount=0,
        er_labourwelfare_amount=0,
        company=None,
        created_by='admin',
        updated_by='admin',
        is_active=True,
        is_deleted=False
    )
    Designation.objects.create(
        designationname='Unskilled',
        is_dailywage=True,
        dailywage=433.64,
        basicpay=0,
        hra=0,
        da=0,
        medicalallowance=0,
        conveyance=0,
        lunchallowance=0,
        cca=0,
        specialallowance=0,
        travelallowance=0,
        washingallowance=0,
        cycleallowance=0,
        other1=0,
        other2=0,
        ed_epf_per=0,
        ed_esi_per=0,
        ed_labourwelfare_per=0,
        ed_epf_amount=0,
        ed_esi_amount=0,
        ed_labourwelfare_amount=0,
        ed_professionaltax=0,
        ed_income_tax=0,
        er_epf_per=0,
        er_esi_per=0,
        er_labourwelfare_per=0,
        er_epf_amount=0,
        er_esi_amount=0,
        er_labourwelfare_amount=0,
        company=None,
        created_by='admin',
        updated_by='admin',
        is_active=True,
        is_deleted=False
    )
    Designation.objects.create(
        designationname='Semi-Skilled(a)',
        is_dailywage=True,
        dailywage=455.32,
        basicpay=0,
        hra=0,
        da=0,
        medicalallowance=0,
        conveyance=0,
        lunchallowance=0,
        cca=0,
        specialallowance=0,
        travelallowance=0,
        washingallowance=0,
        cycleallowance=0,
        other1=0,
        other2=0,
        ed_epf_per=0,
        ed_esi_per=0,
        ed_labourwelfare_per=0,
        ed_epf_amount=0,
        ed_esi_amount=0,
        ed_labourwelfare_amount=0,
        ed_professionaltax=0,
        ed_income_tax=0,
        er_epf_per=0,
        er_esi_per=0,
        er_labourwelfare_per=0,
        er_epf_amount=0,
        er_esi_amount=0,
        er_labourwelfare_amount=0,
        company=None,
        created_by='admin',
        updated_by='admin',
        is_active=True,
        is_deleted=False
    )
    Designation.objects.create(
        designationname='Semi-Skilled(b)',
        is_dailywage=True,
        dailywage=478.08,
        basicpay=0,
        hra=0,
        da=0,
        medicalallowance=0,
        conveyance=0,
        lunchallowance=0,
        cca=0,
        specialallowance=0,
        travelallowance=0,
        washingallowance=0,
        cycleallowance=0,
        other1=0,
        other2=0,
        ed_epf_per=0,
        ed_esi_per=0,
        ed_labourwelfare_per=0,
        ed_epf_amount=0,
        ed_esi_amount=0,
        ed_labourwelfare_amount=0,
        ed_professionaltax=0,
        ed_income_tax=0,
        er_epf_per=0,
        er_esi_per=0,
        er_labourwelfare_per=0,
        er_epf_amount=0,
        er_esi_amount=0,
        er_labourwelfare_amount=0,
        company=None,
        created_by='admin',
        updated_by='admin',
        is_active=True,
        is_deleted=False
    )
    Designation.objects.create(
        designationname='Skilled(a)',
        is_dailywage=True,
        dailywage=501.99,
        basicpay=0,
        hra=0,
        da=0,
        medicalallowance=0,
        conveyance=0,
        lunchallowance=0,
        cca=0,
        specialallowance=0,
        travelallowance=0,
        washingallowance=0,
        cycleallowance=0,
        other1=0,
        other2=0,
        ed_epf_per=0,
        ed_esi_per=0,
        ed_labourwelfare_per=0,
        ed_epf_amount=0,
        ed_esi_amount=0,
        ed_labourwelfare_amount=0,
        ed_professionaltax=0,
        ed_income_tax=0,
        er_epf_per=0,
        er_esi_per=0,
        er_labourwelfare_per=0,
        er_epf_amount=0,
        er_esi_amount=0,
        er_labourwelfare_amount=0,
        company=None,
        created_by='admin',
        updated_by='admin',
        is_active=True,
        is_deleted=False
    )
    Designation.objects.create(
        designationname='Skilled(b)',
        is_dailywage=True,
        dailywage=527.15,
        basicpay=0,
        hra=0,
        da=0,
        medicalallowance=0,
        conveyance=0,
        lunchallowance=0,
        cca=0,
        specialallowance=0,
        travelallowance=0,
        washingallowance=0,
        cycleallowance=0,
        other1=0,
        other2=0,
        ed_epf_per=0,
        ed_esi_per=0,
        ed_labourwelfare_per=0,
        ed_epf_amount=0,
        ed_esi_amount=0,
        ed_labourwelfare_amount=0,
        ed_professionaltax=0,
        ed_income_tax=0,
        er_epf_per=0,
        er_esi_per=0,
        er_labourwelfare_per=0,
        er_epf_amount=0,
        er_esi_amount=0,
        er_labourwelfare_amount=0,
        company=None,
        created_by='admin',
        updated_by='admin',
        is_active=True,
        is_deleted=False
    )    
class CreateInitialDesignation(migrations.Migration):

    dependencies = [
        ('Aapp', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_initial_designation),
    ]