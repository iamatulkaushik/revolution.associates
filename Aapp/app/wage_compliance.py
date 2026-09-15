"""
Minimum Wages Act, 1948 and Payment of Wages Act, 1936 — annual returns.

Already covered elsewhere:
    Aapp/app/wages.py              -> wages_fine (Form I), wages_deduction (Form II),
                                       Wages Register / Form III/17 (read-only, from salary_slip)
    Aapp/app/attandance.py         -> MinimumWagesOvertimeRegister (Form IV — Overtime Register)

This file adds the two annual returns not yet covered:
    Minimum Wages Form V        -> MinimumWagesAnnualReturn   (due 1 Feb)
    Payment of Wages Form IV    -> PaymentOfWagesAnnualReturn (due 15 Feb)
"""

from django import forms
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from Sapp.app.company import Company


RETURN_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('filed', 'Filed'),
    ('overdue', 'Overdue'),
]

WAGE_PERIOD_CHOICES = [
    ('weekly', 'Weekly'),
    ('fortnightly', 'Fortnightly'),
    ('monthly', 'Monthly'),
]

PAYMENT_MODE_CHOICES = [
    ('cash', 'Cash'),
    ('cheque', 'Cheque'),
    ('bank_transfer', 'Bank Transfer'),
]


# ── Models ───────────────────────────────────────────────────────────────────

class MinimumWagesAnnualReturn(models.Model):
    """Form V (Rule 21(4A)) — due by 1 February of the following year."""
    return_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    year = models.PositiveSmallIntegerField()

    category_of_work = models.CharField(max_length=255, help_text='Category of scheduled employment (Form V)')
    total_employees_male = models.PositiveIntegerField(default=0)
    total_employees_female = models.PositiveIntegerField(default=0)
    min_wage_rate_unskilled = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    min_wage_rate_semiskilled = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    min_wage_rate_skilled = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_wages_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_ot_hours = models.PositiveIntegerField(default=0)
    total_ot_wages = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_fines_imposed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    filing_status = models.CharField(max_length=10, choices=RETURN_STATUS_CHOICES, default='pending')
    filed_date = models.DateField(null=True, blank=True)
    acknowledgement_no = models.CharField(max_length=100, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='mw_returns_created')
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'minimum_wages_annual_return'
        unique_together = ('company', 'year')
        ordering = ['-year']

    def __str__(self):
        return f"Min Wages Annual Return {self.year} — {self.company.company_name}"


class PaymentOfWagesAnnualReturn(models.Model):
    """Form IV (Rule 18) — due by 15 February of the following year."""
    return_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    year = models.PositiveSmallIntegerField()

    total_employed = models.PositiveIntegerField(default=0)
    total_wages_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_fines_imposed = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_fines_realised = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    wage_period = models.CharField(max_length=20, choices=WAGE_PERIOD_CHOICES, default='monthly')
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default='bank_transfer')

    filing_status = models.CharField(max_length=10, choices=RETURN_STATUS_CHOICES, default='pending')
    filed_date = models.DateField(null=True, blank=True)
    acknowledgement_no = models.CharField(max_length=100, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='pow_returns_created')
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payment_of_wages_annual_return'
        unique_together = ('company', 'year')
        ordering = ['-year']

    def __str__(self):
        return f"POW Annual Return {self.year} — {self.company.company_name}"


# ── Forms ────────────────────────────────────────────────────────────────────

class MinimumWagesEditForm(forms.ModelForm):
    """Rate fields + filing status are set by hand; everything else is
    auto-computed from the salary sheet, overtime register, and fines table."""
    class Meta:
        model = MinimumWagesAnnualReturn
        fields = ['category_of_work', 'min_wage_rate_unskilled', 'min_wage_rate_semiskilled',
                  'min_wage_rate_skilled', 'filing_status', 'filed_date', 'acknowledgement_no']
        widgets = {'filed_date': forms.DateInput(attrs={'type': 'date'})}


class MinimumWagesAnnualReturnForm(forms.ModelForm):
    class Meta:
        model = MinimumWagesAnnualReturn
        fields = ['year', 'category_of_work', 'total_employees_male', 'total_employees_female',
                  'min_wage_rate_unskilled', 'min_wage_rate_semiskilled', 'min_wage_rate_skilled',
                  'total_wages_paid', 'total_ot_hours', 'total_ot_wages', 'total_fines_imposed',
                  'total_deductions', 'filing_status', 'filed_date', 'acknowledgement_no']
        widgets = {'filed_date': forms.DateInput(attrs={'type': 'date'})}


