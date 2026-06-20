from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from Sapp.app.company import Company
from Aapp.app.employee import employee
from Aapp.app.designation import designation
from Aapp.app.attandance import attendance, MONTH_CHOICES


DEDUCTION_TYPE_CHOICES = [
    ('epf',             'EPF'),
    ('esi',             'ESI'),
    ('professional_tax','Professional Tax'),
    ('income_tax',      'Income Tax'),
    ('labour_welfare',  'Labour Welfare Fund'),
    ('advance',         'Advance Recovery'),
    ('fine',            'Fine'),
    ('other',           'Other'),
]


# ── Models ────────────────────────────────────────────────────────────────────

class wages_record(models.Model):
    wages_id        = models.AutoField(primary_key=True)
    company         = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee        = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID', related_name='wages')
    attendance      = models.OneToOneField(attendance, on_delete=models.SET_NULL, null=True, blank=True, db_column='AttendanceID', related_name='wages')
    salary_month    = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    salary_year     = models.PositiveSmallIntegerField()
    working_days    = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overtime_hours  = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    # Earnings — pulled from designation at time of generation
    basic_wages     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    da              = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hra             = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    overtime_wages  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_earnings  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gross_wages     = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Deductions — pulled from designation at time of generation
    epf_deduction           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    esi_deduction           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    professional_tax        = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    income_tax              = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    labour_welfare          = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_deductions        = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_deductions        = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    net_wages       = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_finalized    = models.BooleanField(default=False)
    remarks         = models.CharField(max_length=255, blank=True)
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='wages_created')
    created_date    = models.DateTimeField(auto_now_add=True)
    updated_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='wages_updated')
    updated_date    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'wages_record'
        unique_together = ('employee', 'salary_month', 'salary_year')
        ordering        = ['-salary_year', '-salary_month']

    def __str__(self):
        return f"{self.employee.employeecode} — {self.get_salary_month_display()} {self.salary_year}"


class wages_fine(models.Model):
    fine_id         = models.AutoField(primary_key=True)
    company         = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee        = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID', related_name='fines')
    wages_record    = models.ForeignKey(wages_record, on_delete=models.SET_NULL, null=True, blank=True, related_name='fines')
    fine_date       = models.DateField()
    fine_amount     = models.DecimalField(max_digits=10, decimal_places=2)
    fine_reason     = models.CharField(max_length=500)
    salary_month    = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    salary_year     = models.PositiveSmallIntegerField()
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='fines_created')
    created_date    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wages_fine'
        ordering = ['-fine_date']

    def __str__(self):
        return f"{self.employee.employeecode} — Fine ₹{self.fine_amount} on {self.fine_date}"


class wages_deduction(models.Model):
    deduction_id    = models.AutoField(primary_key=True)
    company         = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee        = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID', related_name='extra_deductions')
    wages_record    = models.ForeignKey(wages_record, on_delete=models.SET_NULL, null=True, blank=True, related_name='extra_deductions')
    deduction_type  = models.CharField(max_length=30, choices=DEDUCTION_TYPE_CHOICES)
    deduction_amount= models.DecimalField(max_digits=10, decimal_places=2)
    reason          = models.CharField(max_length=500)
    salary_month    = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    salary_year     = models.PositiveSmallIntegerField()
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='deductions_created')
    created_date    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wages_deduction'
        ordering = ['-salary_year', '-salary_month']

    def __str__(self):
        return f"{self.employee.employeecode} — {self.get_deduction_type_display()} ₹{self.deduction_amount}"


# ── Helper ────────────────────────────────────────────────────────────────────

def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


