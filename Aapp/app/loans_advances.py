"""
Aapp/app/loans_advances.py
=============================
Separate module for Loans & Advances — per pt_upgrades.md: "saprate file
for loans and advances from salary/allowances". Two record types (Loan,
Advance) share the same amortization logic but stay in distinct models
since they carry different approval/interest semantics in practice.

Deduction mode is chosen per record:
  - 'instalments' : user sets number_of_instalments, EMI amount is derived
  - 'fixed_amount' : user sets a fixed per-month deduction amount, number
                      of instalments is derived (last instalment may be
                      smaller — the remainder)

Auto-deduction: calculate_employee_salary() in salary_processing.py calls
get_due_deduction_for_month() for each active loan/advance and adds it to
loan_deduction / advance_deduction on the slip — replacing manual entry
for anything on schedule. Manual entry in edit_salary_slip still works
for ad-hoc adjustments outside the schedule.
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Select, NumberInput, DateInput, Textarea

from Aapp.app.employee import employee as employee_model
from Sapp.app.company import Company


DEDUCTION_MODE_CHOICES = [
    ('instalments', 'Fixed Number of Instalments'),
    ('fixed_amount', 'Fixed Deduction Amount'),
]

STATUS_CHOICES = [
    ('active', 'Active'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]

MONTH_CHOICES = [
    (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
    (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
    (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
]


def _round(v):
    return Decimal(v).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class LoanAdvanceBase(models.Model):
    """Abstract base shared by Loan and Advance — same schedule logic."""
    employee = models.ForeignKey(employee_model, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate_annual = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                                help_text="Annual %, 0 for interest-free")

    deduction_mode = models.CharField(max_length=15, choices=DEDUCTION_MODE_CHOICES)
    number_of_instalments = models.PositiveIntegerField(null=True, blank=True,
                                                          help_text="Required if mode = instalments")
    fixed_deduction_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                                  help_text="Required if mode = fixed_amount")

    deduction_start_month = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    deduction_start_year = models.PositiveIntegerField()

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    remarks = models.CharField(max_length=500, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.deduction_mode == 'instalments' and not self.number_of_instalments:
            raise ValidationError("Number of instalments required for this deduction mode.")
        if self.deduction_mode == 'fixed_amount' and not self.fixed_deduction_amount:
            raise ValidationError("Fixed deduction amount required for this deduction mode.")

    @property
    def total_payable(self):
        """Principal + simple interest (flat, not reducing-balance) if interest_rate_annual > 0."""
        if not self.interest_rate_annual:
            return self.principal_amount
        instalments = self.number_of_instalments or self._derived_instalment_count()
        years = Decimal(instalments) / Decimal('12')
        interest = self.principal_amount * (self.interest_rate_annual / Decimal('100')) * years
        return _round(self.principal_amount + interest)

    def _derived_instalment_count(self):
        """When mode is fixed_amount: how many full instalments + remainder."""
        if not self.fixed_deduction_amount:
            return 0
        total = self.total_payable if self.interest_rate_annual else self.principal_amount
        full = int(total // self.fixed_deduction_amount)
        remainder = total - (full * self.fixed_deduction_amount)
        return full + (1 if remainder > 0 else 0)

    def amortization_schedule(self):
        """
        Returns a list of dicts: [{instalment_no, month, year, amount}, ...]
        covering the full repayment period from deduction_start_month/year.
        """
        total = self.total_payable
        schedule = []

        if self.deduction_mode == 'instalments':
            count = self.number_of_instalments
            emi = _round(total / count)
            remaining = total
            m, y = self.deduction_start_month, self.deduction_start_year
            for i in range(1, count + 1):
                amount = emi if i < count else remaining  # last instalment absorbs rounding remainder
                schedule.append({'instalment_no': i, 'month': m, 'year': y, 'amount': _round(amount)})
                remaining -= amount
                m += 1
                if m > 12:
                    m, y = 1, y + 1
        else:  # fixed_amount
            remaining = total
            m, y = self.deduction_start_month, self.deduction_start_year
            i = 1
            while remaining > 0:
                amount = min(self.fixed_deduction_amount, remaining)
                schedule.append({'instalment_no': i, 'month': m, 'year': y, 'amount': _round(amount)})
                remaining -= amount
                m += 1
                if m > 12:
                    m, y = 1, y + 1
                i += 1

        return schedule

    def get_due_deduction_for_month(self, month, year):
        """Returns the Decimal amount due for this specific month/year, or 0 if none due."""
        if self.status != 'active':
            return Decimal('0')
        for row in self.amortization_schedule():
            if row['month'] == month and row['year'] == year:
                return row['amount']
        return Decimal('0')


class Loan(LoanAdvanceBase):
    loan_id = models.AutoField(primary_key=True)
    purpose = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_loans'
        verbose_name = "Employee Loan"

    def __str__(self):
        return f"Loan #{self.loan_id} - {self.employee.name} - Rs.{self.principal_amount}"


class Advance(LoanAdvanceBase):
    advance_id = models.AutoField(primary_key=True)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_advances'
        verbose_name = "Employee Advance"

    def __str__(self):
        return f"Advance #{self.advance_id} - {self.employee.name} - Rs.{self.principal_amount}"


class LoanForm(ModelForm):
    class Meta:
        model = Loan
        fields = ['employee', 'principal_amount', 'interest_rate_annual', 'purpose',
                  'deduction_mode', 'number_of_instalments', 'fixed_deduction_amount',
                  'deduction_start_month', 'deduction_start_year', 'remarks']
        widgets = {
            'employee': Select(attrs={'class': 'form-control'}),
            'principal_amount': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'interest_rate_annual': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'purpose': Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'deduction_mode': Select(attrs={'class': 'form-control'}),
            'number_of_instalments': NumberInput(attrs={'class': 'form-control'}),
            'fixed_deduction_amount': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'deduction_start_month': Select(attrs={'class': 'form-control'}, choices=MONTH_CHOICES),
            'deduction_start_year': NumberInput(attrs={'class': 'form-control'}),
            'remarks': Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class AdvanceForm(ModelForm):
    class Meta:
        model = Advance
        fields = ['employee', 'principal_amount', 'interest_rate_annual', 'reason',
                  'deduction_mode', 'number_of_instalments', 'fixed_deduction_amount',
                  'deduction_start_month', 'deduction_start_year', 'remarks']
        widgets = {
            'employee': Select(attrs={'class': 'form-control'}),
            'principal_amount': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'interest_rate_annual': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'reason': Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'deduction_mode': Select(attrs={'class': 'form-control'}),
            'number_of_instalments': NumberInput(attrs={'class': 'form-control'}),
            'fixed_deduction_amount': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'deduction_start_month': Select(attrs={'class': 'form-control'}, choices=MONTH_CHOICES),
            'deduction_start_year': NumberInput(attrs={'class': 'form-control'}),
            'remarks': Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


def get_total_loan_deduction_for_month(employee_obj, month, year):
    """Sum of all active Loan instalments due for this employee this month."""
    total = Decimal('0')
    for loan in Loan.objects.filter(employee=employee_obj, status='active'):
        total += loan.get_due_deduction_for_month(month, year)
    return total


def get_total_advance_deduction_for_month(employee_obj, month, year):
    """Sum of all active Advance instalments due for this employee this month."""
    total = Decimal('0')
    for adv in Advance.objects.filter(employee=employee_obj, status='active'):
        total += adv.get_due_deduction_for_month(month, year)
    return total


def mark_completed_if_schedule_ended(month, year):
    """
    Housekeeping: flip status to 'completed' for any active loan/advance
    whose last scheduled instalment falls before the given month/year.
    Call this once per payroll run (e.g. from the monthly batch job)
    rather than per-employee-per-slip.
    """
    updated = 0
    for model in (Loan, Advance):
        for record in model.objects.filter(status='active'):
            schedule = record.amortization_schedule()
            if not schedule:
                continue
            last = schedule[-1]
            if (last['year'], last['month']) < (year, month):
                record.status = 'completed'
                record.save(update_fields=['status', 'updated_at'])
                updated += 1
    return updated


# =====================================================================
# VIEWS
# =====================================================================

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse


def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Loans ────────────────────────────────────────────────────────────

@login_required
def list_loans(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    loans = Loan.objects.filter(company=company).select_related('employee').order_by('-created_at')
    rows = [{
        'cells': [
            l.loan_id, l.employee.employeecode, l.employee.name, INR_STR(l.principal_amount),
            l.get_deduction_mode_display(), f"{l.deduction_start_month}/{l.deduction_start_year}",
            l.get_status_display(),
        ],
        'actions': [
            {'url': reverse('view_loan_schedule', args=[l.loan_id]), 'label': 'Schedule', 'css': 'edit'},
            {'url': reverse('alter_loan', args=[l.loan_id]), 'label': 'Edit', 'css': 'edit'},
        ],
    } for l in loans]

    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Employee Loans',
        'columns': ['Loan ID', 'Emp Code', 'Name', 'Principal', 'Mode', 'Start (M/Y)', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('create_loan'), 'add_label': 'Add Loan',
        'empty_message': 'No loans on record yet.',
    })


@login_required
def create_loan(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        form = LoanForm(request.POST)
        if form.is_valid():
            loan = form.save(commit=False)
            loan.company = company
            loan.created_by = request.user.username
            loan.save()
            messages.success(request, 'Loan created successfully.')
            return redirect('list_loans')
    else:
        form = LoanForm()
        form.fields['employee'].queryset = employee_model.objects.filter(CompanyID=company, is_working=True)

    return render(request, 'Aapp/works/create_loan.html', {'form': form, 'company': company})


@login_required
def alter_loan(request, loan_id):
    company = _company(request)
    loan = get_object_or_404(Loan, loan_id=loan_id, company=company)

    if request.method == 'POST':
        form = LoanForm(request.POST, instance=loan)
        if form.is_valid():
            form.save()
            messages.success(request, 'Loan updated successfully.')
            return redirect('list_loans')
    else:
        form = LoanForm(instance=loan)
        form.fields['employee'].queryset = employee_model.objects.filter(CompanyID=company, is_working=True)

    return render(request, 'Aapp/works/alter_loan.html', {'form': form, 'loan': loan})


@login_required
def view_loan_schedule(request, loan_id):
    """Renders the amortization schedule on-screen; PDF via separate download view."""
    company = _company(request)
    loan = get_object_or_404(Loan, loan_id=loan_id, company=company)
    schedule = loan.amortization_schedule()
    return render(request, 'Aapp/works/loan_schedule.html', {
        'loan': loan, 'schedule': schedule, 'record_type': 'Loan',
        'download_url': reverse('download_loan_schedule', args=[loan_id]),
    })


@login_required
def download_loan_schedule(request, loan_id):
    from django.http import HttpResponse
    from Aapp.app.loan_schedule_pdf import loan_advance_schedule_pdf

    company = _company(request)
    loan = get_object_or_404(Loan, loan_id=loan_id, company=company)
    pdf_bytes = loan_advance_schedule_pdf(loan)
    return HttpResponse(pdf_bytes, content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="loan_schedule_{loan_id}.pdf"'
    })


# ── Advances ─────────────────────────────────────────────────────────

@login_required
def list_advances(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    advances = Advance.objects.filter(company=company).select_related('employee').order_by('-created_at')
    rows = [{
        'cells': [
            a.advance_id, a.employee.employeecode, a.employee.name, INR_STR(a.principal_amount),
            a.get_deduction_mode_display(), f"{a.deduction_start_month}/{a.deduction_start_year}",
            a.get_status_display(),
        ],
        'actions': [
            {'url': reverse('view_advance_schedule', args=[a.advance_id]), 'label': 'Schedule', 'css': 'edit'},
            {'url': reverse('alter_advance', args=[a.advance_id]), 'label': 'Edit', 'css': 'edit'},
        ],
    } for a in advances]

    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Employee Advances',
        'columns': ['Advance ID', 'Emp Code', 'Name', 'Principal', 'Mode', 'Start (M/Y)', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('create_advance'), 'add_label': 'Add Advance',
        'empty_message': 'No advances on record yet.',
    })


@login_required
def create_advance(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        form = AdvanceForm(request.POST)
        if form.is_valid():
            advance = form.save(commit=False)
            advance.company = company
            advance.created_by = request.user.username
            advance.save()
            messages.success(request, 'Advance created successfully.')
            return redirect('list_advances')
    else:
        form = AdvanceForm()
        form.fields['employee'].queryset = employee_model.objects.filter(CompanyID=company, is_working=True)

    return render(request, 'Aapp/works/create_advance.html', {'form': form, 'company': company})


@login_required
def alter_advance(request, advance_id):
    company = _company(request)
    advance = get_object_or_404(Advance, advance_id=advance_id, company=company)

    if request.method == 'POST':
        form = AdvanceForm(request.POST, instance=advance)
        if form.is_valid():
            form.save()
            messages.success(request, 'Advance updated successfully.')
            return redirect('list_advances')
    else:
        form = AdvanceForm(instance=advance)
        form.fields['employee'].queryset = employee_model.objects.filter(CompanyID=company, is_working=True)

    return render(request, 'Aapp/works/alter_advance.html', {'form': form, 'advance': advance})


@login_required
def view_advance_schedule(request, advance_id):
    company = _company(request)
    advance = get_object_or_404(Advance, advance_id=advance_id, company=company)
    schedule = advance.amortization_schedule()
    return render(request, 'Aapp/works/loan_schedule.html', {
        'loan': advance, 'schedule': schedule, 'record_type': 'Advance',
        'download_url': reverse('download_advance_schedule', args=[advance_id]),
    })


@login_required
def download_advance_schedule(request, advance_id):
    from django.http import HttpResponse
    from Aapp.app.loan_schedule_pdf import loan_advance_schedule_pdf

    company = _company(request)
    advance = get_object_or_404(Advance, advance_id=advance_id, company=company)
    pdf_bytes = loan_advance_schedule_pdf(advance)
    return HttpResponse(pdf_bytes, content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="advance_schedule_{advance_id}.pdf"'
    })


def INR_STR(amount):
    """Lightweight Rs. formatter for list rows (full INR() with grouping lives in pdf_engine)."""
    return f"Rs. {amount:,.2f}"
