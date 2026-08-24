"""
Aapp/app/punch_log.py
========================
Raw punch (in/out) storage and daily aggregation, per pt_upgrades.md:
"RFID Integration for employees in and out timing (overtime auto
calculate)" and "RFID attandnace sheet schedule for referance and
record".

Flow:
  1. On-prem daemon polls the physical device, pushes each punch to
     ingest_punch() via POST /Aapp/biometric/ingest/ (see urls.py).
  2. aggregate_daily_attendance() runs once per day (or on demand) per
     employee: pairs punches into a first-in/last-out for that day,
     compares against their assigned Shift, and computes late minutes,
     early-leaving minutes, overtime hours beyond shift end.
  3. LOP (Loss of Pay) is flagged when a working day has zero punches
     and no approved leave on file for that date (checked against
     leave_management, not duplicated here).
  4. sync_month_to_attendance() rolls up a month of DailyAttendance rows
     into the existing monthly `attendance` model's overtime_hours field
     — this module feeds that model, it doesn't replace it.
"""

from datetime import datetime, timedelta, date
from decimal import Decimal

from django.db import models
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

from Aapp.app.employee import employee as employee_model
from Sapp.app.company import Company
from Aapp.app.biometric_device import BiometricDevice, resolve_employee
from Aapp.app.shift import get_shift_for_date


PUNCH_TYPE_CHOICES = [('in', 'Check In'), ('out', 'Check Out')]


class PunchLog(models.Model):
    """One raw punch event as received from the daemon."""
    punch_id = models.AutoField(primary_key=True)
    device = models.ForeignKey(BiometricDevice, on_delete=models.CASCADE, related_name='punches')
    employee = models.ForeignKey(employee_model, on_delete=models.CASCADE, related_name='punches')
    punch_type = models.CharField(max_length=3, choices=PUNCH_TYPE_CHOICES, blank=True,
                                   help_text="Some devices don't distinguish in/out — left blank if unknown, "
                                             "resolved by aggregate_daily_attendance() using sequence order instead")
    punch_datetime = models.DateTimeField()
    raw_device_user_id = models.CharField(max_length=50)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_punch_log'
        ordering = ['punch_datetime']
        indexes = [models.Index(fields=['employee', 'punch_datetime'])]
        verbose_name = "Punch Log"


class DailyAttendance(models.Model):
    """One row per employee per calendar day, derived from PunchLog + Shift."""
    daily_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(employee_model, on_delete=models.CASCADE, related_name='daily_attendance')
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    attendance_date = models.DateField()

    first_in = models.DateTimeField(null=True, blank=True)
    last_out = models.DateTimeField(null=True, blank=True)

    shift = models.ForeignKey('Aapp.Shift', on_delete=models.SET_NULL, null=True, blank=True)
    late_minutes = models.PositiveIntegerField(default=0)
    early_leaving_minutes = models.PositiveIntegerField(default=0)
    overtime_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    is_present = models.BooleanField(default=False)
    is_lop = models.BooleanField(default=False, help_text="Loss of Pay — no punches, no approved leave")

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_daily_attendance'
        unique_together = ('employee', 'attendance_date')
        ordering = ['-attendance_date']
        verbose_name = "Daily Attendance (Biometric)"


