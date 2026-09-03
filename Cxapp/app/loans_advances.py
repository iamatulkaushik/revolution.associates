"""
Cxapp/app/loans_advances.py
==============================
Loans & Advances for the Cxapp (self-signup Company Owner) portal —
mirrors Aapp.app.loans_advances but scoped to CxOwnerProfile/CxEmployee
instead of Sapp.Company/Aapp.employee, since Cxapp maintains its own
independent employee/payroll model tree (see Cxapp/app/process.py
module docstring).

Deduction mode is per-record: instalments OR fixed amount (owner's
choice), same as the Aapp version. Amortization logic is intentionally
duplicated rather than imported from Aapp — the two apps don't share a
company/employee foreign-key target, so a shared implementation would
need an awkward dual-FK design for no real benefit; the schedule math
itself is small and stable.

Wired into CxSalary.process() via get_total_loan_deduction_for_month()
and get_total_advance_deduction_for_month() — called from
Cxapp/app/process.py, added as deduction lines alongside statutory
EPF/ESI/Labour, same as Aapp's salary_processing.py does.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Select, NumberInput, Textarea

from Cxapp.app.employee import CxEmployee


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


class CxLoanAdvanceBase(models.Model):
    employee = models.ForeignKey(CxEmployee, on_delete=models.CASCADE)
    company = models.ForeignKey('Cxapp.CxOwnerProfile', on_delete=models.CASCADE)

    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate_annual = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    deduction_mode = models.CharField(max_length=15, choices=DEDUCTION_MODE_CHOICES)
    number_of_instalments = models.PositiveIntegerField(null=True, blank=True)
    fixed_deduction_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    deduction_start_month = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    deduction_start_year = models.PositiveIntegerField()

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    remarks = models.CharField(max_length=500, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, blank=True)
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
        if not self.interest_rate_annual:
            return self.principal_amount
        instalments = self.number_of_instalments or self._derived_instalment_count()
        years = Decimal(instalments) / Decimal('12')
        interest = self.principal_amount * (self.interest_rate_annual / Decimal('100')) * years
        return _round(self.principal_amount + interest)

    def _derived_instalment_count(self):
        if not self.fixed_deduction_amount:
            return 0
        total = self.total_payable if self.interest_rate_annual else self.principal_amount
        full = int(total // self.fixed_deduction_amount)
        remainder = total - (full * self.fixed_deduction_amount)
        return full + (1 if remainder > 0 else 0)

    def amortization_schedule(self):
        total = self.total_payable
        schedule = []

        if self.deduction_mode == 'instalments':
            count = self.number_of_instalments
            emi = _round(total / count)
            remaining = total
            m, y = self.deduction_start_month, self.deduction_start_year
            for i in range(1, count + 1):
                amount = emi if i < count else remaining
                schedule.append({'instalment_no': i, 'month': m, 'year': y, 'amount': _round(amount)})
                remaining -= amount
                m += 1
                if m > 12:
                    m, y = 1, y + 1
        else:
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
        if self.status != 'active':
            return Decimal('0')
        for row in self.amortization_schedule():
            if row['month'] == month and row['year'] == year:
                return row['amount']
        return Decimal('0')


class CxLoan(CxLoanAdvanceBase):
    loan_id = models.AutoField(primary_key=True)
    purpose = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_loans'
        verbose_name = "Employee Loan"

    def __str__(self):
        return f"Loan #{self.loan_id} - {self.employee.name}"


class CxAdvance(CxLoanAdvanceBase):
    advance_id = models.AutoField(primary_key=True)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_advances'
        verbose_name = "Employee Advance"

    def __str__(self):
        return f"Advance #{self.advance_id} - {self.employee.name}"


class CxLoanForm(ModelForm):
    class Meta:
        model = CxLoan
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


class CxAdvanceForm(ModelForm):
    class Meta:
        model = CxAdvance
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
    total = Decimal('0')
    for loan in CxLoan.objects.filter(employee=employee_obj, status='active'):
        total += loan.get_due_deduction_for_month(month, year)
    return total


def get_total_advance_deduction_for_month(employee_obj, month, year):
    total = Decimal('0')
    for adv in CxAdvance.objects.filter(employee=employee_obj, status='active'):
        total += adv.get_due_deduction_for_month(month, year)
    return total


def get_outstanding_balance(record, as_of_month, as_of_year):
    """Remaining unpaid amount as of (but not including) as_of_month/year — used by FnF."""
    remaining = record.total_payable
    for row in record.amortization_schedule():
        if (row['year'], row['month']) < (as_of_year, as_of_month):
            remaining -= row['amount']
    return max(remaining, Decimal('0'))


# =====================================================================
# VIEWS
# =====================================================================

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse


def _can_manage_payroll(request):
    if getattr(request, 'cx_sub_user', None) is None:
        return True
    return request.cx_sub_user.get_role_permissions().get('wages', False)


def cxapp_list_loans(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_list_loans)(request)


def _list_loans(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to view loans.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    loans = CxLoan.objects.filter(company=owner_profile).select_related('employee').order_by('-created_at')
    return render(request, 'Cxapp/loans_advances/loan_list.html', {'loans': loans})


def cxapp_create_loan(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_create_loan)(request)


def _create_loan(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to manage loans.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    if request.method == 'POST':
        form = CxLoanForm(request.POST)
        if form.is_valid():
            loan = form.save(commit=False)
            loan.company = owner_profile
            loan.created_by = getattr(request.cx_sub_user, 'username', 'Owner')
            loan.save()
            messages.success(request, 'Loan created successfully.')
            return redirect('cxapp_list_loans')
    else:
        form = CxLoanForm()
        form.fields['employee'].queryset = CxEmployee.objects.filter(company=owner_profile)

    return render(request, 'Cxapp/loans_advances/create_loan.html', {'form': form})


def cxapp_view_loan_schedule(request, loan_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_view_loan_schedule)(request, loan_id)


def _view_loan_schedule(request, loan_id):
    owner_profile = request.cx_owner_profile
    loan = get_object_or_404(CxLoan, loan_id=loan_id, company=owner_profile)
    schedule = loan.amortization_schedule()
    return render(request, 'Cxapp/loans_advances/schedule.html', {
        'loan': loan, 'schedule': schedule, 'record_type': 'Loan',
    })


def cxapp_list_advances(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_list_advances)(request)


def _list_advances(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to view advances.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    advances = CxAdvance.objects.filter(company=owner_profile).select_related('employee').order_by('-created_at')
    return render(request, 'Cxapp/loans_advances/advance_list.html', {'advances': advances})


def cxapp_create_advance(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_create_advance)(request)


def _create_advance(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to manage advances.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    if request.method == 'POST':
        form = CxAdvanceForm(request.POST)
        if form.is_valid():
            advance = form.save(commit=False)
            advance.company = owner_profile
            advance.created_by = getattr(request.cx_sub_user, 'username', 'Owner')
            advance.save()
            messages.success(request, 'Advance created successfully.')
            return redirect('cxapp_list_advances')
    else:
        form = CxAdvanceForm()
        form.fields['employee'].queryset = CxEmployee.objects.filter(company=owner_profile)

    return render(request, 'Cxapp/loans_advances/create_advance.html', {'form': form})


def cxapp_view_advance_schedule(request, advance_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_view_advance_schedule)(request, advance_id)


def _view_advance_schedule(request, advance_id):
    owner_profile = request.cx_owner_profile
    advance = get_object_or_404(CxAdvance, advance_id=advance_id, company=owner_profile)
    schedule = advance.amortization_schedule()
    return render(request, 'Cxapp/loans_advances/schedule.html', {
        'loan': advance, 'schedule': schedule, 'record_type': 'Advance',
    })
