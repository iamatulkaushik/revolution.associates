"""
Cxapp/app/process.py
======================
Salary processing module for the Cxapp (self-signup Company Owner)
portal. Computes a monthly salary run per employee from:
    - CxAttendance   (working days vs. designation's full-month baseline
                       — prorates allowances by attendance)
    - CxDesignation  (basic_pay, da — fixed per Wage Code 2019)
    - CxDesignationComponent (dynamic allowances/deductions, resolved
                       via resolved_amount(basic_pay))
    - CxEmployeeStatutory.deduction_eligibility() (EPF/ESI/Labour —
                       no registration, no deduction, same rule as
                       everywhere else in this codebase)

TABLE SPLIT — sensitivity/access-driven, same principle as employee.py
and attandance.py:
    CxSalary       — core payroll record, one per employee per month.
                     Read by Owner + HR routinely (payslips, totals).
    CxSalaryLine    — per-component breakdown (each allowance/deduction
                     as its own row with its resolved amount). Split out
                     because it's write-once/read-rarely audit detail —
                     routine salary list/summary views never need to
                     join every line item, only the totals stored on
                     CxSalary itself. Low access, mainly for payslip
                     generation and statutory register drill-down.

Allowances are prorated by attendance (working_day / designation's
expected working days for that month) — a component marked flat is
still scaled down if the employee didn't work the full month, since
that's the standard payroll convention; percentage-of-basic components
resolve off the (unprorated) basic first, then get the same proration
applied, consistent with how Basic/DA themselves are prorated below.

Deductions are NOT prorated — statutory deductions (EPF/ESI/Labour) are
computed off whatever gross was actually paid that month, and manual
deduction components are assumed to be intentional fixed amounts
(e.g. loan recovery) that don't scale with days worked.
"""

from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.db import models, transaction
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404

from Cxapp.app.employee import CxEmployee
from Cxapp.app.designation import CxDesignation, CxDesignationComponent
from Cxapp.app.attandance import CxAttendance, MONTH_CHOICES, YEAR_CHOICES

TWOPLACES = Decimal('0.01')


def _q(value):
    return Decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


# ── Core salary table ─────────────────────────────────────────────────────────

