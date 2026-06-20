from django import forms
from django.db import models
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from Sapp.app.company import Company
from Aapp.app.employee import employee


# ── Models ───────────────────────────────────────────────────────────────────

class FactoryRegistration(models.Model):
    factory_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    factory_license_no = models.CharField(max_length=100, unique=True)
    occupier_name = models.CharField(max_length=255)
    manager_name = models.CharField(max_length=255)
    factory_area_sqm = models.DecimalField(max_digits=10, decimal_places=2)
    total_hp_used = models.DecimalField(max_digits=10, decimal_places=2)
    max_workers_day = models.IntegerField()
    max_workers_night = models.IntegerField()
    license_expiry_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'factory_registration'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.factory_license_no} - {self.company.company_name}"


class FactoryWhitewashRegister(models.Model):
    whitewash_id = models.AutoField(primary_key=True)
    factory = models.ForeignKey(FactoryRegistration, on_delete=models.CASCADE, related_name='whitewash_records')
    area_description = models.TextField()
    type_of_work = models.CharField(max_length=100)
    date_done = models.DateField()
    next_due_date = models.DateField()
    contractor_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'factory_whitewash_register'
        ordering = ['-date_done']

    def __str__(self):
        return f"{self.factory.factory_license_no} - {self.area_description[:50]}"


class FactoryVesselExamination(models.Model):
    vessel_id = models.AutoField(primary_key=True)
    factory = models.ForeignKey(FactoryRegistration, on_delete=models.CASCADE, related_name='vessel_examinations')
    vessel_description = models.TextField()
    exam_date = models.DateField()
    examiner_name = models.CharField(max_length=255)
    max_permissible_pressure = models.DecimalField(max_digits=10, decimal_places=2)
    is_fit_for_use = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'factory_vessel_examination'
        ordering = ['-exam_date']

    def __str__(self):
        return f"{self.factory.factory_license_no} - {self.vessel_description[:50]}"


class LeaveWithWagesRegister(models.Model):
    leave_register_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(employee, on_delete=models.CASCADE, related_name='leave_wages_records')
    year = models.IntegerField()
    opening_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    leave_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    leave_availed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    leave_lapsed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    leave_encashed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    encashment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'leave_with_wages_register'
        ordering = ['-year', 'employee']
        unique_together = ['employee', 'year']

    def __str__(self):
        return f"{self.employee.name} - {self.year}"


class FactoryAccidentRegister(models.Model):
    accident_id = models.AutoField(primary_key=True)
    factory = models.ForeignKey(FactoryRegistration, on_delete=models.CASCADE, related_name='accidents')
    employee = models.ForeignKey(employee, on_delete=models.CASCADE, related_name='factory_accidents', null=True, blank=True)
    accident_date = models.DateField()
    nature_of_accident = models.CharField(max_length=255)
    injury_description = models.TextField()
    is_fatal = models.BooleanField(default=False)
    days_lost = models.IntegerField(default=0)
    reported_to_dish = models.BooleanField(default=False)
    dish_reference_no = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'factory_accident_register'
        ordering = ['-accident_date']

    def __str__(self):
        return f"{self.factory.factory_license_no} - {self.accident_date}"


class FactoryAnnualReturn(models.Model):
    return_id = models.AutoField(primary_key=True)
    factory = models.ForeignKey(FactoryRegistration, on_delete=models.CASCADE, related_name='annual_returns')
    year = models.IntegerField()
    total_workers_male = models.IntegerField(default=0)
    total_workers_female = models.IntegerField(default=0)
    total_man_days = models.IntegerField(default=0)
    total_overtime_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_accidents = models.IntegerField(default=0)
    total_wages_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    filing_status = models.CharField(max_length=50, choices=[
        ('Draft', 'Draft'),
        ('Filed', 'Filed'),
        ('Acknowledged', 'Acknowledged')
    ], default='Draft')
    acknowledgement_no = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'factory_annual_return'
        ordering = ['-year']
        unique_together = ['factory', 'year']

    def __str__(self):
        return f"{self.factory.factory_license_no} - {self.year}"


# ── Forms ────────────────────────────────────────────────────────────────────

