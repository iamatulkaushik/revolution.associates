"""
Aapp/app/fnf_settlement.py
=============================
Full & Final (FnF) Settlement Engine — per pt_upgrades.md: automated
offboarding workflow computing leave encashment, notice period pay,
gratuity, loan/advance recoveries, and asset recovery in a single
click, plus Experience/LPC/Character certificate generation.

Reuses existing engines rather than duplicating logic:
  - Gratuity: Aapp.app.gratuity.gratuity_record.calculate_gratuity()
  - Leave balance: attendance.leave_balance() (gated on Shop Act)
  - Loan/Advance outstanding: Aapp.app.loans_advances (Loan, Advance)
  - Last drawn pay: most recent salary_slip for the employee

Asset recovery pulls from Aapp.app.asset_management.get_pending_asset_recovery()
if that module has pending recoveries on file for the employee; falls back
to the manual asset_recovery_amount field for anything raised outside
that system (e.g. verbal agreement, pre-module legacy record).
"""

from datetime import date
from decimal import Decimal

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Select, NumberInput, DateInput, Textarea, CheckboxInput

from Aapp.app.employee import employee as employee_model
from Sapp.app.company import Company


SETTLEMENT_STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('finalized', 'Finalized'),
    ('paid', 'Paid'),
]

CERTIFICATE_TYPES = ['experience', 'last_pay', 'character']