def _calculate_wages(emp, att, desig):
    """Calculate wages from designation rates and attendance days."""
    days = float(att.working_days) if att else 0
    ot_hours = float(att.work_pay) if att else 0  # work_pay reused as OT hours until attendance updated

    if desig.is_dailywage:
        basic = round(desig.dailywage * days, 2)
        da    = 0
        hra   = 0
    else:
        # Pro-rate monthly salary by working days (assume 26 working days/month)
        factor = days / 26 if days else 0
        basic  = round(float(desig.basicpay) * factor, 2)
        da     = round(float(desig.da) * factor, 2)
        hra    = round(float(desig.hra) * factor, 2)

    # Overtime: basic daily rate × 2 × OT hours / 8
    daily_rate  = float(desig.dailywage) if desig.is_dailywage else float(desig.basicpay) / 26
    ot_wages    = round(daily_rate * 2 * ot_hours / 8, 2)

    gross = round(basic + da + hra + ot_wages, 2)

    # Deductions from designation
    epf  = round(float(desig.ed_epf_amount) or gross * float(desig.ed_epf_per) / 100, 2)
    esi  = round(float(desig.ed_esi_amount) or gross * float(desig.ed_esi_per) / 100, 2)
    pt   = round(float(desig.ed_professionaltax), 2)
    lw   = round(float(desig.ed_labourwelfare_amount) or gross * float(desig.ed_labourwelfare_per) / 100, 2)
    total_ded = round(epf + esi + pt + lw, 2)
    net  = round(gross - total_ded, 2)

    return {
        'working_days': days, 'overtime_hours': ot_hours,
        'basic_wages': basic, 'da': da, 'hra': hra,
        'overtime_wages': ot_wages, 'gross_wages': gross,
        'epf_deduction': epf, 'esi_deduction': esi,
        'professional_tax': pt, 'labour_welfare': lw,
        'total_deductions': total_ded, 'net_wages': net,
    }


# ── Views ─────────────────────────────────────────────────────────────────────