class FactoryRegistrationForm(forms.ModelForm):
    class Meta:
        model = FactoryRegistration
        fields = ['factory_license_no', 'occupier_name', 'manager_name', 'factory_area_sqm',
                  'total_hp_used', 'max_workers_day', 'max_workers_night', 'license_expiry_date']
        widgets = {
            'license_expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }


class FactoryWhitewashRegisterForm(forms.ModelForm):
    class Meta:
        model = FactoryWhitewashRegister
        fields = ['area_description', 'type_of_work', 'date_done', 'next_due_date', 'contractor_name']
        widgets = {
            'date_done': forms.DateInput(attrs={'type': 'date'}),
            'next_due_date': forms.DateInput(attrs={'type': 'date'}),
        }


class FactoryVesselExaminationForm(forms.ModelForm):
    class Meta:
        model = FactoryVesselExamination
        fields = ['vessel_description', 'exam_date', 'examiner_name', 'max_permissible_pressure', 'is_fit_for_use']
        widgets = {
            'exam_date': forms.DateInput(attrs={'type': 'date'}),
        }


class LeaveWithWagesRegisterForm(forms.ModelForm):
    class Meta:
        model = LeaveWithWagesRegister
        fields = ['employee', 'year', 'opening_balance', 'leave_earned', 'leave_availed',
                  'leave_lapsed', 'leave_encashed', 'encashment_amount']


class FactoryAccidentRegisterForm(forms.ModelForm):
    class Meta:
        model = FactoryAccidentRegister
        fields = ['employee', 'accident_date', 'nature_of_accident', 'injury_description',
                  'is_fatal', 'days_lost', 'reported_to_dish', 'dish_reference_no']
        widgets = {
            'accident_date': forms.DateInput(attrs={'type': 'date'}),
        }


class FactoryAnnualReturnForm(forms.ModelForm):
    class Meta:
        model = FactoryAnnualReturn
        fields = ['year', 'total_workers_male', 'total_workers_female', 'total_man_days',
                  'total_overtime_hours', 'total_accidents', 'total_wages_paid',
                  'filing_status', 'acknowledgement_no']


# ── Helpers ──────────────────────────────────────────────────────────────────

def _company_ctx(request):
    cid = request.session.get('selected_company_id')
    if not cid:
        return None
    return Company.objects.filter(company_id=cid).first()


# ── Factory Registration Views ───────────────────────────────────────────────

@login_required
def list_factory_registration(request):
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    factories = FactoryRegistration.objects.filter(company=company)
    return render(request, 'Aapp/factory_act/list_factory_registration.html',
                  {'factories': factories, 'company': company})


@login_required
def create_factory_registration(request):
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = FactoryRegistrationForm(request.POST)
        if form.is_valid():
            factory = form.save(commit=False)
            factory.company = company
            factory.save()
            messages.success(request, f"Factory '{factory.factory_license_no}' registered successfully.")
            return redirect('Aapp:list_factory_registration')
    else:
        form = FactoryRegistrationForm()

    return render(request, 'Aapp/factory_act/create_factory_registration.html',
                  {'form': form, 'company': company})


@login_required
def alter_factory_registration(request, factory_id):
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    factory = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)

    if request.method == 'POST':
        form = FactoryRegistrationForm(request.POST, instance=factory)
        if form.is_valid():
            form.save()
            messages.success(request, f"Factory '{factory.factory_license_no}' updated successfully.")
            return redirect('Aapp:list_factory_registration')
    else:
        form = FactoryRegistrationForm(instance=factory)

    return render(request, 'Aapp/factory_act/alter_factory_registration.html',
                  {'form': form, 'factory': factory, 'company': company})


# ── Whitewash Register Views ─────────────────────────────────────────────────

@login_required
def list_whitewash_register(request, factory_id):
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    factory = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)
    records = FactoryWhitewashRegister.objects.filter(factory=factory)
    return render(request, 'Aapp/factory_act/list_whitewash_register.html',
                  {'records': records, 'factory': factory, 'company': company})