class PaymentOfWagesEditForm(forms.ModelForm):
    """Only the filing-status fields an admin sets by hand; totals are
    auto-computed from the salary sheet, fines, and deductions tables."""
    class Meta:
        model = PaymentOfWagesAnnualReturn
        fields = ['wage_period', 'payment_mode', 'filing_status', 'filed_date', 'acknowledgement_no']
        widgets = {'filed_date': forms.DateInput(attrs={'type': 'date'})}


class PaymentOfWagesAnnualReturnForm(forms.ModelForm):
    class Meta:
        model = PaymentOfWagesAnnualReturn
        fields = ['year', 'total_employed', 'total_wages_paid', 'total_fines_imposed',
                  'total_fines_realised', 'total_deductions', 'wage_period', 'payment_mode',
                  'filing_status', 'filed_date', 'acknowledgement_no']
        widgets = {'filed_date': forms.DateInput(attrs={'type': 'date'})}


# ── Helper ───────────────────────────────────────────────────────────────────

def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Minimum Wages Return Views (Form V) ──────────────────────────────────────

@login_required
def list_minwages_returns(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')
    returns = MinimumWagesAnnualReturn.objects.filter(company=company)
    rows = [{
        'cells': [r.year, r.category_of_work, r.total_employees_male, r.total_employees_female,
                  r.total_wages_paid, r.get_filing_status_display()],
        'actions': [{'url': reverse('alter_minwages_return', args=[r.return_id]), 'label': 'Edit', 'css': 'edit'},
                    {'url': reverse('download_minwages_return', args=[r.return_id]), 'label': 'Download PDF', 'css': 'download'}],
    } for r in returns]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Minimum Wages Act — Annual Return (Form V)',
        'columns': ['Year', 'Category of Work', 'Male', 'Female', 'Total Wages Paid', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_minwages_return'), 'add_label': 'Add Annual Return',
        'empty_message': 'No Minimum Wages annual returns filed yet.',
    })


@login_required
def _compute_minwages_totals(company, year):
    from decimal import Decimal
    from Aapp.app.salary_processing import salary_slip
    from Aapp.app.attandance import MinimumWagesOvertimeRegister
    from Aapp.app.wages import wages_fine, wages_deduction

    slips = salary_slip.objects.filter(company_id=company, processing_id__year=year).select_related('employee_id')
    male = female = 0
    total_wages = Decimal('0')
    seen_employees = set()
    for s in slips:
        total_wages += Decimal(s.gross_earnings or 0)
        if s.employee_id_id not in seen_employees:
            seen_employees.add(s.employee_id_id)
            if s.employee_id.gender == 'Male':
                male += 1
            elif s.employee_id.gender == 'Female':
                female += 1

    ot_records = MinimumWagesOvertimeRegister.objects.filter(
        attendance__companyid=company, attendance__salary_year=year)
    total_ot_hours = sum((r.overtime_hours for r in ot_records), Decimal('0'))
    total_ot_wages = sum((r.ot_wages_paid for r in ot_records), Decimal('0'))

    total_fines = wages_fine.objects.filter(company=company, salary_year=year).aggregate(
        t=models.Sum('fine_amount'))['t'] or Decimal('0')
    total_deductions = wages_deduction.objects.filter(company=company, salary_year=year).aggregate(
        t=models.Sum('deduction_amount'))['t'] or Decimal('0')

    return {
        'total_employees_male': male, 'total_employees_female': female,
        'total_wages_paid': total_wages, 'total_ot_hours': int(total_ot_hours),
        'total_ot_wages': total_ot_wages, 'total_fines_imposed': total_fines,
        'total_deductions': total_deductions,
    }


@login_required
def add_minwages_return(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        year = int(request.POST.get('year'))
        category = request.POST.get('category_of_work', '').strip()
        if MinimumWagesAnnualReturn.objects.filter(company=company, year=year).exists():
            messages.error(request, f'A Minimum Wages return for {year} already exists. Edit it instead.')
            return redirect('list_minwages_returns')

        totals = _compute_minwages_totals(company, year)
        if totals['total_wages_paid'] == 0:
            messages.error(request, f'No salary sheet data found for {year}.')
            return redirect('list_minwages_returns')

        ret = MinimumWagesAnnualReturn(company=company, year=year, category_of_work=category,
                                        created_by=request.user, **totals)
        ret.save()
        messages.success(request, f'Minimum Wages return for {year} generated from salary sheet. '
                                    'Set the wage rates and file it.')
        return redirect('alter_minwages_return', return_id=ret.return_id)

    year_choices = [(y, y) for y in range(2023, 2031)]
    return render(request, 'Aapp/generic/year_category_picker.html', {
        'company': company, 'page_title': 'Generate Minimum Wages Return — Select Year',
        'year_choices': year_choices,
    })


@login_required
def alter_minwages_return(request, return_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    ret = get_object_or_404(MinimumWagesAnnualReturn, return_id=return_id, company=company)

    if request.method == 'POST':
        form = MinimumWagesEditForm(request.POST, instance=ret)
        if form.is_valid():
            form.save()
            messages.success(request, 'Return updated.')
            return redirect('list_minwages_returns')
    else:
        form = MinimumWagesEditForm(instance=ret)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': f'Edit Minimum Wages Return — {ret.year}',
        'cancel_url': reverse('list_minwages_returns'),
        'readonly_summary': [
            ('Male Employees', ret.total_employees_male),
            ('Female Employees', ret.total_employees_female),
            ('Total Wages Paid', ret.total_wages_paid),
            ('Total OT Hours', ret.total_ot_hours),
            ('Total OT Wages', ret.total_ot_wages),
            ('Total Fines Imposed', ret.total_fines_imposed),
            ('Total Deductions', ret.total_deductions),
        ],
    })


