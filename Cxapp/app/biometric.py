"""
Cxapp/app/biometric.py
=========================
Biometric/RFID device registration, shift definitions, and punch log
ingest for the Cxapp portal — mirrors Aapp's three-file split
(biometric_device.py + shift.py + punch_log.py) combined into one file
here since Cxapp's simpler model tree doesn't need the separation.

Same daemon-relay architecture as Aapp: an on-prem daemon polls the
physical device and pushes punches to ingest_punch() over HTTPS with a
device-level API key (no session auth, since the daemon runs
unattended).

Overtime: Cxapp's CxAttendance had no overtime concept before this
module — CxOvertimeHours below is a new supplementary field on
CxAttendance, and CxSalary.process() now adds an OT pay line using the
same 2x-hourly-basic-rate formula Aapp uses (STANDARD_WORKING_HOURS=8,
30-day month baseline), computed by _calculate_overtime() here rather
than importing Aapp's version (keeps Cxapp fully self-contained, matches
the rest of this app's independence from Aapp).
"""

from datetime import datetime, timedelta, date
from decimal import Decimal

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import TextInput, TimeInput, NumberInput, Select, DateInput
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

from Cxapp.app.employee import CxEmployee

STANDARD_WORKING_HOURS = Decimal('8')

DEVICE_TYPE_CHOICES = [
    ('biometric', 'Biometric (Fingerprint/Face)'),
    ('rfid', 'RFID Card Reader'),
]


class CxBiometricDevice(models.Model):
    device_id = models.AutoField(primary_key=True)
    company = models.ForeignKey('Cxapp.CxOwnerProfile', on_delete=models.CASCADE, related_name='biometric_devices')
    device_name = models.CharField(max_length=100)
    device_type = models.CharField(max_length=10, choices=DEVICE_TYPE_CHOICES)
    device_serial = models.CharField(max_length=100, unique=True)
    daemon_api_key = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_biometric_devices'
        verbose_name = "Biometric/RFID Device"

    def __str__(self):
        return f"{self.device_name} ({self.get_device_type_display()})"


class CxEmployeeDeviceMapping(models.Model):
    mapping_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(CxEmployee, on_delete=models.CASCADE, related_name='device_mappings')
    device = models.ForeignKey(CxBiometricDevice, on_delete=models.CASCADE, related_name='employee_mappings')
    device_user_id = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_employee_device_mapping'
        unique_together = ('device', 'device_user_id')
        verbose_name = "Employee Device Mapping"

    def __str__(self):
        return f"{self.employee.name} -> {self.device.device_name}"


class CxShift(models.Model):
    shift_id = models.AutoField(primary_key=True)
    company = models.ForeignKey('Cxapp.CxOwnerProfile', on_delete=models.CASCADE, related_name='shifts')
    shift_name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    grace_minutes = models.PositiveSmallIntegerField(default=10)
    is_night_shift = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_shifts'
        verbose_name = "Shift"

    def __str__(self):
        return f"{self.shift_name} ({self.start_time}-{self.end_time})"


class CxEmployeeShiftAssignment(models.Model):
    assignment_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(CxEmployee, on_delete=models.CASCADE, related_name='shift_assignments')
    shift = models.ForeignKey(CxShift, on_delete=models.CASCADE, related_name='assigned_employees')
    effective_from = models.DateField()

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_employee_shift_assignment'
        ordering = ['-effective_from']
        verbose_name = "Employee Shift Assignment"


class CxPunchLog(models.Model):
    punch_id = models.AutoField(primary_key=True)
    device = models.ForeignKey(CxBiometricDevice, on_delete=models.CASCADE, related_name='punches')
    employee = models.ForeignKey(CxEmployee, on_delete=models.CASCADE, related_name='punches')
    punch_datetime = models.DateTimeField()
    raw_device_user_id = models.CharField(max_length=50)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_punch_log'
        ordering = ['punch_datetime']
        indexes = [models.Index(fields=['employee', 'punch_datetime'])]
        verbose_name = "Punch Log"


class CxDailyAttendance(models.Model):
    daily_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(CxEmployee, on_delete=models.CASCADE, related_name='daily_attendance')
    company = models.ForeignKey('Cxapp.CxOwnerProfile', on_delete=models.CASCADE)
    attendance_date = models.DateField()

    first_in = models.DateTimeField(null=True, blank=True)
    last_out = models.DateTimeField(null=True, blank=True)
    shift = models.ForeignKey(CxShift, on_delete=models.SET_NULL, null=True, blank=True)
    late_minutes = models.PositiveIntegerField(default=0)
    early_leaving_minutes = models.PositiveIntegerField(default=0)
    overtime_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_present = models.BooleanField(default=False)
    is_lop = models.BooleanField(default=False)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_daily_attendance'
        unique_together = ('employee', 'attendance_date')
        ordering = ['-attendance_date']
        verbose_name = "Daily Attendance (Biometric)"


