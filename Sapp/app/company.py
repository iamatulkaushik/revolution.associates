from datetime import date

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
    company_logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    created_at = models.DateTimeField(default=date.today)
    created_by = models.CharField(max_length=50, null=True, blank=True)
    updated_at = models.DateTimeField(default=date.today)
    updated_by = models.CharField(max_length=50, null=True, blank=True)

    # ── PDF letterhead preference ────────────────────────────────────────
    # Lets each company choose how generated PDFs (salary slips, registers,
    # returns, etc.) handle their letterhead — see Aapp.app.pdf_engine.
    LETTERHEAD_MODE_CHOICES = [
        ('drawn',      'Generated header/footer (no physical letterhead)'),
        ('preprinted', 'Pre-printed stationery (blank margins only)'),
        ('overlay',    'Digital letterhead overlay (background PDF)'),
    ]
    letterhead_mode = models.CharField(
        max_length=15, choices=LETTERHEAD_MODE_CHOICES, default='drawn',
        help_text='How PDFs handle this company\'s letterhead.',
    )
    letterhead_top_margin_mm = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Blank top margin (mm) to match pre-printed stationery. '
                   'Only used when letterhead_mode is preprinted/overlay.',
    )
    letterhead_bottom_margin_mm = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Blank bottom margin (mm) to match pre-printed stationery.',
    )
    letterhead_background_pdf = models.FileField(
        upload_to='letterheads/', null=True, blank=True,
        help_text='PDF of the letterhead artwork — required when letterhead_mode is overlay.',
    )

    def __str__(self):
        return self.company_name

    class Meta:
        app_label = 'Sapp'
        db_table = 'sa_Company'
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'

    def pdf_letterhead_kwargs(self):
        """
        Resolves this company's letterhead preference into the kwargs
        build_pdf() expects, so callers don't need to know the details:

            from Aapp.app.pdf_engine import build_pdf
            pdf_bytes = build_pdf(story, company=company, doc_meta=meta,
                                   **company.pdf_letterhead_kwargs())
        """
        kwargs = {'letterhead_mode': self.letterhead_mode}
        margins = {}
        if self.letterhead_top_margin_mm:
            margins['top'] = self.letterhead_top_margin_mm
        if self.letterhead_bottom_margin_mm:
            margins['bottom'] = self.letterhead_bottom_margin_mm
        if margins:
            kwargs['margins'] = margins
        if self.letterhead_mode == 'overlay' and self.letterhead_background_pdf:
            kwargs['background_pdf_path'] = self.letterhead_background_pdf.path
        return kwargs

    @property
    def full_address(self):
        address_parts = [self.address1, self.address2, self.address3,
                         f"{self.district_id.name}, {self.state_id.name}",
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
    pt_number = models.CharField(max_length=15, null=True, blank=True)
    pt_date = models.DateField(null=True, blank=True)
    psara = models.CharField(max_length=15, null=True, blank=True)
    psara_from = models.DateField(null=True, blank=True)
    psara_to = models.DateField(null=True, blank=True)
    factory = models.CharField(max_length=15, null=True, blank=True)
    factory_from = models.DateField(null=True, blank=True)
    factory_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=date.today)
    created_by = models.CharField(max_length=50, null=True, blank=True)
    updated_at = models.DateTimeField(default=date.today)
    updated_by = models.CharField(max_length=50, null=True, blank=True)
    

    def __str__(self):
        return f"Statutory Info for {self.company.company_name}"

    class Meta:
        db_table = 'sa_company_statury'
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
            'company_name': forms.TextInput(attrs={'placeholder': 'Company Name'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'shut_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'tagline1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tagline'}),
            'address1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address Line 1'}),
            'address2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address Line 2'}),
            'address3': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address Line 3'}),
            'state_id': forms.Select(attrs={'class': 'form-control'}),
            'district_id': forms.Select(attrs={'class': 'form-control'}),
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
            'bank_id': forms.Select(attrs={'class': 'form-control'}),
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
                      'psara', 'psara_from', 'psara_to', 'pt_number', 'pt_date']
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
                'pt_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Professional Tax Registration Number'}),
                'pt_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
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

# Company Selector Views for Associate and Operator Users
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

@login_required
def select_company(request):
    """Select default company for associate/operator user"""
    if request.method == 'POST':
        company_id = request.POST.get('company_id')
        if company_id:
            request.session['selected_company_id'] = int(company_id)
            return JsonResponse({'status': 'success', 'company_id': company_id})
    return redirect('Aapp:dashboard')