@csrf_exempt
def ingest_punch(request):
    """
    POST endpoint the on-prem daemon calls for each punch it reads off
    the device. Expects JSON:
        {"device_serial": "...", "api_key": "...",
         "device_user_id": "...", "punch_datetime": "2026-08-23T09:05:00",
         "punch_type": "in"}  # punch_type optional

    Auth is the device's own api_key, not a logged-in user session —
    the daemon runs unattended, so session auth doesn't apply here.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    device = BiometricDevice.objects.filter(
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

    PunchLog.objects.create(
        device=device,
        employee=emp,
        punch_type=payload.get('punch_type', ''),
        punch_datetime=punch_dt,
        raw_device_user_id=device_user_id,
    )

    from django.utils import timezone
    device.last_sync_at = timezone.now()
    device.save(update_fields=['last_sync_at'])

    return JsonResponse({'status': 'ok'})


def aggregate_daily_attendance(employee_obj, on_date):
    """
    Pairs the day's punches into first-in/last-out, compares against
    the employee's shift, computes late/early/overtime. Approved-leave
    check for LOP is done via a lazy import of leave_management to
    avoid a circular import at module load time.
    """
    punches = PunchLog.objects.filter(
        employee=employee_obj, punch_datetime__date=on_date
    ).order_by('punch_datetime')

    daily, _ = DailyAttendance.objects.get_or_create(
        employee=employee_obj, attendance_date=on_date,
        defaults={'company': employee_obj.CompanyID}
    )

    if not punches.exists():
        daily.first_in = None
        daily.last_out = None
        daily.is_present = False

        has_approved_leave = False
        try:
            from Aapp.app.leave_management import leave_request
            has_approved_leave = leave_request.objects.filter(
                employee=employee_obj, from_date__lte=on_date, to_date__gte=on_date, status='approved'
            ).exists()
        except Exception:
            pass

        daily.is_lop = not has_approved_leave
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
        if daily.first_in > grace_cutoff:
            daily.late_minutes = int((daily.first_in - shift_start).total_seconds() / 60)
        else:
            daily.late_minutes = 0

        if daily.last_out < shift_end:
            daily.early_leaving_minutes = int((shift_end - daily.last_out).total_seconds() / 60)
        else:
            daily.early_leaving_minutes = 0

        if daily.last_out > shift_end:
            overtime_seconds = (daily.last_out - shift_end).total_seconds()
            daily.overtime_hours = Decimal(str(round(overtime_seconds / 3600, 2)))
        else:
            daily.overtime_hours = Decimal('0')
    else:
        # No shift assigned — cannot compute late/early/OT meaningfully
        daily.late_minutes = 0
        daily.early_leaving_minutes = 0
        daily.overtime_hours = Decimal('0')

    daily.save()
    return daily


def sync_month_to_attendance(employee_obj, month, year):
    """
    Rolls up a month of DailyAttendance rows into the existing monthly
    `attendance` model — sums overtime_hours and counts LOP days.
    Feeds the existing model rather than replacing it; caller is
    responsible for creating/fetching the attendance row first.
    """
    from Aapp.app.attandance import attendance as attendance_model
    import calendar as _cal

    last_day = _cal.monthrange(year, month)[1]
    daily_rows = DailyAttendance.objects.filter(
        employee=employee_obj, attendance_date__year=year, attendance_date__month=month
    )

    total_overtime = sum((d.overtime_hours for d in daily_rows), start=Decimal('0'))
    lop_days = daily_rows.filter(is_lop=True).count()

    att = attendance_model.objects.filter(
        employee_id=employee_obj, salary_month=month, salary_year=year
    ).first()
    if att:
        att.overtime_hours = total_overtime
        # working_days reduced by LOP days — existing field, not a new one
        if lop_days:
            att.working_days = max(Decimal('0'), att.working_days - Decimal(lop_days))
        att.save(update_fields=['overtime_hours', 'working_days'])

    return {'total_overtime': total_overtime, 'lop_days': lop_days}


# =====================================================================
# VIEWS
# =====================================================================

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse


def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


@login_required
def download_punch_sheet(request, month, year):
    from django.http import HttpResponse
    from Aapp.app.punch_report_pdf import punch_sheet_pdf

    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    pdf_bytes = punch_sheet_pdf(company, month, year)
    return HttpResponse(pdf_bytes, content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="punch_sheet_{month}_{year}.pdf"'
    })


@login_required
def view_daily_attendance(request, month, year):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    rows = (DailyAttendance.objects
            .filter(company=company, attendance_date__year=year, attendance_date__month=month)
            .select_related('employee').order_by('employee__employeecode', 'attendance_date'))

    return render(request, 'Aapp/works/daily_attendance_list.html', {
        'rows': rows, 'company': company, 'month': month, 'year': year,
        'download_url': reverse('download_punch_sheet', args=[month, year]),
    })