@login_required
def list_wages(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    records = wages_record.objects.filter(company=company).select_related('employee')
    return render(request, 'Aapp/wages/list_wages.html', {'records': records, 'company': company})


@login_required
def generate_wages(request):
    """Generate wages for one employee+month+year from attendance + designation."""
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    employees = employee.objects.filter(CompanyID=company, is_working=True).order_by('name')

    if request.method == 'POST':
        p       = request.POST
        emp     = get_object_or_404(employee, employeeid=p.get('employee_id'), CompanyID=company)
        month   = int(p.get('salary_month', 0))
        year    = int(p.get('salary_year', 0))

        if wages_record.objects.filter(employee=emp, salary_month=month, salary_year=year).exists():
            messages.error(request, f'Wages for {emp.name} — {month}/{year} already generated.')
        else:
            att    = attendance.objects.filter(employee_id=emp, salary_month=month, salary_year=year).first()
            desig  = emp.designationID
            calc   = _calculate_wages(emp, att, desig)

            # Add any fines for this month
            fines_total = sum(
                float(f.fine_amount)
                for f in wages_fine.objects.filter(employee=emp, salary_month=month, salary_year=year)
            )
            # Add any extra deductions for this month
            extra_ded = sum(
                float(d.deduction_amount)
                for d in wages_deduction.objects.filter(employee=emp, salary_month=month, salary_year=year)
            )
            calc['other_deductions'] = round(fines_total + extra_ded, 2)
            calc['total_deductions'] = round(calc['total_deductions'] + calc['other_deductions'], 2)
            calc['net_wages']        = round(calc['gross_wages'] - calc['total_deductions'], 2)

            wr = wages_record.objects.create(
                company=company, employee=emp, attendance=att,
                salary_month=month, salary_year=year,
                created_by=request.user, **calc
            )
            messages.success(request, f'Wages generated for {emp.name} — {month}/{year}.')
            return redirect('Aapp:list_wages')

    return render(request, 'Aapp/wages/generate_wages.html', {
        'employees': employees, 'months': MONTH_CHOICES, 'company': company,
    })


@login_required
def update_wages(request, wages_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(wages_record, wages_id=wages_id, company=company, is_finalized=False)

    if request.method == 'POST':
        p = request.POST
        rec.overtime_hours   = p.get('overtime_hours', rec.overtime_hours)
        rec.other_earnings   = p.get('other_earnings', rec.other_earnings)
        rec.other_deductions = p.get('other_deductions', rec.other_deductions)
        rec.remarks          = p.get('remarks', rec.remarks)
        rec.gross_wages      = round(
            float(rec.basic_wages) + float(rec.da) + float(rec.hra) +
            float(rec.overtime_wages) + float(rec.other_earnings), 2
        )
        rec.total_deductions = round(
            float(rec.epf_deduction) + float(rec.esi_deduction) +
            float(rec.professional_tax) + float(rec.labour_welfare) +
            float(rec.other_deductions), 2
        )
        rec.net_wages   = round(float(rec.gross_wages) - float(rec.total_deductions), 2)
        rec.updated_by  = request.user
        rec.save()
        messages.success(request, 'Wages record updated.')
        return redirect('Aapp:list_wages')

    return render(request, 'Aapp/wages/update_wages.html', {'rec': rec, 'months': MONTH_CHOICES})


@login_required
def finalize_wages(request, wages_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(wages_record, wages_id=wages_id, company=company)
    if request.method == 'POST':
        rec.is_finalized = True
        rec.updated_by   = request.user
        rec.save()
        messages.success(request, f'Wages finalized for {rec.employee.name}.')
        return redirect('Aapp:list_wages')
    return render(request, 'Aapp/wages/finalize_wages.html', {'rec': rec})


@login_required
def delete_wages(request, wages_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(wages_record, wages_id=wages_id, company=company, is_finalized=False)
    if request.method == 'POST':
        rec.delete()
        messages.success(request, 'Wages record deleted.')
        return redirect('Aapp:list_wages')
    return render(request, 'Aapp/wages/delete_wages.html', {'rec': rec})


# ── Fine Views ────────────────────────────────────────────────────────────────

@login_required
def list_fines(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    fines = wages_fine.objects.filter(company=company).select_related('employee')
    return render(request, 'Aapp/wages/list_fines.html', {'fines': fines, 'company': company})


@login_required
def add_fine(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    employees = employee.objects.filter(CompanyID=company, is_working=True).order_by('name')

    if request.method == 'POST':
        p   = request.POST
        emp = get_object_or_404(employee, employeeid=p.get('employee_id'), CompanyID=company)
        wages_fine.objects.create(
            company=company, employee=emp,
            fine_date=p.get('fine_date'),
            fine_amount=p.get('fine_amount'),
            fine_reason=p.get('fine_reason'),
            salary_month=int(p.get('salary_month')),
            salary_year=int(p.get('salary_year')),
            created_by=request.user,
        )
        messages.success(request, 'Fine recorded.')
        return redirect('Aapp:list_fines')

    return render(request, 'Aapp/wages/add_fine.html', {
        'employees': employees, 'months': MONTH_CHOICES, 'company': company,
    })


@login_required
def delete_fine(request, fine_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    fine = get_object_or_404(wages_fine, fine_id=fine_id, company=company)
    if request.method == 'POST':
        fine.delete()
        messages.success(request, 'Fine deleted.')
        return redirect('Aapp:list_fines')
    return render(request, 'Aapp/wages/delete_fine.html', {'fine': fine})


# ── Deduction Views ───────────────────────────────────────────────────────────

@login_required
def list_deductions(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    deductions = wages_deduction.objects.filter(company=company).select_related('employee')
    return render(request, 'Aapp/wages/list_deductions.html', {'deductions': deductions, 'company': company})


@login_required
def add_deduction(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    employees = employee.objects.filter(CompanyID=company, is_working=True).order_by('name')

    if request.method == 'POST':
        p   = request.POST
        emp = get_object_or_404(employee, employeeid=p.get('employee_id'), CompanyID=company)
        wages_deduction.objects.create(
            company=company, employee=emp,
            deduction_type=p.get('deduction_type'),
            deduction_amount=p.get('deduction_amount'),
            reason=p.get('reason'),
            salary_month=int(p.get('salary_month')),
            salary_year=int(p.get('salary_year')),
            created_by=request.user,
        )
        messages.success(request, 'Deduction recorded.')
        return redirect('Aapp:list_deductions')

    return render(request, 'Aapp/wages/add_deduction.html', {
        'employees': employees, 'months': MONTH_CHOICES,
        'deduction_types': DEDUCTION_TYPE_CHOICES, 'company': company,
    })


@login_required
def delete_deduction(request, deduction_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    ded = get_object_or_404(wages_deduction, deduction_id=deduction_id, company=company)
    if request.method == 'POST':
        ded.delete()
        messages.success(request, 'Deduction deleted.')
        return redirect('Aapp:list_deductions')
    return render(request, 'Aapp/wages/delete_deduction.html', {'ded': ded})
