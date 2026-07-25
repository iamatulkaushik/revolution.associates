from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
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




from django import forms as _wforms

class WagesRecordForm(_wforms.ModelForm):
    class Meta:
        model = wages_record
        fields = ['basic_wages', 'da', 'hra', 'overtime_wages', 'other_earnings',
                  'working_days', 'overtime_hours', 'epf_deduction', 'esi_deduction',
                  'professional_tax', 'income_tax', 'labour_welfare', 'other_deductions',
                  'remarks']

class WagesFineForm(_wforms.ModelForm):
    class Meta:
        model = wages_fine
        fields = ['employee', 'fine_date', 'fine_reason', 'fine_amount',
                  'salary_month', 'salary_year']
        widgets = {'fine_date': _wforms.DateInput(attrs={'type': 'date'})}

class WagesDeductionForm(_wforms.ModelForm):
    class Meta:
        model = wages_deduction
        fields = ['employee', 'deduction_type', 'reason',
                  'deduction_amount', 'salary_month', 'salary_year']


def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Wage Register Views (Form 17 — Register of Wages) ────────────────────────

@login_required
def list_wages(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')
    records = wages_record.objects.filter(company=company).select_related('employee')
    rows = [{
        'cells': [r.employee.name, r.emp_code, f'{r.salary_month}/{r.salary_year}',
                  r.basic_wages, r.net_wages, 'Finalised' if r.is_finalized else 'Draft'],
        'actions': [
            {'url': reverse('update_wages', args=[r.wages_id]), 'label': 'Edit', 'css': 'edit'},
        ] + ([{'url': reverse('finalize_wages', args=[r.wages_id]), 'label': 'Finalise'}]
             if not r.is_finalized else []) +
            [{'url': reverse('delete_wages', args=[r.wages_id]), 'label': 'Delete', 'css': 'delete'}],
    } for r in records]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Wages Register (Form 17 / Form III)',
        'columns': ['Employee', 'Code', 'Month/Year', 'Basic Wages', 'Net Wages', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('generate_wages'), 'add_label': 'Generate Wages',
        'extra_links': [
            {'url': reverse('list_fines'), 'label': 'Fines Register (Form I)'},
            {'url': reverse('list_deductions'), 'label': 'Deductions Register (Form II)'},
        ],
        'empty_message': 'No wage records yet. Use "Generate Wages" to auto-calculate.',
    })


@login_required
def generate_wages(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        from Aapp.app.attandance import attendance
        from Aapp.app.designation import designation
        p = request.POST
        month = int(p.get('salary_month', 0))
        year = int(p.get('salary_year', 0))
        if not month or not year:
            messages.error(request, 'Please provide month and year.')
        else:
            employees = employee.objects.filter(CompanyID=company, is_working=True)
            created = 0
            for emp in employees:
                att = attendance.objects.filter(
                    employee_id=emp, salary_month=month, salary_year=year
                ).first()
                desig = designation.objects.filter(
                    CompanyID=company, is_active=True,
                    designationid=emp.designation_id
                ).first() if hasattr(emp, 'designation_id') else None
                if not wages_record.objects.filter(
                    employee=emp, salary_month=month, salary_year=year
                ).exists():
                    wages = _calculate_wages(emp, att, desig)
                    wages_record.objects.create(
                        company=company, employee=emp,
                        salary_month=month, salary_year=year,
                        created_by=request.user, **wages,
                    )
                    created += 1
            messages.success(request, f'Generated wages for {created} employee(s) — {month}/{year}.')
            return redirect('list_wages')

    return render(request, 'Aapp/generic/form.html', {
        'manual_fields': [
            {'name': 'salary_month', 'label': 'Month', 'type': 'select',
             'choices': [(str(i), name) for i, name in MONTH_CHOICES]},
            {'name': 'salary_year', 'label': 'Year', 'type': 'text'},
        ],
        'company': company,
        'page_title': 'Generate Monthly Wages (Form 17)',
        'cancel_url': reverse('list_wages'),
    })


@login_required
def update_wages(request, wages_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    rec = get_object_or_404(wages_record, wages_id=wages_id, company=company, is_finalized=False)

    if request.method == 'POST':
        p = request.POST
        for field in ['basic_wages', 'da', 'hra', 'overtime_wages', 'other_earnings',
                      'working_days', 'epf_deduction', 'esi_deduction',
                      'professional_tax', 'income_tax', 'labour_welfare', 'other_deductions']:
            if p.get(field):
                setattr(rec, field, p[field])
        rec.gross_wages = sum([
            float(rec.basic_wages or 0), float(rec.da or 0), float(rec.hra or 0),
            float(rec.overtime_wages or 0), float(rec.other_earnings or 0),
        ])
        rec.total_deductions = sum([
            float(rec.epf_deduction or 0), float(rec.esi_deduction or 0),
            float(rec.professional_tax or 0), float(rec.income_tax or 0),
            float(rec.labour_welfare or 0), float(rec.other_deductions or 0),
        ])
        rec.net_wages = round(float(rec.gross_wages) - float(rec.total_deductions), 2)
        rec.updated_by = request.user
        rec.save()
        messages.success(request, f'Wages updated for {rec.employee.name}.')
        return redirect('list_wages')

    return render(request, 'Aapp/generic/form.html', {
        'form': WagesRecordForm(instance=rec), 'company': company,
        'page_title': f'Edit Wages — {rec.employee.name} ({rec.salary_month}/{rec.salary_year})',
        'cancel_url': reverse('list_wages'),
    })


@login_required
def finalize_wages(request, wages_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    rec = get_object_or_404(wages_record, wages_id=wages_id, company=company, is_finalized=False)
    if request.method == 'POST':
        rec.is_finalized = True
        rec.save()
        messages.success(request, f'Wages finalised for {rec.employee.name}.')
        return redirect('list_wages')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Finalise Wages',
        'confirm_message': f'Finalise wages for <strong>{rec.employee.name}</strong> '
                            f'({rec.salary_month}/{rec.salary_year})? '
                            f'Net wages: <strong>₹{rec.net_wages}</strong>. '
                            f'This cannot be undone.',
        'cancel_url': reverse('list_wages'),
    })


@login_required
def delete_wages(request, wages_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    rec = get_object_or_404(wages_record, wages_id=wages_id, company=company, is_finalized=False)
    if request.method == 'POST':
        rec.delete()
        messages.success(request, 'Wages record deleted.')
        return redirect('list_wages')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Delete Wages Record',
        'confirm_message': f'Delete wages record for <strong>{rec.employee.name}</strong> '
                            f'({rec.salary_month}/{rec.salary_year})?',
        'cancel_url': reverse('list_wages'),
    })