# ── Payment of Wages Return Views (Form IV) ─────────────────────────────────

@login_required
def list_pow_returns(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')
    returns = PaymentOfWagesAnnualReturn.objects.filter(company=company)
    rows = [{
        'cells': [r.year, r.total_employed, r.total_wages_paid, r.get_wage_period_display(),
                  r.get_payment_mode_display(), r.get_filing_status_display()],
        'actions': [{'url': reverse('alter_pow_return', args=[r.return_id]), 'label': 'Edit', 'css': 'edit'},
                    {'url': reverse('download_pow_return', args=[r.return_id]), 'label': 'Download PDF', 'css': 'download'}],
    } for r in returns]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Payment of Wages Act — Annual Return (Form IV)',
        'columns': ['Year', 'Employees', 'Total Wages Paid', 'Wage Period', 'Payment Mode', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_pow_return'), 'add_label': 'Add Annual Return',
        'empty_message': 'No Payment of Wages annual returns filed yet.',
    })


@login_required
def _compute_pow_totals(company, year):
    from decimal import Decimal
    from Aapp.app.salary_processing import salary_slip
    from Aapp.app.wages import wages_fine, wages_deduction

    slips = salary_slip.objects.filter(company_id=company, processing_id__year=year).select_related('employee_id')
    total_wages = sum((Decimal(s.gross_earnings or 0) for s in slips), Decimal('0'))
    total_employed = slips.values('employee_id').distinct().count()

    total_fines_imposed = wages_fine.objects.filter(company=company, salary_year=year).aggregate(
        t=models.Sum('fine_amount'))['t'] or Decimal('0')
    total_deductions = wages_deduction.objects.filter(company=company, salary_year=year).aggregate(
        t=models.Sum('deduction_amount'))['t'] or Decimal('0')

    return {
        'total_employed': total_employed, 'total_wages_paid': total_wages,
        'total_fines_imposed': total_fines_imposed, 'total_fines_realised': total_fines_imposed,
        'total_deductions': total_deductions,
    }


@login_required
def add_pow_return(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        year = int(request.POST.get('year'))
        if PaymentOfWagesAnnualReturn.objects.filter(company=company, year=year).exists():
            messages.error(request, f'A Payment of Wages return for {year} already exists. Edit it instead.')
            return redirect('list_pow_returns')

        totals = _compute_pow_totals(company, year)
        if totals['total_wages_paid'] == 0:
            messages.error(request, f'No salary sheet data found for {year}.')
            return redirect('list_pow_returns')

        ret = PaymentOfWagesAnnualReturn(company=company, year=year, created_by=request.user, **totals)
        ret.save()
        messages.success(request, f'Payment of Wages return for {year} generated from salary sheet.')
        return redirect('alter_pow_return', return_id=ret.return_id)

    year_choices = [(y, y) for y in range(2023, 2031)]
    return render(request, 'Aapp/generic/year_category_picker.html', {
        'company': company, 'page_title': 'Generate Payment of Wages Return — Select Year',
        'year_choices': year_choices, 'hide_category': True,
    })


@login_required
def alter_pow_return(request, return_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    ret = get_object_or_404(PaymentOfWagesAnnualReturn, return_id=return_id, company=company)

    if request.method == 'POST':
        form = PaymentOfWagesEditForm(request.POST, instance=ret)
        if form.is_valid():
            form.save()
            messages.success(request, 'Return updated.')
            return redirect('list_pow_returns')
    else:
        form = PaymentOfWagesEditForm(instance=ret)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': f'Edit Payment of Wages Return — {ret.year}',
        'cancel_url': reverse('list_pow_returns'),
        'readonly_summary': [
            ('Total Employed', ret.total_employed),
            ('Total Wages Paid', ret.total_wages_paid),
            ('Total Fines Imposed', ret.total_fines_imposed),
            ('Total Fines Realised', ret.total_fines_realised),
            ('Total Deductions', ret.total_deductions),
        ],
    })