class FnFSettlement(models.Model):
    """One row per employee offboarding event."""
    settlement_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(employee_model, on_delete=models.CASCADE, related_name='fnf_settlements')
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    last_working_day = models.DateField()
    notice_period_days_required = models.PositiveSmallIntegerField(default=30)
    notice_period_days_served = models.PositiveSmallIntegerField(default=0)

    # Earnings
    leave_encashment_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    leave_encashment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notice_pay_recovery = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                               help_text="Positive = company owes employee (excess notice served); "
                                                         "Negative = employee owes company (short notice)")
    gratuity_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pending_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                          help_text="Any unpaid salary up to last working day")

    # Deductions / recoveries
    loan_outstanding_recovery = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advance_outstanding_recovery = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    asset_recovery_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                                 help_text="Auto-filled from pending Asset Recoveries on compute(); "
                                                           "editable to add/adjust for anything raised outside that system")
    other_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    net_settlement_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                                  help_text="Auto-computed: total earnings minus total recoveries")

    status = models.CharField(max_length=10, choices=SETTLEMENT_STATUS_CHOICES, default='draft')
    remarks = models.CharField(max_length=500, blank=True)

    finalized_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_fnf_settlements'
        ordering = ['-last_working_day']
        verbose_name = "Full & Final Settlement"

    def __str__(self):
        return f"FnF #{self.settlement_id} - {self.employee.name} - {self.get_status_display()}"

    @property
    def total_earnings(self):
        return (self.leave_encashment_amount + max(self.notice_pay_recovery, Decimal('0')) +
                self.gratuity_amount + self.pending_salary)

    @property
    def total_recoveries(self):
        return (self.loan_outstanding_recovery + self.advance_outstanding_recovery +
                self.asset_recovery_amount + self.other_deductions +
                abs(min(self.notice_pay_recovery, Decimal('0'))))

    def compute(self):
        """
        Runs the full one-click calculation. Populates every field on
        self from the employee's live records. Does not save — caller
        calls .save() after.

        Asset recovery: preserves whatever was in asset_recovery_amount
        BEFORE this call (i.e. manually entered on the form) and adds
        auto-pulled pending AssetRecovery totals on top. Safe to call
        compute() more than once only if the caller resets
        asset_recovery_amount to the original manual value first —
        the create view does this by calling compute() exactly once,
        immediately after form.save(commit=False).
        """
        from Aapp.app.salary_processing import salary_slip
        from Aapp.app.loans_advances import Loan, Advance
        from Aapp.app.gratuity import gratuity_record

        emp = self.employee

        # --- Last drawn pay (most recent processed slip) ---
        last_slip = salary_slip.objects.filter(employee_id=emp).order_by(
            '-processing_id__year', '-processing_id__month'
        ).first()
        last_basic = last_slip.basic_earned if last_slip else Decimal('0')
        last_da = last_slip.da_earned if last_slip else Decimal('0')

        # --- Leave encashment ---
        latest_attendance = None
        try:
            from Aapp.app.attandance import attendance
            latest_attendance = attendance.objects.filter(
                employee_id=emp
            ).order_by('-salary_year', '-salary_month').first()
        except Exception:
            pass

        if latest_attendance:
            balance = latest_attendance.leave_balance()
            if balance and balance > 0:
                self.leave_encashment_days = Decimal(str(balance))
                daily_rate = (last_basic + last_da) / Decimal('30') if (last_basic + last_da) else Decimal('0')
                self.leave_encashment_amount = (daily_rate * self.leave_encashment_days).quantize(Decimal('0.01'))
            else:
                self.leave_encashment_days = Decimal('0')
                self.leave_encashment_amount = Decimal('0')

        # --- Notice period pay/recovery ---
        shortfall_days = self.notice_period_days_required - self.notice_period_days_served
        daily_rate = (last_basic + last_da) / Decimal('30') if (last_basic + last_da) else Decimal('0')
        if shortfall_days > 0:
            # employee served less than required -> company recovers the shortfall
            self.notice_pay_recovery = -(daily_rate * Decimal(shortfall_days)).quantize(Decimal('0.01'))
        elif shortfall_days < 0:
            # employee served extra -> company pays the excess
            self.notice_pay_recovery = (daily_rate * Decimal(abs(shortfall_days))).quantize(Decimal('0.01'))
        else:
            self.notice_pay_recovery = Decimal('0')

        # --- Gratuity (reuses existing engine, does not duplicate it) ---
        years_of_service = Decimal('0')
        if emp.dateofjoining and self.last_working_day:
            days = (self.last_working_day - emp.dateofjoining).days
            years_of_service = (Decimal(days) / Decimal('365.25')).quantize(Decimal('0.01'))

        if years_of_service >= Decimal('5'):
            self.gratuity_amount = Decimal(str(
                gratuity_record.calculate_gratuity(last_basic, last_da, years_of_service)
            ))
        else:
            self.gratuity_amount = Decimal('0')  # not eligible, per Payment of Gratuity Act

        # --- Loan / Advance outstanding ---
        loan_total = Decimal('0')
        for loan in Loan.objects.filter(employee=emp, status='active'):
            remaining = loan.total_payable
            for row in loan.amortization_schedule():
                if (row['year'], row['month']) < (self.last_working_day.year, self.last_working_day.month):
                    remaining -= row['amount']
            loan_total += max(remaining, Decimal('0'))
        self.loan_outstanding_recovery = loan_total.quantize(Decimal('0.01'))

        advance_total = Decimal('0')
        for adv in Advance.objects.filter(employee=emp, status='active'):
            remaining = adv.total_payable
            for row in adv.amortization_schedule():
                if (row['year'], row['month']) < (self.last_working_day.year, self.last_working_day.month):
                    remaining -= row['amount']
            advance_total += max(remaining, Decimal('0'))
        self.advance_outstanding_recovery = advance_total.quantize(Decimal('0.01'))

        # --- Asset recovery (auto-pulled, additive to the manually
        # entered amount on the form — see compute() docstring on
        # call-once safety) ---
        from Aapp.app.asset_management import get_pending_asset_recovery
        auto_asset_recovery = get_pending_asset_recovery(emp)
        self.asset_recovery_amount = (self.asset_recovery_amount or Decimal('0')) + auto_asset_recovery

        # --- Net settlement ---
        self.net_settlement_amount = (self.total_earnings - self.total_recoveries).quantize(Decimal('0.01'))