class CxSalary(models.Model):
    """
    One row per employee per month — the processed payslip record.
    Snapshot fields (employee_code, name, father/husband name, UAN,
    ESI, DOB, DOJ) are copied at process-time rather than joined live,
    so a payslip stays accurate even if the employee's master data
    changes later (matches standard payroll audit practice — a payslip
    should reflect what was true when it was issued).
    """
    salary_id       = models.AutoField(primary_key=True)
    attendance       = models.OneToOneField(CxAttendance, on_delete=models.PROTECT,
                                            related_name='salary')
    company          = models.ForeignKey('Cxapp.CxOwnerProfile', on_delete=models.CASCADE,
                                         related_name='salaries')
    employee         = models.ForeignKey(CxEmployee, on_delete=models.PROTECT,
                                         related_name='salaries')
    designation      = models.ForeignKey(CxDesignation, on_delete=models.PROTECT,
                                         related_name='salaries')

    salary_month     = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    salary_year      = models.PositiveSmallIntegerField(choices=YEAR_CHOICES)

    # ── Employee data snapshot (frozen at process-time) ──
    employee_code     = models.CharField(max_length=20)
    employee_name      = models.CharField(max_length=255)
    father_husband_name = models.CharField(max_length=255, blank=True)
    uan               = models.CharField(max_length=50, blank=True)
    esi               = models.CharField(max_length=20, blank=True)
    date_of_birth      = models.DateField(null=True, blank=True)
    date_of_joining     = models.DateField(null=True, blank=True)

    # ── Totals (component-level detail lives in CxSalaryLine) ──
    total_allowances  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_deductions  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount      = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    # ── Audit ──
    created_by        = models.CharField(max_length=50, blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_by         = models.CharField(max_length=50, blank=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_salary'
        unique_together = ('employee', 'salary_month', 'salary_year')
        ordering = ['-salary_year', '-salary_month']
        verbose_name = 'Salary'
        verbose_name_plural = 'Salaries'

    def __str__(self):
        return f'{self.employee_code} — {self.get_salary_month_display()} {self.salary_year}'

    @classmethod
    def process(cls, attendance, created_by=''):
        """
        Compute and persist a salary record from an CxAttendance row.
        Recomputes from scratch if a CxSalary already exists for this
        attendance (re-processing overwrites, doesn't duplicate).
        """
        employee = attendance.employee
        designation = employee.designation
        company = attendance.company

        # Proration factor: working_day / designation's expected days.
        # Falls back to 1 (no proration) if the designation has no
        # explicit working-day baseline configured, or if attendance
        # somehow exceeds it (treated as full attendance, capped at 1).
        expected_days = Decimal('30')  # standard payroll month baseline
        proration = Decimal('1.00')
        if attendance.working_day and expected_days > 0:
            proration = min(Decimal('1.00'), Decimal(attendance.working_day) / expected_days)

        basic_pay = designation.basic_pay or Decimal('0.00')
        da = designation.da or Decimal('0.00')

        prorated_basic = _q(basic_pay * proration)
        prorated_da = _q(da * proration)

        lines = []
        total_allowances = prorated_basic + prorated_da
        total_deductions = Decimal('0.00')

        lines.append({
            'component_name': 'Basic Pay', 'component_type': CxSalaryLine.TYPE_ALLOWANCE,
            'resolved_amount': prorated_basic, 'is_prorated': True,
        })
        lines.append({
            'component_name': 'Dearness Allowance', 'component_type': CxSalaryLine.TYPE_ALLOWANCE,
            'resolved_amount': prorated_da, 'is_prorated': True,
        })

        for component in designation.components.filter(is_deleted=False, is_active=True):
            resolved = component.resolved_amount(basic_pay)
            if component.component_type == CxDesignationComponent.TYPE_ALLOWANCE:
                prorated = _q(resolved * proration)
                total_allowances += prorated
                lines.append({
                    'component_name': component.component_name, 'component_type': CxSalaryLine.TYPE_ALLOWANCE,
                    'resolved_amount': prorated, 'is_prorated': True,
                })
            else:
                # Deductions are NOT prorated — see module docstring.
                total_deductions += resolved
                lines.append({
                    'component_name': component.component_name, 'component_type': CxSalaryLine.TYPE_DEDUCTION,
                    'resolved_amount': resolved, 'is_prorated': False,
                })

        # Statutory deductions — gated the same as everywhere else in
        # this codebase: no registration on file, no deduction.
        #
        # EPF is computed on Basic+DA only (not full gross) — this is
        # the statutory EPF wage base under the EPF & MP Act; HRA and
        # other special allowances are excluded. ESI is computed on
        # gross wages (all allowances), which IS the correct ESI wage
        # definition. Labour Welfare Fund is a flat per-employee
        # contribution, unrelated to wages.
        if hasattr(employee, 'statutory'):
            eligibility = employee.statutory.deduction_eligibility()
            epf_da_base = prorated_basic + prorated_da
            if eligibility.get('epf'):
                amount = _q(epf_da_base * Decimal('0.12'))
                total_deductions += amount
                lines.append({
                    'component_name': 'EPF (Statutory)', 'component_type': CxSalaryLine.TYPE_DEDUCTION,
                    'resolved_amount': amount, 'is_prorated': False,
                })
            if eligibility.get('esi'):
                amount = _q(total_allowances * Decimal('0.0075'))
                total_deductions += amount
                lines.append({
                    'component_name': 'ESI (Statutory)', 'component_type': CxSalaryLine.TYPE_DEDUCTION,
                    'resolved_amount': amount, 'is_prorated': False,
                })
            if eligibility.get('labour'):
                amount = Decimal('20.00')  # flat LWF employee contribution
                total_deductions += amount
                lines.append({
                    'component_name': 'LABOUR (Statutory)', 'component_type': CxSalaryLine.TYPE_DEDUCTION,
                    'resolved_amount': amount, 'is_prorated': False,
                })

        total_amount = total_allowances - total_deductions

        with transaction.atomic():
            existing = cls.objects.filter(attendance=attendance).first()
            salary, created = cls.objects.update_or_create(
                attendance=attendance,
                defaults=dict(
                    company=company, employee=employee, designation=designation,
                    salary_month=attendance.attandance_month, salary_year=attendance.attandance_year,
                    employee_code=employee.employee_code, employee_name=employee.name,
                    father_husband_name=employee.father_husband_name,
                    uan=getattr(getattr(employee, 'statutory', None), 'uan_number', ''),
                    esi=getattr(getattr(employee, 'statutory', None), 'esi_number', ''),
                    date_of_birth=employee.date_of_birth,
                    date_of_joining=getattr(getattr(employee, 'employment', None), 'date_of_joining', None),
                    total_allowances=_q(total_allowances),
                    total_deductions=_q(total_deductions),
                    total_amount=_q(total_amount),
                    updated_by=created_by,
                ),
            )
            if existing is None:
                salary.created_by = created_by
                salary.save(update_fields=['created_by'])
            salary.lines.all().delete()
            CxSalaryLine.objects.bulk_create([
                CxSalaryLine(salary=salary, **line) for line in lines
            ])

        return salary


# ── Line items (component-level breakdown, low access) ────────────────────────

class CxSalaryLine(models.Model):
    """
    One row per allowance/deduction component that fed into a CxSalary
    total. Kept separate from CxSalary itself: routine salary list/
    summary views only need the totals already stored there, and this
    detail is only pulled for payslip rendering or statutory register
    drill-down — low-frequency, audit-oriented access.
    """
    TYPE_ALLOWANCE = 'allowance'
    TYPE_DEDUCTION = 'deduction'
    LINE_TYPES = [
        (TYPE_ALLOWANCE, 'Allowance'),
        (TYPE_DEDUCTION, 'Deduction'),
    ]

    salary            = models.ForeignKey(CxSalary, on_delete=models.CASCADE, related_name='lines')
    component_name     = models.CharField(max_length=100)
    component_type     = models.CharField(max_length=10, choices=LINE_TYPES)
    resolved_amount     = models.DecimalField(max_digits=10, decimal_places=2)
    is_prorated        = models.BooleanField(default=False)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_salary_line'
        ordering = ['component_type', 'component_name']
        verbose_name = 'Salary Line Item'
        verbose_name_plural = 'Salary Line Items'

    def __str__(self):
        return f'{self.salary.employee_code} — {self.component_name}: ₹{self.resolved_amount}'


# ── Forms ────────────────────────────────────────────────────────────────────

class CxSalaryProcessForm(forms.Form):
    """
    Not a ModelForm — picks an existing CxAttendance row to process
    into a CxSalary, rather than editing salary fields directly
    (salary figures are always derived, never hand-entered).
    """
    attendance = forms.ModelChoiceField(queryset=CxAttendance.objects.none(), label='Attendance Record')

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company is not None:
            self.fields['attendance'].queryset = CxAttendance.objects.filter(
                company=company
            ).exclude(salary__isnull=False).select_related('employee').order_by(
                '-attandance_year', '-attandance_month'
            )


class CxSalaryBulkProcessForm(forms.Form):
    """Process every un-processed attendance record for a given month/year in one action."""
    salary_month = forms.ChoiceField(choices=MONTH_CHOICES)
    salary_year = forms.ChoiceField(choices=YEAR_CHOICES)


# ── Views ────────────────────────────────────────────────────────────────────
# Payroll totals are sensitive — Owner + HR only, same tier as
# employee KYC/banking. Other sub-user roles cannot process or view.

def _can_manage_payroll(request):
    if getattr(request, 'cx_sub_user', None) is None:
        return True  # owner always can
    return request.cx_sub_user.get_role_permissions().get('wages', False)


def cxapp_salary_list(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_salary_list)(request)


def _salary_list(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to view payroll.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    salaries = CxSalary.objects.filter(company=owner_profile).select_related('employee', 'designation')

    month = request.GET.get('month')
    year = request.GET.get('year')
    if month:
        salaries = salaries.filter(salary_month=month)
    if year:
        salaries = salaries.filter(salary_year=year)

    return render(request, 'Cxapp/processing/salary_list.html', {
        'salaries': salaries,
        'month_choices': MONTH_CHOICES,
        'year_choices': YEAR_CHOICES,
        'selected_month': int(month) if month else None,
        'selected_year': int(year) if year else None,
    })


def cxapp_salary_process(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_salary_process)(request)


def _salary_process(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to process payroll.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile

    if request.method == 'POST':
        form = CxSalaryProcessForm(request.POST, company=owner_profile)
        if form.is_valid():
            attendance = form.cleaned_data['attendance']
            salary = CxSalary.process(attendance, created_by=request.user.username)
            messages.success(request, f"Salary processed for {salary.employee_name} "
                                       f"— {salary.get_salary_month_display()} {salary.salary_year}: "
                                       f"₹{salary.total_amount}.")
            return redirect('cxapp_salary_detail', salary_id=salary.salary_id)
    else:
        form = CxSalaryProcessForm(company=owner_profile)

    return render(request, 'Cxapp/processing/salary_process_form.html', {'form': form})


def cxapp_salary_bulk_process(request):
    from Cxapp.views import owner_only
    return owner_only(_salary_bulk_process)(request)


def _salary_bulk_process(request):
    owner_profile = request.cx_owner_profile

    if request.method == 'POST':
        form = CxSalaryBulkProcessForm(request.POST)
        if form.is_valid():
            month = int(form.cleaned_data['salary_month'])
            year = int(form.cleaned_data['salary_year'])
            pending = CxAttendance.objects.filter(
                company=owner_profile, attandance_month=month, attandance_year=year
            ).exclude(salary__isnull=False)

            processed_count = 0
            for attendance in pending:
                CxSalary.process(attendance, created_by=request.user.username)
                processed_count += 1

            if processed_count:
                messages.success(request, f'Processed {processed_count} salary record(s) for '
                                           f'{dict(MONTH_CHOICES)[month]} {year}.')
            else:
                messages.info(request, 'No unprocessed attendance records found for that period.')
            return redirect('cxapp_salary_list')
    else:
        form = CxSalaryBulkProcessForm()

    return render(request, 'Cxapp/processing/salary_bulk_process_form.html', {'form': form})


def cxapp_salary_detail(request, salary_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_salary_detail)(request, salary_id)


def _salary_detail(request, salary_id):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to view payroll.')
        return redirect('cxapp_dashboard')

    salary = get_object_or_404(CxSalary, salary_id=salary_id, company=request.cx_owner_profile)
    allowance_lines = salary.lines.filter(component_type=CxSalaryLine.TYPE_ALLOWANCE)
    deduction_lines = salary.lines.filter(component_type=CxSalaryLine.TYPE_DEDUCTION)

    return render(request, 'Cxapp/processing/salary_detail.html', {
        'salary': salary,
        'allowance_lines': allowance_lines,
        'deduction_lines': deduction_lines,
    })


def cxapp_salary_reprocess(request, salary_id):
    from Cxapp.views import owner_only
    return owner_only(_salary_reprocess)(request, salary_id)


def _salary_reprocess(request, salary_id):
    salary = get_object_or_404(CxSalary, salary_id=salary_id, company=request.cx_owner_profile)
    if request.method == 'POST':
        salary = CxSalary.process(salary.attendance, created_by=request.user.username)
        messages.success(request, 'Salary reprocessed with current designation/attendance data.')
    return redirect('cxapp_salary_detail', salary_id=salary.salary_id)