@login_required
def get_user_companies(request):
    """Get companies available to current user"""
    from Sapp.app.user import get_user_type
    
    user_type, profile = get_user_type(request.user)
    companies = []
    
    if user_type == 'associate':
        companies = list(profile.get_companies().values('company_id', 'company_name'))
    elif user_type == 'owner':
        companies = list(profile.get_companies().values('company_id', 'company_name'))
    elif user_type == 'subuser':
        companies = list(profile.get_companies().values('company_id', 'company_name'))
    
    selected_id = request.session.get('selected_company_id')
    return JsonResponse({'companies': companies, 'selected_id': selected_id})

@login_required
def get_selected_company(request):
    """Get currently selected company details"""
    company_id = request.session.get('selected_company_id')
    if company_id:
        try:
            company = Company.objects.get(company_id=company_id)
            return JsonResponse({
                'company_id': company.company_id,
                'company_name': company.company_name,
                'mobile': company.mobile,
                'email': company.email1,
                'address': company.full_address
            })
        except Company.DoesNotExist:
            pass
    return JsonResponse({'company_id': None})

@login_required
def create_company_associate(request):
    from django.contrib import messages
    from datetime import date
    
    if request.method == 'POST':
        company_name = request.POST.get('company_name')
        start_date = request.POST.get('start_date')
        mobile = request.POST.get('mobile')
        email1 = request.POST.get('email1')
        pan = request.POST.get('pan')
        
        if not all([company_name, start_date, mobile, email1, pan]):
            messages.error(request, "All required fields must be filled.")
        elif date.fromisoformat(start_date) > date.today():
            messages.error(request, "Start date cannot be in the future.")
        elif Company.objects.filter(company_name=company_name).exists():
            messages.error(request, f"Company '{company_name}' already exists.")
        elif Company.objects.filter(pan=pan).exists():
            messages.error(request, f"PAN '{pan}' already exists.")
        else:
            default_state = State.objects.first()
            default_district = District.objects.filter(state=default_state).first() if default_state else None
            
            new_company = Company.objects.create(
                company_name=company_name,
                start_date=start_date,
                mobile=mobile,
                email1=email1,
                pan=pan,
                state_id=default_state,
                district_id=default_district
            )

            user = request.user
            if hasattr(user, 'associate_profile'):
                user.associate_profile.companyid.add(new_company)
            elif hasattr(user, 'subuser_profile'):
                user.subuser_profile.companyid.add(new_company)

            messages.success(request, f"Company '{company_name}' created successfully.")
            return redirect('list_company_associate')
    
    return render(request, 'Aapp/company/create.html', {})

@login_required
def list_company_associate(request):
    user = request.user
    if hasattr(user, 'associate_profile'):
        companies = user.associate_profile.companyid.filter(shut_date__isnull=True)
    elif hasattr(user, 'subuser_profile'):
        companies = user.subuser_profile.companyid.filter(shut_date__isnull=True)
    elif user.is_superuser:
        companies = Company.objects.filter(shut_date__isnull=True)
    else:
        companies = Company.objects.none()
    return render(request, 'Aapp/company/list.html', {'companies': companies})

@login_required
def alter_company_associate(request, company_id):
    from django.contrib import messages
    from django.shortcuts import get_object_or_404
    
    company = get_object_or_404(Company, company_id=company_id)
    
    if request.method == 'POST':
        company.start_date = request.POST.get('start_date')
        company.tagline1 = request.POST.get('tagline1', '')
        company.address1 = request.POST.get('address1', '')
        company.address2 = request.POST.get('address2', '')
        company.address3 = request.POST.get('address3', '')
        company.pin = request.POST.get('pin', '')
        company.phone = request.POST.get('phone', '')
        company.phone2 = request.POST.get('phone2', '')
        company.mobile = request.POST.get('mobile')
        company.mobile2 = request.POST.get('mobile2', '')
        company.email2 = request.POST.get('email2', '')
        company.website = request.POST.get('website', '')
        company.tan = request.POST.get('tan', '')
        company.cin = request.POST.get('cin', '')
        bank_id = request.POST.get('bank_id')
        if bank_id:
            company.bank_id = bank_name.objects.get(id=bank_id)
        else:
            company.bank_id = None
        company.account = request.POST.get('account', '')
        company.ifsc = request.POST.get('ifsc', '')
        company.branch_address = request.POST.get('branch_address', '')
        company.state_id = State.objects.get(Stateid=request.POST.get('stateid'))
        company.district_id = District.objects.get(Districtid=request.POST.get('DistrictID'))
        company.updated_by = request.user.username
        company.updated_at = date.today()
        company.created_by = company.created_by or request.user.username  # Preserve original created_by
        company.created_at = company.created_at or date.today()  # Preserve original created_at
        company.save()
        messages.success(request, f"Company '{company.company_name}' updated successfully.")
        return redirect('list_company_associate')
    
    banks = bank_name.objects.all()
    states = State.objects.all()
    districts = District.objects.filter(state=company.state_id)
    return render(request, 'Aapp/company/alter.html', {
        'company': company,
        'banks': banks,
        'states': states,
        'districts': districts,
    })