class FnFSettlementForm(ModelForm):
    class Meta:
        model = FnFSettlement
        fields = ['employee', 'last_working_day', 'notice_period_days_required',
                  'notice_period_days_served', 'asset_recovery_amount',
                  'other_deductions', 'pending_salary', 'remarks']
        widgets = {
            'employee': Select(attrs={'class': 'form-control'}),
            'last_working_day': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notice_period_days_required': NumberInput(attrs={'class': 'form-control'}),
            'notice_period_days_served': NumberInput(attrs={'class': 'form-control'}),
            'asset_recovery_amount': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'other_deductions': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'pending_salary': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'remarks': Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


# =====================================================================
# VIEWS
# =====================================================================

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone


def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


@login_required
def list_fnf_settlements(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    settlements = FnFSettlement.objects.filter(company=company).select_related('employee').order_by(
        '-last_working_day'
    )
    rows = [{
        'cells': [
            s.settlement_id, s.employee.employeecode, s.employee.name,
            s.last_working_day, f"Rs. {s.net_settlement_amount}", s.get_status_display(),
        ],
        'actions': [
            {'url': reverse('view_fnf_settlement', args=[s.settlement_id]), 'label': 'View', 'css': 'edit'},
        ] + ([{'url': reverse('finalize_fnf_settlement', args=[s.settlement_id]), 'label': 'Finalize'}]
             if s.status == 'draft' else []),
    } for s in settlements]

    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Full & Final Settlements',
        'columns': ['ID', 'Emp Code', 'Name', 'Last Working Day', 'Net Amount', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('create_fnf_settlement'), 'add_label': 'Initiate FnF Settlement',
        'empty_message': 'No settlements initiated yet.',
    })


@login_required
def create_fnf_settlement(request):
    """One-click: form captures only the manual inputs, compute() fills the rest."""
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        form = FnFSettlementForm(request.POST)
        if form.is_valid():
            settlement = form.save(commit=False)
            settlement.company = company
            settlement.created_by = request.user.username
            settlement.compute()
            settlement.save()
            messages.success(request, 'FnF settlement calculated successfully. Review before finalizing.')
            return redirect('view_fnf_settlement', settlement_id=settlement.settlement_id)
    else:
        form = FnFSettlementForm()
        # Only employees already marked as leaving/left are eligible for FnF
        form.fields['employee'].queryset = employee_model.objects.filter(
            CompanyID=company, is_working=False
        )

    return render(request, 'Aapp/works/create_fnf.html', {'form': form, 'company': company})


@login_required
def view_fnf_settlement(request, settlement_id):
    company = _company(request)
    settlement = get_object_or_404(FnFSettlement, settlement_id=settlement_id, company=company)
    return render(request, 'Aapp/works/fnf_settlement_detail.html', {
        'settlement': settlement,
        'download_url': reverse('download_fnf_settlement', args=[settlement_id]),
        'cert_urls': {
            cert: reverse('download_fnf_certificate', args=[settlement_id, cert])
            for cert in CERTIFICATE_TYPES
        },
    })


@login_required
def finalize_fnf_settlement(request, settlement_id):
    company = _company(request)
    settlement = get_object_or_404(FnFSettlement, settlement_id=settlement_id, company=company)
    if settlement.status == 'draft':
        settlement.status = 'finalized'
        settlement.finalized_at = timezone.now()
        settlement.save(update_fields=['status', 'finalized_at'])
        messages.success(request, 'Settlement finalized.')
    return redirect('view_fnf_settlement', settlement_id=settlement_id)


@login_required
def download_fnf_settlement(request, settlement_id):
    from django.http import HttpResponse
    from Aapp.app.fnf_pdf import fnf_settlement_pdf

    company = _company(request)
    settlement = get_object_or_404(FnFSettlement, settlement_id=settlement_id, company=company)
    pdf_bytes = fnf_settlement_pdf(settlement)
    return HttpResponse(pdf_bytes, content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="fnf_settlement_{settlement_id}.pdf"'
    })


@login_required
def download_fnf_certificate(request, settlement_id, cert_type):
    from django.http import HttpResponse, Http404
    from Aapp.app.fnf_pdf import fnf_certificate_pdf

    if cert_type not in CERTIFICATE_TYPES:
        raise Http404("Unknown certificate type")

    company = _company(request)
    settlement = get_object_or_404(FnFSettlement, settlement_id=settlement_id, company=company)
    pdf_bytes = fnf_certificate_pdf(settlement, cert_type)
    return HttpResponse(pdf_bytes, content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="{cert_type}_certificate_{settlement_id}.pdf"'
    })
