"""
Cxapp/app/fnf_settlement.py
==============================
Full & Final Settlement for the Cxapp portal — mirrors
Aapp.app.fnf_settlement but scoped to CxOwnerProfile/CxEmployee/CxSalary/
CxLoan/CxAdvance, since Cxapp has its own independent model tree.

Gratuity is computed inline with the standard Payment of Gratuity Act
formula (15/26 * last drawn basic+DA * years of service, eligible only
at 5+ years) — Cxapp has no separate gratuity module to reuse (Aapp's
gratuity_record.calculate_gratuity() is Aapp-only and not accessible
here without an awkward cross-app FK).

Asset/Expense recovery pulls from Cxapp.app.asset_management.
get_pending_asset_recovery() — additive to any manually entered amount,
same call-once-safety caveat as Aapp's version (see compute() docstring).
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Select, NumberInput, DateInput, Textarea

from Cxapp.app.employee import CxEmployee

GRATUITY_DAYS_PER_YEAR = Decimal('15')
GRATUITY_MONTH_DAYS = Decimal('26')
GRATUITY_MIN_YEARS = Decimal('5')

SETTLEMENT_STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('finalized', 'Finalized'),
    ('paid', 'Paid'),
]

CERTIFICATE_TYPES = ['experience', 'last_pay', 'character']


def _round(v):
    return Decimal(v).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class CxFnFSettlement(models.Model):
    settlement_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(CxEmployee, on_delete=models.CASCADE, related_name='fnf_settlements')
    company = models.ForeignKey('Cxapp.CxOwnerProfile', on_delete=models.CASCADE)

    last_working_day = models.DateField()
    notice_period_days_required = models.PositiveSmallIntegerField(default=30)
    notice_period_days_served = models.PositiveSmallIntegerField(default=0)

    leave_encashment_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    leave_encashment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notice_pay_recovery = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gratuity_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pending_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    loan_outstanding_recovery = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advance_outstanding_recovery = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    asset_recovery_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                                 help_text="Auto-filled from pending CxAssetRecovery on compute(); "
                                                           "editable to add/adjust manually")
    other_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    net_settlement_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(max_length=10, choices=SETTLEMENT_STATUS_CHOICES, default='draft')
    remarks = models.CharField(max_length=500, blank=True)

    finalized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_fnf_settlements'
        ordering = ['-last_working_day']
        verbose_name = "Full & Final Settlement"

    def __str__(self):
        return f"FnF #{self.settlement_id} - {self.employee.name}"

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
        """Runs the full one-click calculation. Does not save — caller saves after."""
        from Cxapp.app.process import CxSalary
        from Cxapp.app.loans_advances import CxLoan, CxAdvance, get_outstanding_balance

        emp = self.employee

        last_salary = CxSalary.objects.filter(employee=emp).order_by(
            '-salary_year', '-salary_month'
        ).first()

        # Basic+DA aren't stored as separate totals on CxSalary (only
        # total_allowances is) — pull them from the line items instead.
        last_basic = Decimal('0')
        last_da = Decimal('0')
        if last_salary:
            basic_line = last_salary.lines.filter(component_name='Basic Pay').first()
            da_line = last_salary.lines.filter(component_name='Dearness Allowance').first()
            last_basic = basic_line.resolved_amount if basic_line else Decimal('0')
            last_da = da_line.resolved_amount if da_line else Decimal('0')

        # --- Leave encashment (earned_leave lives directly on CxAttendance) ---
        latest_attendance = emp.attendances.order_by('-attandance_year', '-attandance_month').first()
        if latest_attendance and latest_attendance.earned_leave > 0:
            self.leave_encashment_days = latest_attendance.earned_leave
            daily_rate = (last_basic + last_da) / Decimal('30') if (last_basic + last_da) else Decimal('0')
            self.leave_encashment_amount = _round(daily_rate * self.leave_encashment_days)
        else:
            self.leave_encashment_days = Decimal('0')
            self.leave_encashment_amount = Decimal('0')

        # --- Notice period pay/recovery ---
        shortfall_days = self.notice_period_days_required - self.notice_period_days_served
        daily_rate = (last_basic + last_da) / Decimal('30') if (last_basic + last_da) else Decimal('0')
        if shortfall_days > 0:
            self.notice_pay_recovery = -_round(daily_rate * Decimal(shortfall_days))
        elif shortfall_days < 0:
            self.notice_pay_recovery = _round(daily_rate * Decimal(abs(shortfall_days)))
        else:
            self.notice_pay_recovery = Decimal('0')

        # --- Gratuity (inline formula — see module docstring) ---
        date_of_joining = getattr(getattr(emp, 'employment', None), 'date_of_joining', None)
        years_of_service = Decimal('0')
        if date_of_joining and self.last_working_day:
            days = (self.last_working_day - date_of_joining).days
            years_of_service = (Decimal(days) / Decimal('365.25')).quantize(Decimal('0.01'))

        if years_of_service >= GRATUITY_MIN_YEARS:
            self.gratuity_amount = _round(
                (last_basic + last_da) * GRATUITY_DAYS_PER_YEAR / GRATUITY_MONTH_DAYS * years_of_service
            )
        else:
            self.gratuity_amount = Decimal('0')

        # --- Loan / Advance outstanding ---
        loan_total = Decimal('0')
        for loan in CxLoan.objects.filter(employee=emp, status='active'):
            loan_total += get_outstanding_balance(loan, self.last_working_day.month, self.last_working_day.year)
        self.loan_outstanding_recovery = _round(loan_total)

        advance_total = Decimal('0')
        for adv in CxAdvance.objects.filter(employee=emp, status='active'):
            advance_total += get_outstanding_balance(adv, self.last_working_day.month, self.last_working_day.year)
        self.advance_outstanding_recovery = _round(advance_total)

        # --- Asset recovery (auto-pulled, additive to manual entry) ---
        from Cxapp.app.asset_management import get_pending_asset_recovery
        auto_asset_recovery = get_pending_asset_recovery(emp)
        self.asset_recovery_amount = (self.asset_recovery_amount or Decimal('0')) + auto_asset_recovery

        # --- Net settlement ---
        self.net_settlement_amount = _round(self.total_earnings - self.total_recoveries)


class CxFnFSettlementForm(ModelForm):
    class Meta:
        model = CxFnFSettlement
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

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone


def _can_manage_payroll(request):
    if getattr(request, 'cx_sub_user', None) is None:
        return True
    return request.cx_sub_user.get_role_permissions().get('wages', False)


def cxapp_list_fnf(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_list_fnf)(request)


def _list_fnf(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to view settlements.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    settlements = CxFnFSettlement.objects.filter(company=owner_profile).select_related('employee').order_by(
        '-last_working_day'
    )
    return render(request, 'Cxapp/fnf/list.html', {'settlements': settlements})


def cxapp_create_fnf(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_create_fnf)(request)


def _create_fnf(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to manage settlements.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    if request.method == 'POST':
        form = CxFnFSettlementForm(request.POST)
        if form.is_valid():
            settlement = form.save(commit=False)
            settlement.company = owner_profile
            settlement.created_by = getattr(request.cx_sub_user, 'username', 'Owner')
            settlement.compute()
            settlement.save()
            messages.success(request, 'FnF settlement calculated successfully.')
            return redirect('cxapp_view_fnf', settlement_id=settlement.settlement_id)
    else:
        form = CxFnFSettlementForm()
        form.fields['employee'].queryset = CxEmployee.objects.filter(company=owner_profile, is_working=False)

    return render(request, 'Cxapp/fnf/create.html', {'form': form})


def cxapp_view_fnf(request, settlement_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_view_fnf)(request, settlement_id)


def _view_fnf(request, settlement_id):
    owner_profile = request.cx_owner_profile
    settlement = get_object_or_404(CxFnFSettlement, settlement_id=settlement_id, company=owner_profile)
    return render(request, 'Cxapp/fnf/detail.html', {'settlement': settlement})


def cxapp_finalize_fnf(request, settlement_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_finalize_fnf)(request, settlement_id)


def _finalize_fnf(request, settlement_id):
    owner_profile = request.cx_owner_profile
    settlement = get_object_or_404(CxFnFSettlement, settlement_id=settlement_id, company=owner_profile)
    if settlement.status == 'draft':
        settlement.status = 'finalized'
        settlement.finalized_at = timezone.now()
        settlement.save(update_fields=['status', 'finalized_at'])
        messages.success(request, 'Settlement finalized.')
    return redirect('cxapp_view_fnf', settlement_id=settlement_id)


def cxapp_download_fnf(request, settlement_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_download_fnf)(request, settlement_id)


def _download_fnf(request, settlement_id):
    from django.http import HttpResponse
    from Cxapp.app.fnf_pdf import cx_fnf_settlement_pdf

    owner_profile = request.cx_owner_profile
    settlement = get_object_or_404(CxFnFSettlement, settlement_id=settlement_id, company=owner_profile)
    pdf_bytes = cx_fnf_settlement_pdf(settlement)
    return HttpResponse(pdf_bytes, content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="fnf_settlement_{settlement_id}.pdf"'
    })


def cxapp_download_fnf_certificate(request, settlement_id, cert_type):
    from Cxapp.views import cx_login_required
    return cx_login_required(_download_fnf_certificate)(request, settlement_id, cert_type)


def _download_fnf_certificate(request, settlement_id, cert_type):
    from django.http import HttpResponse, Http404
    from Cxapp.app.fnf_pdf import cx_fnf_certificate_pdf

    if cert_type not in CERTIFICATE_TYPES:
        raise Http404("Unknown certificate type")

    owner_profile = request.cx_owner_profile
    settlement = get_object_or_404(CxFnFSettlement, settlement_id=settlement_id, company=owner_profile)
    pdf_bytes = cx_fnf_certificate_pdf(settlement, cert_type)
    return HttpResponse(pdf_bytes, content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="{cert_type}_certificate_{settlement_id}.pdf"'
    })
