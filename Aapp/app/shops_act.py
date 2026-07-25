from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from Sapp.app.company import Company
from Aapp.app.employee import employee
from Aapp.app.attandance import MONTH_CHOICES


WEEKLY_OFF_CHOICES = [
    ('sunday',      'Sunday'),
    ('monday',      'Monday'),
    ('tuesday',     'Tuesday'),
    ('wednesday',   'Wednesday'),
    ('thursday',    'Thursday'),
    ('friday',      'Friday'),
    ('saturday',    'Saturday'),
]

OT_RATE_CHOICES = [
    ('single',  'Single Rate'),
    ('double',  'Double Rate (Statutory)'),
]


# ── Models ────────────────────────────────────────────────────────────────────

class establishment_details(models.Model):
    """
    Shops & Commercial Establishments Act — Establishment Register.
    One record per company branch/location.
    """
    estab_id            = models.AutoField(primary_key=True)
    company             = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    establishment_name  = models.CharField(max_length=255,
                            help_text='Name as registered under Shops & Establishments Act')
    registration_number = models.CharField(max_length=50, blank=True,
                            help_text='Shop Act registration number')
    registration_date   = models.DateField(null=True, blank=True)
    renewal_date        = models.DateField(null=True, blank=True)

    # Working hours
    opening_time        = models.TimeField(help_text='Daily opening time')
    closing_time        = models.TimeField(help_text='Daily closing time')
    daily_work_hours    = models.DecimalField(max_digits=4, decimal_places=2, default=8.0,
                            help_text='Standard working hours per day (max 9 hrs as per Act)')
    weekly_work_hours   = models.DecimalField(max_digits=5, decimal_places=2, default=48.0,
                            help_text='Standard working hours per week (max 48 hrs as per Act)')

    # Off days
    weekly_off_day      = models.CharField(max_length=15, choices=WEEKLY_OFF_CHOICES, default='sunday')
    second_off_day      = models.CharField(max_length=15, choices=WEEKLY_OFF_CHOICES, blank=True,
                            help_text='Second weekly off if applicable')

    # Overtime
    ot_rate_type        = models.CharField(max_length=10, choices=OT_RATE_CHOICES, default='double')
    max_ot_hours_day    = models.DecimalField(max_digits=4, decimal_places=2, default=2.0,
                            help_text='Max overtime hours per day allowed')
    max_ot_hours_week   = models.DecimalField(max_digits=5, decimal_places=2, default=10.0,
                            help_text='Max overtime hours per week allowed')

    address             = models.TextField(blank=True)
    manager_name        = models.CharField(max_length=255, blank=True,
                            help_text='Manager/Occupier name as per registration')
    manager_mobile      = models.CharField(max_length=15, blank=True)

    created_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='estab_created')
    created_date        = models.DateTimeField(auto_now_add=True)
    updated_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='estab_updated')
    updated_date        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'establishment_details'
        unique_together = ('company', 'registration_number')
        ordering        = ['establishment_name']

    def __str__(self):
        return f"{self.establishment_name} — {self.company.company_name}"


class overtime_register(models.Model):
    """
    Overtime register as required under Shops & Establishments Act.
    Linked to attendance for the month.
    """
    ot_id           = models.AutoField(primary_key=True)
    company         = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    establishment   = models.ForeignKey(establishment_details, on_delete=models.SET_NULL, null=True, blank=True,
                        related_name='ot_records')
    employee        = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID',
                        related_name='ot_records')
    salary_month    = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    salary_year     = models.PositiveSmallIntegerField()
    ot_date         = models.DateField()
    ot_hours        = models.DecimalField(max_digits=5, decimal_places=2)
    ot_reason       = models.CharField(max_length=255, blank=True)
    ot_wages        = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                        help_text='Auto-calculated when wages are generated')
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ot_created')
    created_date    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'overtime_register'
        ordering = ['-ot_date']

    def __str__(self):
        return f"{self.employee.employeecode} — OT {self.ot_hours}hrs on {self.ot_date}"


# ── Helper ────────────────────────────────────────────────────────────────────

from django import forms as _saforms

class EstablishmentForm(_saforms.ModelForm):
    class Meta:
        model = establishment_details
        fields = ['establishment_name', 'registration_number', 'registration_date',
                  'renewal_date', 'manager_name', 'manager_mobile', 'address',
                  'daily_work_hours', 'weekly_work_hours', 'weekly_off_day',
                  'opening_time', 'closing_time']
        widgets = {
            'registration_date': _saforms.DateInput(attrs={'type': 'date'}),
            'renewal_date': _saforms.DateInput(attrs={'type': 'date'}),
        }

