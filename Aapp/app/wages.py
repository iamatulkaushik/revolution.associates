"""
Wages Register (Form 17 / Form III) — no longer a separately-entered or
separately-calculated record. It is now a read-only view over
Aapp.app.salary_processing.salary_slip, filtered to employees whose
designation is a daily-wage designation, exactly as the batch salary
processor already computes and gates (Shop Act / EPF / ESI / Labour /
TAN) via statutory_gates. This avoids a second, independently-maintained
wage calculation drifting out of sync with the payroll engine.

wages_fine and wages_deduction remain genuinely separate data (manual
entries, not derivable from salary processing) — their link now points
at salary_slip instead of the deleted wages_record.
"""

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
from Aapp.app.statutory_gates import get_company_gates
from Aapp.app.salary_processing import salary_slip as sp


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
MONTH_CHOICES = [
    (1,'January'),(2,'February'),(3,'March'),(4,'April'),
    (5,'May'),(6,'June'),(7,'July'),(8,'August'),
    (9,'September'),(10,'October'),(11,'November'),(12,'December'),
]
YEAR_CHOICES = [(y, y) for y in range(2026, 2032)]

# ── Models ────────────────────────────────────────────────────────────────────

class wages_fine(models.Model):
    fine_id         = models.AutoField(primary_key=True)
    company         = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee        = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID', related_name='fines')
    salary_slip     = models.ForeignKey(sp, on_delete=models.SET_NULL, null=True, blank=True, related_name='fines')
    fine_date       = models.DateField()
    fine_amount     = models.DecimalField(max_digits=10, decimal_places=2)
    fine_reason     = models.CharField(max_length=500)
    salary_month    = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    salary_year     = models.PositiveSmallIntegerField(choices=YEAR_CHOICES)
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
    salary_slip     = models.ForeignKey(sp, on_delete=models.SET_NULL, null=True, blank=True, related_name='extra_deductions')
    deduction_type  = models.CharField(max_length=30, choices=DEDUCTION_TYPE_CHOICES)
    deduction_amount= models.DecimalField(max_digits=10, decimal_places=2)
    reason          = models.CharField(max_length=500)
    salary_month    = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    salary_year     = models.PositiveSmallIntegerField(choices=YEAR_CHOICES)
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='deductions_created')
    created_date    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wages_deduction'
        ordering = ['-salary_year', '-salary_month']

    def __str__(self):
        return f"{self.employee.employeecode} — {self.get_deduction_type_display()} ₹{self.deduction_amount}"


from django import forms as _wforms

class WagesFineForm(_wforms.ModelForm):
    class Meta:
        model = wages_fine
        fields = ['employee', 'fine_date', 'fine_amount', 'fine_reason', 'salary_month', 'salary_year']
        widgets = {'fine_date': _wforms.DateInput(attrs={'type': 'date'})}


class WagesDeductionForm(_wforms.ModelForm):
    class Meta:
        model = wages_deduction
        fields = ['employee', 'deduction_type', 'deduction_amount', 'reason', 'salary_month', 'salary_year']


def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Wage Register View (Form 17 / Form III) — READ ONLY, sourced from salary_slip ──

@login_required
def list_wages(request):
    """
    Wages Register — read-only, generated from salary_slip records for
    daily-wage designations only. No separate generation step: run the
    normal salary batch (salary_processing) for the month first, and the
    daily-wage employees within it appear here automatically.
    """
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    from Aapp.app.salary_processing import salary_slip

    month = request.GET.get('month')
    year = request.GET.get('year')

    records = salary_slip.objects.filter(
        company_id=company, designation_id__is_dailywage=True
    ).select_related('employee_id', 'designation_id')
    if month:
        records = records.filter(processing_id__month=month)
    if year:
        records = records.filter(processing_id__year=year)

    rows = [{
        'cells': [
            r.employee_id.name, r.employee_id.employeecode,
            f'{r.processing_id.month}/{r.processing_id.year}',
            r.basic_earned, r.net_pay, r.processing_id.status,
        ],
        'actions': [
            {'url': reverse('view_salary_slip', args=[r.id]), 'label': 'View', 'css': 'edit'},
        ],
    } for r in records]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Wages Register (Form 17 / Form III)',
        'columns': ['Employee', 'Code', 'Month/Year', 'Basic Wages', 'Net Wages', 'Status'],
        'rows': rows, 'company': company,
        'extra_links': [
            {'url': reverse('salary_dashboard'), 'label': 'Process Salary Batch'},
            {'url': reverse('list_fines'), 'label': 'Fines Register (Form I)'},
            {'url': reverse('list_deductions'), 'label': 'Deductions Register (Form II)'},
        ],
        'empty_message': 'No wage records yet. Process a salary batch to populate this register.',
    })


# ── Fines Register Views (Form I) ─────────────────────────────────────────────
# Fines require Shop Act registration — same as overtime and leave.

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

    gates = get_company_gates(company)
    if not gates['shop_act']:
        messages.error(
            request,
            'Shop & Establishments Act registration not on file — fines cannot be recorded for this company.'
        )
        return redirect('list_fines')

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