@login_required
def create_whitewash_register(request, factory_id):
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    factory = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)

    if request.method == 'POST':
        form = FactoryWhitewashRegisterForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.factory = factory
            record.save()
            messages.success(request, 'Whitewash record created successfully.')
            return redirect('Aapp:list_whitewash_register', factory_id=factory_id)
    else:
        form = FactoryWhitewashRegisterForm()

    return render(request, 'Aapp/factory_act/create_whitewash_register.html',
                  {'form': form, 'factory': factory, 'company': company})


# ── Vessel Examination Views ─────────────────────────────────────────────────

@login_required
def list_vessel_examination(request, factory_id):
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    factory = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)
    records = FactoryVesselExamination.objects.filter(factory=factory)
    return render(request, 'Aapp/factory_act/list_vessel_examination.html',
                  {'records': records, 'factory': factory, 'company': company})


@login_required
def create_vessel_examination(request, factory_id):
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    factory = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)

    if request.method == 'POST':
        form = FactoryVesselExaminationForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.factory = factory
            record.save()
            messages.success(request, 'Vessel examination record created successfully.')
            return redirect('Aapp:list_vessel_examination', factory_id=factory_id)
    else:
        form = FactoryVesselExaminationForm()

    return render(request, 'Aapp/factory_act/create_vessel_examination.html',
                  {'form': form, 'factory': factory, 'company': company})


# ── Leave With Wages Register Views ──────────────────────────────────────────

@login_required
def list_leave_wages_register(request):
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    records = LeaveWithWagesRegister.objects.filter(employee__CompanyID=company).select_related('employee')
    return render(request, 'Aapp/factory_act/list_leave_wages_register.html',
                  {'records': records, 'company': company})


@login_required
def create_leave_wages_register(request):
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = LeaveWithWagesRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Leave with wages record created successfully.')
            return redirect('Aapp:list_leave_wages_register')
    else:
        form = LeaveWithWagesRegisterForm()
        form.fields['employee'].queryset = employee.objects.filter(CompanyID=company)

    return render(request, 'Aapp/factory_act/create_leave_wages_register.html',
                  {'form': form, 'company': company})


# ── Accident Register Views ──────────────────────────────────────────────────

@login_required
def list_accident_register(request, factory_id):
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    factory = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)
    records = FactoryAccidentRegister.objects.filter(factory=factory).select_related('employee')
    return render(request, 'Aapp/factory_act/list_accident_register.html',
                  {'records': records, 'factory': factory, 'company': company})


@login_required
def create_accident_register(request, factory_id):
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    factory = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)

    if request.method == 'POST':
        form = FactoryAccidentRegisterForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.factory = factory
            record.save()
            messages.success(request, 'Accident record created successfully.')
            return redirect('Aapp:list_accident_register', factory_id=factory_id)
    else:
        form = FactoryAccidentRegisterForm()
        form.fields['employee'].queryset = employee.objects.filter(CompanyID=company)

    return render(request, 'Aapp/factory_act/create_accident_register.html',
                  {'form': form, 'factory': factory, 'company': company})


# ── Annual Return Views ──────────────────────────────────────────────────────

@login_required
def list_annual_return(request, factory_id):
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    factory = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)
    records = FactoryAnnualReturn.objects.filter(factory=factory)
    return render(request, 'Aapp/factory_act/list_annual_return.html',
                  {'records': records, 'factory': factory, 'company': company})


@login_required
def create_annual_return(request, factory_id):
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    factory = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)

    if request.method == 'POST':
        form = FactoryAnnualReturnForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.factory = factory
            record.save()
            messages.success(request, 'Annual return created successfully.')
            return redirect('Aapp:list_annual_return', factory_id=factory_id)
    else:
        form = FactoryAnnualReturnForm()

    return render(request, 'Aapp/factory_act/create_annual_return.html',
                  {'form': form, 'factory': factory, 'company': company})


@login_required
def alter_annual_return(request, return_id):
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    record = get_object_or_404(FactoryAnnualReturn, return_id=return_id, factory__company=company)

    if request.method == 'POST':
        form = FactoryAnnualReturnForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, 'Annual return updated successfully.')
            return redirect('Aapp:list_annual_return', factory_id=record.factory.factory_id)
    else:
        form = FactoryAnnualReturnForm(instance=record)

    return render(request, 'Aapp/factory_act/alter_annual_return.html',
                  {'form': form, 'record': record, 'company': company})