class OvertimeRegisterForm(_saforms.ModelForm):
    class Meta:
        model = overtime_register
        fields = ['employee', 'salary_month', 'salary_year', 'ot_date',
                  'ot_hours', 'ot_reason', 'ot_wages']
        widgets = {'ot_date': _saforms.DateInput(attrs={'type': 'date'})}


def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Establishment Views (Punjab Shops Act — Form F / G) ──────────────────────

@login_required
def list_establishments(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')
    estabs = establishment_details.objects.filter(company=company)
    rows = [{
        'cells': [e.registration_number or '—', e.establishment_name, e.manager_name or '—',
                  e.registration_date, e.renewal_date or '—'],
        'actions': [
            {'url': reverse('update_establishment', args=[e.estab_id]), 'label': 'Edit', 'css': 'edit'},
            {'url': reverse('delete_establishment', args=[e.estab_id]), 'label': 'Delete', 'css': 'delete'},
        ],
    } for e in estabs]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Punjab Shops & Establishments Act 1958 (Haryana) — Establishments (Form F)',
        'columns': ['Reg. No.', 'Establishment', 'Manager', 'Reg. Date', 'Renewal Due'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_establishment'), 'add_label': 'Register Establishment',
        'extra_links': [{'url': reverse('list_overtime'), 'label': 'Overtime Register'}],
        'empty_message': 'No establishments registered.',
    })


@login_required
def add_establishment(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        form = EstablishmentForm(request.POST)
        if form.is_valid():
            est = form.save(commit=False)
            est.company = company
            est.created_by = request.user
            est.save()
            messages.success(request, 'Establishment registered.')
            return redirect('list_establishments')
    else:
        form = EstablishmentForm()

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': 'Register Establishment (Shops Act — Form F)',
        'cancel_url': reverse('list_establishments'),
    })


@login_required
def update_establishment(request, estab_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    est = get_object_or_404(establishment_details, estab_id=estab_id, company=company)

    if request.method == 'POST':
        form = EstablishmentForm(request.POST, instance=est)
        if form.is_valid():
            form.save()
            messages.success(request, 'Establishment updated.')
            return redirect('list_establishments')
    else:
        form = EstablishmentForm(instance=est)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': f'Edit Establishment — {est.establishment_name}',
        'cancel_url': reverse('list_establishments'),
    })


@login_required
def delete_establishment(request, estab_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    est = get_object_or_404(establishment_details, estab_id=estab_id, company=company)
    if request.method == 'POST':
        est.delete()
        messages.success(request, 'Establishment deleted.')
        return redirect('list_establishments')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Delete Establishment',
        'confirm_message': f'Delete establishment <strong>{est.establishment_name} ({est.registration_number})</strong>?',
        'cancel_url': reverse('list_establishments'),
    })


# ── Overtime Register Views (Form IV) ────────────────────────────────────────

@login_required
def list_overtime(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')
    records = overtime_register.objects.filter(
        employee__CompanyID=company
    ).select_related('employee')
    rows = [{
        'cells': [r.employee.name, r.ot_date, r.ot_hours, r.ot_reason or '—',
                  r.ot_wages, f'{r.salary_month}/{r.salary_year}'],
        'actions': [{'url': reverse('delete_overtime', args=[r.ot_id]), 'label': 'Delete', 'css': 'delete'}],
    } for r in records]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Shops Act / Minimum Wages Act — Overtime Register (Form IV)',
        'columns': ['Employee', 'OT Date', 'OT Hours', 'Reason', 'OT Wages Paid', 'Month/Year'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_overtime'), 'add_label': 'Add Overtime Record',
        'empty_message': 'No overtime records yet.',
    })


@login_required
def add_overtime(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        form = OvertimeRegisterForm(request.POST)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.save()
            messages.success(request, 'Overtime record added.')
            return redirect('list_overtime')
    else:
        form = OvertimeRegisterForm()
        form.fields['employee'].queryset = employee.objects.filter(CompanyID=company, is_working=True)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': 'Add Overtime Record (Form IV)',
        'cancel_url': reverse('list_overtime'),
    })


@login_required
def delete_overtime(request, ot_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    rec = get_object_or_404(overtime_register, ot_id=ot_id, employee__CompanyID=company)
    if request.method == 'POST':
        rec.delete()
        messages.success(request, 'Overtime record deleted.')
        return redirect('list_overtime')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Delete Overtime Record',
        'confirm_message': f'Delete overtime record for <strong>{rec.employee.name}</strong> on {rec.ot_date} ({rec.ot_hours} hrs)?',
        'cancel_url': reverse('list_overtime'),
    })
