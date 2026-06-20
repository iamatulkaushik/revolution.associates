from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from Sapp.app.company import Company
from Aapp.app.employee import employee
from Aapp.app.attandance import MONTH_CHOICES


# ── Model ─────────────────────────────────────────────────────────────────────

class bonus_record(models.Model):
    bonus_id            = models.AutoField(primary_key=True)
    company             = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee            = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID', related_name='bonuses')
    salary_month        = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    salary_year         = models.PositiveSmallIntegerField()

    # Bonus components
    basic_bonus         = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                            help_text='Statutory bonus as per Payment of Bonus Act (8.33% min)')
    performance_bonus   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    festival_bonus      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_bonus         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_bonus         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bonus_percentage    = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                            help_text='Percentage of basic wages (min 8.33%, max 20%)')

    # Bonus Act compliance fields
    gross_profit        = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                            help_text='Company gross profit for the accounting year (Form A)')
    allocable_surplus   = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                            help_text='67% of gross profit for non-banking companies (Form A)')

    reason              = models.CharField(max_length=500, blank=True)
    is_paid             = models.BooleanField(default=False)
    payment_date        = models.DateField(null=True, blank=True)
    created_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='bonus_created')
    created_date        = models.DateTimeField(auto_now_add=True)
    updated_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='bonus_updated')
    updated_date        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'bonus_record'
        unique_together = ('employee', 'salary_month', 'salary_year')
        ordering        = ['-salary_year', '-salary_month']

    def __str__(self):
        return f"{self.employee.employeecode} — Bonus {self.get_salary_month_display()} {self.salary_year}"

    def save(self, *args, **kwargs):
        self.total_bonus = round(
            float(self.basic_bonus) + float(self.performance_bonus) +
            float(self.festival_bonus) + float(self.other_bonus), 2
        )
        super().save(*args, **kwargs)


# ── Helper ────────────────────────────────────────────────────────────────────

def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Views ─────────────────────────────────────────────────────────────────────

@login_required
def list_bonus(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    records = bonus_record.objects.filter(company=company).select_related('employee')
    return render(request, 'Aapp/bonus/list_bonus.html', {'records': records, 'company': company})


@login_required
def add_bonus(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    employees = employee.objects.filter(CompanyID=company, is_working=True).order_by('name')

    if request.method == 'POST':
        p   = request.POST
        emp = get_object_or_404(employee, employeeid=p.get('employee_id'), CompanyID=company)
        month = int(p.get('salary_month', 0))
        year  = int(p.get('salary_year', 0))

        if bonus_record.objects.filter(employee=emp, salary_month=month, salary_year=year).exists():
            messages.error(request, f'Bonus for {emp.name} — {month}/{year} already exists.')
        else:
            bonus_record.objects.create(
                company=company, employee=emp,
                salary_month=month, salary_year=year,
                basic_bonus=p.get('basic_bonus', 0) or 0,
                performance_bonus=p.get('performance_bonus', 0) or 0,
                festival_bonus=p.get('festival_bonus', 0) or 0,
                other_bonus=p.get('other_bonus', 0) or 0,
                bonus_percentage=p.get('bonus_percentage', 0) or 0,
                gross_profit=p.get('gross_profit', 0) or 0,
                allocable_surplus=p.get('allocable_surplus', 0) or 0,
                reason=p.get('reason', ''),
                created_by=request.user,
            )
            messages.success(request, f'Bonus recorded for {emp.name}.')
            return redirect('Aapp:list_bonus')

    return render(request, 'Aapp/bonus/add_bonus.html', {
        'employees': employees, 'months': MONTH_CHOICES, 'company': company,
    })


@login_required
def update_bonus(request, bonus_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(bonus_record, bonus_id=bonus_id, company=company, is_paid=False)

    if request.method == 'POST':
        p = request.POST
        rec.basic_bonus       = p.get('basic_bonus', rec.basic_bonus)
        rec.performance_bonus = p.get('performance_bonus', rec.performance_bonus)
        rec.festival_bonus    = p.get('festival_bonus', rec.festival_bonus)
        rec.other_bonus       = p.get('other_bonus', rec.other_bonus)
        rec.bonus_percentage  = p.get('bonus_percentage', rec.bonus_percentage)
        rec.gross_profit      = p.get('gross_profit', rec.gross_profit)
        rec.allocable_surplus = p.get('allocable_surplus', rec.allocable_surplus)
        rec.reason            = p.get('reason', rec.reason)
        rec.updated_by        = request.user
        rec.save()
        messages.success(request, 'Bonus updated.')
        return redirect('Aapp:list_bonus')

    return render(request, 'Aapp/bonus/update_bonus.html', {'rec': rec, 'months': MONTH_CHOICES})


@login_required
def mark_bonus_paid(request, bonus_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(bonus_record, bonus_id=bonus_id, company=company)
    if request.method == 'POST':
        from datetime import date
        rec.is_paid      = True
        rec.payment_date = request.POST.get('payment_date') or date.today()
        rec.updated_by   = request.user
        rec.save()
        messages.success(request, f'Bonus marked as paid for {rec.employee.name}.')
        return redirect('Aapp:list_bonus')
    return render(request, 'Aapp/bonus/mark_bonus_paid.html', {'rec': rec})


@login_required
def delete_bonus(request, bonus_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(bonus_record, bonus_id=bonus_id, company=company, is_paid=False)
    if request.method == 'POST':
        rec.delete()
        messages.success(request, 'Bonus record deleted.')
        return redirect('Aapp:list_bonus')
    return render(request, 'Aapp/bonus/delete_bonus.html', {'rec': rec})
