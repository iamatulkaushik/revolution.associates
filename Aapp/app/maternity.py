from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from Sapp.app.company import Company
from Aapp.app.employee import employee
from Aapp.app.branch_department import department
from Aapp.app.attandance import MONTH_CHOICES


MATERNITY_STATUS_CHOICES = [
    ('applied',     'Applied'),
    ('approved',    'Approved'),
    ('on_leave',    'On Leave'),
    ('returned',    'Returned'),
    ('rejected',    'Rejected'),
]


# ── Model ─────────────────────────────────────────────────────────────────────

class maternity_record(models.Model):
    """
    Maternity Benefit Act 1961 — Register of Women Workers (Form A).
    Applicable to female employees only.
    """
    maternity_id            = models.AutoField(primary_key=True)
    company                 = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee                = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID',
                                related_name='maternity_records',
                                limit_choices_to={'gender': 'Female'})
    department              = models.ForeignKey(department, on_delete=models.SET_NULL, null=True, blank=True,
                                db_column='DepartmentID')

    # Employment details at time of application
    date_of_joining         = models.DateField(help_text='Auto-filled from employee record')
    salary_month            = models.PositiveSmallIntegerField(choices=MONTH_CHOICES,
                                help_text='Month of application')
    salary_year             = models.PositiveSmallIntegerField(help_text='Year of application')

    # Maternity details
    expected_delivery_date  = models.DateField()
    actual_delivery_date    = models.DateField(null=True, blank=True)
    maternity_leave_start   = models.DateField(help_text='Max 8 weeks before expected delivery')
    maternity_leave_end     = models.DateField(help_text='Total 26 weeks for first 2 children, 12 weeks thereafter')
    actual_return_date      = models.DateField(null=True, blank=True)

    # Benefits
    daily_wage_rate         = models.DecimalField(max_digits=10, decimal_places=2,
                                help_text='Average daily wage for benefit calculation')
    maternity_benefit_days  = models.PositiveIntegerField(default=0,
                                help_text='Number of days benefit is payable')
    maternity_benefit_amount= models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                help_text='daily_wage_rate × maternity_benefit_days')
    medical_bonus           = models.DecimalField(max_digits=10, decimal_places=2, default=3500,
                                help_text='Medical bonus ₹3500 as per Act (if no prenatal care provided)')
    nursing_breaks          = models.BooleanField(default=True,
                                help_text='Two nursing breaks per day until child is 15 months old')

    status                  = models.CharField(max_length=15, choices=MATERNITY_STATUS_CHOICES, default='applied')
    remarks                 = models.CharField(max_length=500, blank=True)
    is_paid                 = models.BooleanField(default=False)
    payment_date            = models.DateField(null=True, blank=True)

    created_by              = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='maternity_created')
    created_date            = models.DateTimeField(auto_now_add=True)
    updated_by              = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='maternity_updated')
    updated_date            = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'maternity_record'
        unique_together = ('employee', 'expected_delivery_date')
        ordering        = ['-maternity_leave_start']

    def __str__(self):
        return f"{self.employee.name} — Maternity {self.maternity_leave_start} to {self.maternity_leave_end}"

    def save(self, *args, **kwargs):
        if self.maternity_benefit_days and self.daily_wage_rate:
            self.maternity_benefit_amount = round(
                float(self.daily_wage_rate) * self.maternity_benefit_days, 2
            )
        super().save(*args, **kwargs)

    @staticmethod
    def calculate_leave_days(start, end):
        if start and end:
            return (end - start).days + 1
        return 0


# ── Helper ────────────────────────────────────────────────────────────────────

def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Views ─────────────────────────────────────────────────────────────────────