# ── Fines Register Views (Form I) ─────────────────────────────────────────────

@login_required
def list_fines(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')
    fines = wages_fine.objects.filter(company=company).select_related('employee')
    rows = [{
        'cells': [f.employee.name, f.fine_date, f.fine_reason, f.fine_amount,
                  f'{f.salary_month}/{f.salary_year}'],
        'actions': [{'url': reverse('delete_fine', args=[f.fine_id]), 'label': 'Delete', 'css': 'delete'}],
    } for f in fines]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Payment of Wages Act — Fines Register (Form I)',
        'columns': ['Employee', 'Fine Date', 'Reason', 'Fine Amount (₹)', 'Month/Year'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_fine'), 'add_label': 'Add Fine',
        'empty_message': 'No fines recorded.',
    })


@login_required
def add_fine(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    employees = employee.objects.filter(CompanyID=company, is_working=True).order_by('name')

    if request.method == 'POST':
        form = WagesFineForm(request.POST)
        if form.is_valid():
            fine = form.save(commit=False)
            fine.company = company
            fine.created_by = request.user
            fine.save()
            messages.success(request, 'Fine recorded.')
            return redirect('list_fines')
    else:
        form = WagesFineForm()
        form.fields['employee'].queryset = employees

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': 'Add Fine (Payment of Wages Act — Form I)',
        'cancel_url': reverse('list_fines'),
    })


@login_required
def delete_fine(request, fine_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    fine = get_object_or_404(wages_fine, fine_id=fine_id, company=company)
    if request.method == 'POST':
        fine.delete()
        messages.success(request, 'Fine deleted.')
        return redirect('list_fines')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Delete Fine',
        'confirm_message': f'Delete fine of <strong>₹{fine.fine_amount}</strong> '
                            f'for {fine.employee.name} ({fine.fine_reason})?',
        'cancel_url': reverse('list_fines'),
    })


# ── Deductions Register Views (Form II) ──────────────────────────────────────

@login_required
def list_deductions(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')
    deductions = wages_deduction.objects.filter(company=company).select_related('employee')
    rows = [{
        'cells': [d.employee.name, d.deduction_type, d.reason, d.deduction_amount,
                  f'{d.salary_month}/{d.salary_year}'],
        'actions': [{'url': reverse('delete_deduction', args=[d.deduction_id]), 'label': 'Delete', 'css': 'delete'}],
    } for d in deductions]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Payment of Wages Act — Deductions Register (Form II)',
        'columns': ['Employee', 'Deduction Type', 'Reason', 'Amount (₹)', 'Month/Year'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_deduction'), 'add_label': 'Add Deduction',
        'empty_message': 'No deductions recorded.',
    })


@login_required
def add_deduction(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    employees = employee.objects.filter(CompanyID=company, is_working=True).order_by('name')

    if request.method == 'POST':
        form = WagesDeductionForm(request.POST)
        if form.is_valid():
            ded = form.save(commit=False)
            ded.company = company
            ded.created_by = request.user
            ded.save()
            messages.success(request, 'Deduction recorded.')
            return redirect('list_deductions')
    else:
        form = WagesDeductionForm()
        form.fields['employee'].queryset = employees

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': 'Add Deduction (Payment of Wages Act — Form II)',
        'cancel_url': reverse('list_deductions'),
    })


@login_required
def delete_deduction(request, deduction_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    ded = get_object_or_404(wages_deduction, deduction_id=deduction_id, company=company)
    if request.method == 'POST':
        ded.delete()
        messages.success(request, 'Deduction deleted.')
        return redirect('list_deductions')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Delete Deduction',
        'confirm_message': f'Delete deduction of <strong>₹{ded.deduction_amount}</strong> '
                            f'({ded.deduction_type} — {ded.reason}) for {ded.employee.name}?',
        'cancel_url': reverse('list_deductions'),
    })
