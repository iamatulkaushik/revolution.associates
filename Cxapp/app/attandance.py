"""
Cxapp/app/attandance.py
=========================
Attendance module for the Cxapp (self-signup Company Owner) portal.

TABLE SPLIT — sensitivity-driven, same principle as employee.py:
    CxAttendance          — core monthly attendance record, low-medium
                             sensitivity, touched by HR/Operator/Front
                             Desk routinely for every employee every
                             month. High read volume.
    CxAttendanceMaternity  — maternity leave + benefit details, HIGH
                             sensitivity (health/personal data under
                             the Maternity Benefit Act), 1:1 with
                             CxAttendance, only created for the rare
                             month it's actually relevant. Kept out of
                             the core table so routine attendance
                             reads never carry this data along, and so
                             access can be restricted independently
                             (Owner + HR only, same as KYC/Banking).

leave_balance() gates on the company's Shop Act registration the same
way Aapp's attendance model does — no registration, no leave balance.
"""

from django import forms
from django.db import models
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404

from Cxapp.app.employee import CxEmployee
from Cxapp.app.statutory_gates import get_company_gates


MONTH_CHOICES = [
    (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
    (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
    (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
]
YEAR_CHOICES = [(y, y) for y in range(2026, 2037)]  # 2026–2036


# ── Core attendance table ─────────────────────────────────────────────────────

class CxAttendance(models.Model):
    """
    One row per employee per month. Core table — broad sub-user read
    access (HR, Front Desk, Operator all touch this routinely).
    Maternity details live separately in CxAttendanceMaternity.
    """
    attendance_id      = models.AutoField(primary_key=True)
    company             = models.ForeignKey('Cxapp.CxOwnerProfile', on_delete=models.CASCADE,
                                            related_name='attendances')
    employee            = models.ForeignKey(CxEmployee, on_delete=models.CASCADE,
                                            related_name='attendances')
    employee_code        = models.CharField(max_length=20)

    attandance_month     = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    attandance_year       = models.PositiveSmallIntegerField(choices=YEAR_CHOICES)

    # ── Attendance ──
    working_day          = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    holidays             = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    casual_leave          = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    earned_leave          = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sick_leave            = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    comp_leave            = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    work_pay             = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # ── Leave record ──
    leave_earned          = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    leave_lapsed          = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    leave_encashment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    leave_wages_paid       = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # ── Process ──
    is_bulk              = models.BooleanField(default=False)

    # ── Audit ──
    created_by           = models.CharField(max_length=50, blank=True)
    created_at            = models.DateTimeField(auto_now_add=True)
    updated_by            = models.CharField(max_length=50, blank=True)
    updated_at            = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_attendance'
        unique_together = ('employee', 'attandance_month', 'attandance_year')
        ordering = ['-attandance_year', '-attandance_month']
        verbose_name = 'Attendance'
        verbose_name_plural = 'Attendance Records'

    def __str__(self):
        return f'{self.employee_code} — {self.get_attandance_month_display()} {self.attandance_year}'

    def save(self, *args, **kwargs):
        if not self.employee_code and self.employee_id:
            self.employee_code = self.employee.employee_code
        super().save(*args, **kwargs)

    def leave_balance(self):
        """
        Gated by the company's Shop Act registration — same rule as
        Aapp.app.attandance.attendance.leave_balance(). No registration
        on file, no leave balance available (returns None, not zero).
        """
        gates = get_company_gates(self.company.company)
        if not gates.get('shop_act'):
            return None
        return self.leave_earned - self.leave_lapsed

    @property
    def has_maternity_record(self):
        return hasattr(self, 'maternity')


# ── Maternity table (1:1, HIGH sensitivity) ───────────────────────────────────

class CxAttendanceMaternity(models.Model):
    """
    Maternity leave + benefit details for a specific attendance month.
    Kept separate from the core table: it's rare (one employee, a few
    months a year at most), sensitive health/personal data under the
    Maternity Benefit Act, and shouldn't ride along on every routine
    attendance read/list. Access restricted to Owner + HR, same as
    Employee KYC/Banking.
    """
    attendance             = models.OneToOneField(CxAttendance, on_delete=models.CASCADE,
                                                   related_name='maternity')

    # ── Maternity details ──
    expected_delivery_date  = models.DateField(null=True, blank=True)
    actual_delivery_date    = models.DateField(null=True, blank=True)
    maternity_leave_start    = models.DateField(null=True, blank=True)
    maternity_leave_end      = models.DateField(null=True, blank=True)
    actual_return_date      = models.DateField(null=True, blank=True)

    # ── Maternity benefits ──
    benefit_days           = models.PositiveIntegerField(null=True, blank=True)
    benefit_amount          = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    medical_bonus           = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    nursing_breaks          = models.PositiveIntegerField(null=True, blank=True,
                                                          help_text='Number of nursing breaks per day')

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_attendance_maternity'
        verbose_name = 'Maternity Record'
        verbose_name_plural = 'Maternity Records'

    def __str__(self):
        return f'Maternity — {self.attendance.employee_code} ({self.attendance.get_attandance_month_display()} {self.attendance.attandance_year})'


# ── Forms ────────────────────────────────────────────────────────────────────

class CxAttendanceForm(forms.ModelForm):
    class Meta:
        model = CxAttendance
        fields = ['employee', 'attandance_month', 'attandance_year',
                  'working_day', 'holidays', 'casual_leave', 'earned_leave',
                  'sick_leave', 'comp_leave', 'work_pay',
                  'leave_earned', 'leave_lapsed', 'leave_encashment_amount',
                  'leave_wages_paid', 'is_bulk']
        widgets = {
            'attandance_month': forms.Select(attrs={'class': 'form-control'}),
            'attandance_year': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company is not None:
            self.fields['employee'].queryset = CxEmployee.objects.filter(
                company=company, is_deleted=False, is_working=True
            )

    def clean(self):
        cleaned = super().clean()
        employee = cleaned.get('employee')
        month = cleaned.get('attandance_month')
        year = cleaned.get('attandance_year')
        if employee and month and year:
            qs = CxAttendance.objects.filter(employee=employee, attandance_month=month, attandance_year=year)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    f'An attendance record already exists for {employee.name} '
                    f'in {dict(MONTH_CHOICES)[month]} {year}.'
                )
        return cleaned


class CxAttendanceMaternityForm(forms.ModelForm):
    class Meta:
        model = CxAttendanceMaternity
        fields = ['expected_delivery_date', 'actual_delivery_date',
                  'maternity_leave_start', 'maternity_leave_end', 'actual_return_date',
                  'benefit_days', 'benefit_amount', 'medical_bonus', 'nursing_breaks']
        widgets = {
            'expected_delivery_date': forms.DateInput(attrs={'type': 'date'}),
            'actual_delivery_date': forms.DateInput(attrs={'type': 'date'}),
            'maternity_leave_start': forms.DateInput(attrs={'type': 'date'}),
            'maternity_leave_end': forms.DateInput(attrs={'type': 'date'}),
            'actual_return_date': forms.DateInput(attrs={'type': 'date'}),
        }


# ── Views ────────────────────────────────────────────────────────────────────
# Same access pattern as employee.py: HR-role sub-users and Owner get
# full access; other roles get list/read via ROLE_PERMISSIONS['attendance'].

def _can_manage_attendance(request):
    if getattr(request, 'cx_sub_user', None) is None:
        return True  # owner always can
    return request.cx_sub_user.get_role_permissions().get('attendance', False)


def _can_manage_maternity(request):
    """Maternity is HIGH sensitivity — owner + HR only, same gate as employee KYC/banking."""
    if getattr(request, 'cx_sub_user', None) is None:
        return True
    return request.cx_sub_user.get_role_permissions().get('employees', False)


def cxapp_attendance_list(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_attendance_list)(request)


def _attendance_list(request):
    owner_profile = request.cx_owner_profile
    records = CxAttendance.objects.filter(company=owner_profile).select_related('employee')

    month = request.GET.get('month')
    year = request.GET.get('year')
    if month:
        records = records.filter(attandance_month=month)
    if year:
        records = records.filter(attandance_year=year)

    return render(request, 'Cxapp/attendance/attendance_list.html', {
        'records': records,
        'month_choices': MONTH_CHOICES,
        'year_choices': YEAR_CHOICES,
        'selected_month': int(month) if month else None,
        'selected_year': int(year) if year else None,
        'can_manage': _can_manage_attendance(request),
    })


def cxapp_attendance_create(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_attendance_create)(request)


def _attendance_create(request):
    if not _can_manage_attendance(request):
        messages.error(request, 'You do not have permission to add attendance records.')
        return redirect('cxapp_attendance_list')

    owner_profile = request.cx_owner_profile

    if request.method == 'POST':
        form = CxAttendanceForm(request.POST, company=owner_profile)
        if form.is_valid():
            record = form.save(commit=False)
            record.company = owner_profile
            record.created_by = request.user.username
            record.updated_by = request.user.username
            record.save()
            messages.success(request, f"Attendance recorded for {record.employee.name} "
                                       f"— {record.get_attandance_month_display()} {record.attandance_year}.")
            return redirect('cxapp_attendance_detail', attendance_id=record.attendance_id)
    else:
        form = CxAttendanceForm(company=owner_profile)

    return render(request, 'Cxapp/attendance/attendance_form.html', {
        'form': form, 'is_new': True,
        'month_choices': MONTH_CHOICES, 'year_choices': YEAR_CHOICES,
    })


def cxapp_attendance_edit(request, attendance_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_attendance_edit)(request, attendance_id)


def _attendance_edit(request, attendance_id):
    if not _can_manage_attendance(request):
        messages.error(request, 'You do not have permission to edit attendance records.')
        return redirect('cxapp_attendance_detail', attendance_id=attendance_id)

    record = get_object_or_404(CxAttendance, attendance_id=attendance_id, company=request.cx_owner_profile)

    if request.method == 'POST':
        form = CxAttendanceForm(request.POST, instance=record, company=request.cx_owner_profile)
        if form.is_valid():
            record = form.save(commit=False)
            record.updated_by = request.user.username
            record.save()
            messages.success(request, 'Attendance record updated.')
            return redirect('cxapp_attendance_detail', attendance_id=record.attendance_id)
    else:
        form = CxAttendanceForm(instance=record, company=request.cx_owner_profile)

    return render(request, 'Cxapp/attendance/attendance_form.html', {
        'form': form, 'is_new': False, 'record': record,
        'month_choices': MONTH_CHOICES, 'year_choices': YEAR_CHOICES,
    })


def cxapp_attendance_detail(request, attendance_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_attendance_detail)(request, attendance_id)


def _attendance_detail(request, attendance_id):
    record = get_object_or_404(CxAttendance, attendance_id=attendance_id, company=request.cx_owner_profile)
    can_see_maternity = _can_manage_maternity(request)

    return render(request, 'Cxapp/attendance/attendance_detail.html', {
        'record': record,
        'maternity': getattr(record, 'maternity', None) if can_see_maternity else None,
        'can_manage': _can_manage_attendance(request),
        'can_manage_maternity': can_see_maternity,
        'leave_balance': record.leave_balance(),
    })


def cxapp_attendance_delete(request, attendance_id):
    from Cxapp.views import owner_only
    return owner_only(_attendance_delete)(request, attendance_id)


def _attendance_delete(request, attendance_id):
    record = get_object_or_404(CxAttendance, attendance_id=attendance_id, company=request.cx_owner_profile)
    if request.method == 'POST':
        record.delete()
        messages.success(request, 'Attendance record deleted.')
        return redirect('cxapp_attendance_list')
    return render(request, 'Cxapp/attendance/attendance_delete.html', {'record': record})


def cxapp_attendance_maternity_edit(request, attendance_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_attendance_maternity_edit)(request, attendance_id)


def _attendance_maternity_edit(request, attendance_id):
    if not _can_manage_maternity(request):
        messages.error(request, 'Maternity details are restricted to the Owner and HR role.')
        return redirect('cxapp_attendance_detail', attendance_id=attendance_id)

    record = get_object_or_404(CxAttendance, attendance_id=attendance_id, company=request.cx_owner_profile)
    instance = getattr(record, 'maternity', None)

    if request.method == 'POST':
        form = CxAttendanceMaternityForm(request.POST, instance=instance)
        if form.is_valid():
            maternity = form.save(commit=False)
            maternity.attendance = record
            maternity.save()
            messages.success(request, 'Maternity details saved.')
            return redirect('cxapp_attendance_detail', attendance_id=record.attendance_id)
    else:
        form = CxAttendanceMaternityForm(instance=instance)

    return render(request, 'Cxapp/attendance/attendance_maternity_form.html', {
        'form': form, 'record': record,
    })