@login_required
def mark_inactive_company(request, company_id):
    from django.contrib import messages
    from django.shortcuts import get_object_or_404
    from datetime import date
    
    company = get_object_or_404(Company, company_id=company_id)
    
    if request.method == 'POST':
        company.shut_date = date.today()
        company.save()
        messages.success(request, f"Company '{company.company_name}' marked as inactive.")
        return redirect('list_company_associate')
    
    return render(request, 'Aapp/company/mark_inactive.html', {'company': company})


@login_required
def create_company_statutory(request):
    from django.contrib import messages
    
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return render(request, 'Aapp/company/create_statutory.html', {})
    
    selected_company = Company.objects.get(company_id=selected_company_id)
    
    if request.method == 'POST':
        company_statury.objects.create(
            company=selected_company,
            epfo=request.POST.get('epfo', ''),
            epfo_date=request.POST.get('epfo_date') or None,
            esic=request.POST.get('esic', ''),
            esic_date=request.POST.get('esic_date') or None,
            gst=request.POST.get('gst', ''),
            gst_date=request.POST.get('gst_date') or None,
            shop_act=request.POST.get('shop_act', ''),
            shop_act_date=request.POST.get('shop_act_date') or None,
            labour=request.POST.get('labour', ''),
            labour_from=request.POST.get('labour_from') or None,
            labour_to=request.POST.get('labour_to') or None,
            psara=request.POST.get('psara', ''),
            psara_from=request.POST.get('psara_from') or None,
            psara_to=request.POST.get('psara_to') or None,
            pt_number=request.POST.get('pt_number', ''),
            pt_date=request.POST.get('pt_date') or None,
            factory=request.POST.get('factory', ''),
            factory_from=request.POST.get('factory_from') or None,
            factory_to=request.POST.get('factory_to') or None,
            created_by=request.user.username,
            updated_by=request.user.username,
            created_at=date.today(),
            updated_at=date.today(),
        )
        messages.success(request, f"Statutory details for '{selected_company.company_name}' created successfully.")
        return redirect('list_company_associate')
    
    return render(request, 'Aapp/company/create_statutory.html', {})

@login_required
def alter_company_statutory(request, company_id):
    from django.contrib import messages
    from django.shortcuts import get_object_or_404
    
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return render(request, 'Aapp/company/alter_statutory.html', {'statutory': None})
    
    company = get_object_or_404(Company, company_id=company_id)
    statutory, created = company_statury.objects.get_or_create(company=company)
    
    if request.method == 'POST':
        statutory.epfo = request.POST.get('epfo', '')
        statutory.epfo_date = request.POST.get('epfo_date') or None
        statutory.esic = request.POST.get('esic', '')
        statutory.esic_date = request.POST.get('esic_date') or None
        statutory.gst = request.POST.get('gst', '')
        statutory.gst_date = request.POST.get('gst_date') or None
        statutory.shop_act = request.POST.get('shop_act', '')
        statutory.shop_act_date = request.POST.get('shop_act_date') or None
        statutory.labour = request.POST.get('labour', '')
        statutory.labour_from = request.POST.get('labour_from') or None
        statutory.labour_to = request.POST.get('labour_to') or None
        statutory.psara = request.POST.get('psara', '')
        statutory.psara_from = request.POST.get('psara_from') or None
        statutory.psara_to = request.POST.get('psara_to') or None
        statutory.pt_number = request.POST.get('pt_number', '')
        statutory.pt_date = request.POST.get('pt_date') or None
        statutory.factory = request.POST.get('factory', '')
        statutory.factory_from = request.POST.get('factory_from') or None
        statutory.factory_to = request.POST.get('factory_to') or None
        statutory.updated_by = request.user.username
        statutory.updated_at = date.today()
        statutory.save()
        messages.success(request, f"Statutory details updated successfully.")
        return redirect('list_company_associate')
    
    return render(request, 'Aapp/company/alter_statutory.html', {'statutory': statutory})