@login_required
def list_maternity(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    records = maternity_record.objects.filter(company=company).select_related('employee', 'department')
    return render(request, 'Aapp/maternity/list_maternity.html', {
        'records': records, 'company': company,
    })


@login_required
def add_maternity(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    # Only female employees
    employees   = employee.objects.filter(CompanyID=company, is_working=True, gender='Female').order_by('name')
    departments = department.objects.filter(companyid=company)

    if request.method == 'POST':
        p   = request.POST
        emp = get_object_or_404(employee, employeeid=p.get('employee_id'), CompanyID=company, gender='Female')

        leave_start = p.get('maternity_leave_start')
        leave_end   = p.get('maternity_leave_end')
        daily_rate  = float(p.get('daily_wage_rate', 0))

        from datetime import date as dt
        from datetime import datetime
        start_dt = datetime.strptime(leave_start, '%Y-%m-%d').date() if leave_start else None
        end_dt   = datetime.strptime(leave_end, '%Y-%m-%d').date() if leave_end else None
        days     = maternity_record.calculate_leave_days(start_dt, end_dt)

        maternity_record.objects.create(
            company=company,
            employee=emp,
            department_id=p.get('department_id') or None,
            date_of_joining=emp.dateofjoining,
            salary_month=int(p.get('salary_month', 0)),
            salary_year=int(p.get('salary_year', 0)),
            expected_delivery_date=p.get('expected_delivery_date'),
            maternity_leave_start=leave_start,
            maternity_leave_end=leave_end,
            daily_wage_rate=daily_rate,
            maternity_benefit_days=days,
            medical_bonus=p.get('medical_bonus', 3500),
            nursing_breaks=p.get('nursing_breaks') == 'on',
            status=p.get('status', 'applied'),
            remarks=p.get('remarks', ''),
            created_by=request.user,
        )
        messages.success(request, f'Maternity record created for {emp.name}.')
        return redirect('Aapp:list_maternity')

    return render(request, 'Aapp/maternity/add_maternity.html', {
        'employees': employees, 'departments': departments,
        'months': MONTH_CHOICES, 'statuses': MATERNITY_STATUS_CHOICES,
        'company': company,
    })


@login_required
def update_maternity(request, maternity_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(maternity_record, maternity_id=maternity_id, company=company)

    if request.method == 'POST':
        p = request.POST
        rec.expected_delivery_date  = p.get('expected_delivery_date', rec.expected_delivery_date)
        rec.actual_delivery_date    = p.get('actual_delivery_date') or rec.actual_delivery_date
        rec.maternity_leave_start   = p.get('maternity_leave_start', rec.maternity_leave_start)
        rec.maternity_leave_end     = p.get('maternity_leave_end', rec.maternity_leave_end)
        rec.actual_return_date      = p.get('actual_return_date') or rec.actual_return_date
        rec.daily_wage_rate         = p.get('daily_wage_rate', rec.daily_wage_rate)
        rec.medical_bonus           = p.get('medical_bonus', rec.medical_bonus)
        rec.nursing_breaks          = p.get('nursing_breaks') == 'on'
        rec.status                  = p.get('status', rec.status)
        rec.remarks                 = p.get('remarks', rec.remarks)
        rec.updated_by              = request.user

        from datetime import datetime
        start_dt = datetime.strptime(str(rec.maternity_leave_start), '%Y-%m-%d').date()
        end_dt   = datetime.strptime(str(rec.maternity_leave_end), '%Y-%m-%d').date()
        rec.maternity_benefit_days = maternity_record.calculate_leave_days(start_dt, end_dt)
        rec.save()
        messages.success(request, 'Maternity record updated.')
        return redirect('Aapp:list_maternity')

    return render(request, 'Aapp/maternity/update_maternity.html', {
        'rec': rec,
        'months': MONTH_CHOICES,
        'statuses': MATERNITY_STATUS_CHOICES,
    })


@login_required
def mark_maternity_paid(request, maternity_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(maternity_record, maternity_id=maternity_id, company=company)
    if request.method == 'POST':
        from datetime import date
        rec.is_paid      = True
        rec.payment_date = request.POST.get('payment_date') or date.today()
        rec.status       = 'on_leave'
        rec.updated_by   = request.user
        rec.save()
        messages.success(request, f'Maternity benefit paid for {rec.employee.name}.')
        return redirect('Aapp:list_maternity')
    return render(request, 'Aapp/maternity/mark_maternity_paid.html', {'rec': rec})


@login_required
def delete_maternity(request, maternity_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(maternity_record, maternity_id=maternity_id, company=company)
    if request.method == 'POST':
        rec.delete()
        messages.success(request, 'Maternity record deleted.')
        return redirect('Aapp:list_maternity')
    return render(request, 'Aapp/maternity/delete_maternity.html', {'rec': rec})