class CxBiometricDeviceForm(ModelForm):
    class Meta:
        model = CxBiometricDevice
        fields = ['device_name', 'device_type', 'device_serial']
        widgets = {
            'device_name': TextInput(attrs={'class': 'form-control'}),
            'device_type': Select(attrs={'class': 'form-control'}),
            'device_serial': TextInput(attrs={'class': 'form-control'}),
        }


class CxEmployeeDeviceMappingForm(ModelForm):
    class Meta:
        model = CxEmployeeDeviceMapping
        fields = ['employee', 'device', 'device_user_id']
        widgets = {
            'employee': Select(attrs={'class': 'form-control'}),
            'device': Select(attrs={'class': 'form-control'}),
            'device_user_id': TextInput(attrs={'class': 'form-control'}),
        }


class CxShiftForm(ModelForm):
    class Meta:
        model = CxShift
        fields = ['shift_name', 'start_time', 'end_time', 'grace_minutes', 'is_night_shift']
        widgets = {
            'shift_name': TextInput(attrs={'class': 'form-control'}),
            'start_time': TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'grace_minutes': NumberInput(attrs={'class': 'form-control'}),
        }


class CxEmployeeShiftAssignmentForm(ModelForm):
    class Meta:
        model = CxEmployeeShiftAssignment
        fields = ['employee', 'shift', 'effective_from']
        widgets = {
            'employee': Select(attrs={'class': 'form-control'}),
            'shift': Select(attrs={'class': 'form-control'}),
            'effective_from': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


def generate_api_key():
    import secrets
    return secrets.token_hex(32)


def resolve_employee(device, device_user_id):
    mapping = CxEmployeeDeviceMapping.objects.filter(
        device=device, device_user_id=device_user_id, is_active=True
    ).select_related('employee').first()
    return mapping.employee if mapping else None


def get_shift_for_date(employee_obj, on_date):
    assignment = CxEmployeeShiftAssignment.objects.filter(
        employee=employee_obj, effective_from__lte=on_date
    ).order_by('-effective_from').first()
    return assignment.shift if assignment else None


def _calculate_overtime(basic, overtime_hours):
    """Overtime = 2x hourly rate, hourly rate derived from basic pay. Self-contained, not imported from Aapp."""
    if overtime_hours <= 0 or basic <= 0:
        return Decimal('0')
    hourly_basic = basic / Decimal('30') / STANDARD_WORKING_HOURS
    return (hourly_basic * Decimal('2') * overtime_hours).quantize(Decimal('0.01'))


@csrf_exempt
def ingest_punch(request):
    """Daemon-facing endpoint. Auth via device api_key, not session — see module docstring."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    device = CxBiometricDevice.objects.filter(
        device_serial=payload.get('device_serial'),
        daemon_api_key=payload.get('api_key'),
        is_active=True,
    ).first()
    if not device:
        return JsonResponse({'error': 'Unknown device or invalid API key'}, status=403)

    device_user_id = payload.get('device_user_id')
    emp = resolve_employee(device, device_user_id)
    if not emp:
        return JsonResponse({'error': f'No employee mapped to device_user_id {device_user_id}'}, status=404)

    try:
        punch_dt = datetime.fromisoformat(payload.get('punch_datetime'))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid punch_datetime, expected ISO format'}, status=400)

    CxPunchLog.objects.create(
        device=device, employee=emp, punch_datetime=punch_dt, raw_device_user_id=device_user_id,
    )

    from django.utils import timezone
    device.last_sync_at = timezone.now()
    device.save(update_fields=['last_sync_at'])

    return JsonResponse({'status': 'ok'})


def aggregate_daily_attendance(employee_obj, on_date):
    """Pairs punches into first-in/last-out, computes late/early/OT against assigned shift."""
    punches = CxPunchLog.objects.filter(
        employee=employee_obj, punch_datetime__date=on_date
    ).order_by('punch_datetime')

    daily, _ = CxDailyAttendance.objects.get_or_create(
        employee=employee_obj, attendance_date=on_date,
        defaults={'company': employee_obj.company}
    )

    if not punches.exists():
        daily.first_in = None
        daily.last_out = None
        daily.is_present = False
        daily.is_lop = True  # Cxapp has no approved-leave-request model to cross-check yet
        daily.late_minutes = 0
        daily.early_leaving_minutes = 0
        daily.overtime_hours = Decimal('0')
        daily.save()
        return daily

    daily.first_in = punches.first().punch_datetime
    daily.last_out = punches.last().punch_datetime
    daily.is_present = True
    daily.is_lop = False

    shift = get_shift_for_date(employee_obj, on_date)
    daily.shift = shift

    if shift:
        shift_start = datetime.combine(on_date, shift.start_time)
        shift_end = datetime.combine(on_date, shift.end_time)
        if shift.is_night_shift or shift_end <= shift_start:
            shift_end += timedelta(days=1)

        grace_cutoff = shift_start + timedelta(minutes=shift.grace_minutes)
        daily.late_minutes = int((daily.first_in - shift_start).total_seconds() / 60) if daily.first_in > grace_cutoff else 0
        daily.early_leaving_minutes = int((shift_end - daily.last_out).total_seconds() / 60) if daily.last_out < shift_end else 0
        daily.overtime_hours = (
            Decimal(str(round((daily.last_out - shift_end).total_seconds() / 3600, 2)))
            if daily.last_out > shift_end else Decimal('0')
        )
    else:
        daily.late_minutes = 0
        daily.early_leaving_minutes = 0
        daily.overtime_hours = Decimal('0')

    daily.save()
    return daily


def get_overtime_hours_for_month(employee_obj, month, year):
    """
    Sums CxDailyAttendance.overtime_hours for the month — used by
    CxSalary.process() to add an OT pay line. Returns 0 if no daily
    attendance rows exist (i.e. no biometric device set up for this
    employee) — OT pay only applies where biometric tracking is active.
    """
    total = CxDailyAttendance.objects.filter(
        employee=employee_obj, attendance_date__year=year, attendance_date__month=month
    ).aggregate(total=models.Sum('overtime_hours'))['total']
    return total or Decimal('0')


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


def cxapp_list_devices(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_list_devices)(request)


def _list_devices(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to view devices.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    devices = CxBiometricDevice.objects.filter(company=owner_profile).order_by('device_name')
    return render(request, 'Cxapp/biometric/device_list.html', {'devices': devices})


def cxapp_create_device(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_create_device)(request)


def _create_device(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to register devices.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    if request.method == 'POST':
        form = CxBiometricDeviceForm(request.POST)
        if form.is_valid():
            device = form.save(commit=False)
            device.company = owner_profile
            device.daemon_api_key = generate_api_key()
            device.save()
            messages.success(request, f'Device registered. API key (copy now): {device.daemon_api_key}')
            return redirect('cxapp_list_devices')
    else:
        form = CxBiometricDeviceForm()

    return render(request, 'Cxapp/biometric/create_device.html', {'form': form})


def cxapp_list_device_mappings(request, device_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_list_device_mappings)(request, device_id)


def _list_device_mappings(request, device_id):
    owner_profile = request.cx_owner_profile
    device = get_object_or_404(CxBiometricDevice, device_id=device_id, company=owner_profile)
    mappings = CxEmployeeDeviceMapping.objects.filter(device=device).select_related('employee')
    return render(request, 'Cxapp/biometric/mapping_list.html', {'device': device, 'mappings': mappings})


def cxapp_create_device_mapping(request, device_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_create_device_mapping)(request, device_id)


def _create_device_mapping(request, device_id):
    owner_profile = request.cx_owner_profile
    device = get_object_or_404(CxBiometricDevice, device_id=device_id, company=owner_profile)

    if request.method == 'POST':
        form = CxEmployeeDeviceMappingForm(request.POST)
        if form.is_valid():
            mapping = form.save(commit=False)
            mapping.device = device
            mapping.save()
            messages.success(request, 'Employee mapped to device successfully.')
            return redirect('cxapp_list_device_mappings', device_id=device_id)
    else:
        form = CxEmployeeDeviceMappingForm(initial={'device': device})
        form.fields['employee'].queryset = CxEmployee.objects.filter(company=owner_profile, is_working=True)
        form.fields['device'].queryset = CxBiometricDevice.objects.filter(company=owner_profile)

    return render(request, 'Cxapp/biometric/create_mapping.html', {'form': form, 'device': device})


def cxapp_list_shifts(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_list_shifts)(request)


def _list_shifts(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to view shifts.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    shifts = CxShift.objects.filter(company=owner_profile).order_by('shift_name')
    return render(request, 'Cxapp/biometric/shift_list.html', {'shifts': shifts})


def cxapp_create_shift(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_create_shift)(request)


def _create_shift(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to manage shifts.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    if request.method == 'POST':
        form = CxShiftForm(request.POST)
        if form.is_valid():
            shift = form.save(commit=False)
            shift.company = owner_profile
            shift.save()
            messages.success(request, 'Shift created successfully.')
            return redirect('cxapp_list_shifts')
    else:
        form = CxShiftForm()

    return render(request, 'Cxapp/biometric/create_shift.html', {'form': form})


def cxapp_assign_shift(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_assign_shift)(request)


def _assign_shift(request):
    owner_profile = request.cx_owner_profile
    if request.method == 'POST':
        form = CxEmployeeShiftAssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Shift assigned successfully.')
            return redirect('cxapp_list_shifts')
    else:
        form = CxEmployeeShiftAssignmentForm()
        form.fields['employee'].queryset = CxEmployee.objects.filter(company=owner_profile, is_working=True)
        form.fields['shift'].queryset = CxShift.objects.filter(company=owner_profile, is_active=True)

    return render(request, 'Cxapp/biometric/assign_shift.html', {'form': form})
