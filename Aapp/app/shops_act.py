from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
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

def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Establishment Views ───────────────────────────────────────────────────────

@login_required
def list_establishments(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    estabs = establishment_details.objects.filter(company=company)
    return render(request, 'Aapp/shops_act/list_establishments.html', {
        'estabs': estabs, 'company': company,
    })


@login_required
def add_establishment(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    if request.method == 'POST':
        p = request.POST
        establishment_details.objects.create(
            company=company,
            establishment_name=p.get('establishment_name'),
            registration_number=p.get('registration_number', ''),
            registration_date=p.get('registration_date') or None,
            renewal_date=p.get('renewal_date') or None,
            opening_time=p.get('opening_time'),
            closing_time=p.get('closing_time'),
            daily_work_hours=p.get('daily_work_hours', 8.0),
            weekly_work_hours=p.get('weekly_work_hours', 48.0),
            weekly_off_day=p.get('weekly_off_day', 'sunday'),
            second_off_day=p.get('second_off_day', ''),
            ot_rate_type=p.get('ot_rate_type', 'double'),
            max_ot_hours_day=p.get('max_ot_hours_day', 2.0),
            max_ot_hours_week=p.get('max_ot_hours_week', 10.0),
            address=p.get('address', ''),
            manager_name=p.get('manager_name', ''),
            manager_mobile=p.get('manager_mobile', ''),
            created_by=request.user,
        )
        messages.success(request, 'Establishment registered.')
        return redirect('Aapp:list_establishments')

    return render(request, 'Aapp/shops_act/add_establishment.html', {
        'weekly_off_choices': WEEKLY_OFF_CHOICES,
        'ot_rate_choices': OT_RATE_CHOICES,
        'company': company,
    })


@login_required
def update_establishment(request, estab_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    estab = get_object_or_404(establishment_details, estab_id=estab_id, company=company)

    if request.method == 'POST':
        p = request.POST
        estab.establishment_name  = p.get('establishment_name', estab.establishment_name)
        estab.registration_number = p.get('registration_number', estab.registration_number)
        estab.registration_date   = p.get('registration_date') or estab.registration_date
        estab.renewal_date        = p.get('renewal_date') or estab.renewal_date
        estab.opening_time        = p.get('opening_time', estab.opening_time)
        estab.closing_time        = p.get('closing_time', estab.closing_time)
        estab.daily_work_hours    = p.get('daily_work_hours', estab.daily_work_hours)
        estab.weekly_work_hours   = p.get('weekly_work_hours', estab.weekly_work_hours)
        estab.weekly_off_day      = p.get('weekly_off_day', estab.weekly_off_day)
        estab.second_off_day      = p.get('second_off_day', estab.second_off_day)
        estab.ot_rate_type        = p.get('ot_rate_type', estab.ot_rate_type)
        estab.max_ot_hours_day    = p.get('max_ot_hours_day', estab.max_ot_hours_day)
        estab.max_ot_hours_week   = p.get('max_ot_hours_week', estab.max_ot_hours_week)
        estab.address             = p.get('address', estab.address)
        estab.manager_name        = p.get('manager_name', estab.manager_name)
        estab.manager_mobile      = p.get('manager_mobile', estab.manager_mobile)
        estab.updated_by          = request.user
        estab.save()
        messages.success(request, 'Establishment updated.')
        return redirect('Aapp:list_establishments')

    return render(request, 'Aapp/shops_act/update_establishment.html', {
        'estab': estab,
        'weekly_off_choices': WEEKLY_OFF_CHOICES,
        'ot_rate_choices': OT_RATE_CHOICES,
    })


@login_required
def delete_establishment(request, estab_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    estab = get_object_or_404(establishment_details, estab_id=estab_id, company=company)
    if request.method == 'POST':
        estab.delete()
        messages.success(request, 'Establishment deleted.')
        return redirect('Aapp:list_establishments')
    return render(request, 'Aapp/shops_act/delete_establishment.html', {'estab': estab})


# ── Overtime Register Views ───────────────────────────────────────────────────

@login_required
def list_overtime(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    records = overtime_register.objects.filter(company=company).select_related('employee', 'establishment')
    return render(request, 'Aapp/shops_act/list_overtime.html', {
        'records': records, 'company': company,
    })


@login_required
def add_overtime(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    employees = employee.objects.filter(CompanyID=company, is_working=True).order_by('name')
    estabs    = establishment_details.objects.filter(company=company)

    if request.method == 'POST':
        p   = request.POST
        emp = get_object_or_404(employee, employeeid=p.get('employee_id'), CompanyID=company)
        overtime_register.objects.create(
            company=company,
            establishment_id=p.get('establishment_id') or None,
            employee=emp,
            salary_month=int(p.get('salary_month', 0)),
            salary_year=int(p.get('salary_year', 0)),
            ot_date=p.get('ot_date'),
            ot_hours=p.get('ot_hours', 0),
            ot_reason=p.get('ot_reason', ''),
            created_by=request.user,
        )
        messages.success(request, 'Overtime recorded.')
        return redirect('Aapp:list_overtime')

    return render(request, 'Aapp/shops_act/add_overtime.html', {
        'employees': employees, 'estabs': estabs,
        'months': MONTH_CHOICES, 'company': company,
    })


@login_required
def delete_overtime(request, ot_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(overtime_register, ot_id=ot_id, company=company)
    if request.method == 'POST':
        rec.delete()
        messages.success(request, 'Overtime record deleted.')
        return redirect('Aapp:list_overtime')
    return render(request, 'Aapp/shops_act/delete_overtime.html', {'rec': rec})
