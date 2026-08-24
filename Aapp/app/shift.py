"""
Aapp/app/shift.py
====================
Shift schedule definitions and employee-to-shift mapping, per
pt_upgrades.md: "shift capture" and "overtime auto calculate".

A Shift defines expected start/end time and grace period. Punch logs
(Aapp/app/punch_log.py) are compared against the employee's assigned
shift for that day to determine late arrival, early leaving, overtime
hours beyond shift end, and Loss of Pay (LOP) for unapproved full-day
absence.
"""

from datetime import datetime, timedelta, date

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import TextInput, TimeInput, NumberInput, Select, DateInput

from Aapp.app.employee import employee as employee_model
from Sapp.app.company import Company


class Shift(models.Model):
    """One shift definition (e.g. 'General', 'Night Shift A')."""
    shift_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='shifts')
    shift_name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    grace_minutes = models.PositiveSmallIntegerField(default=10, help_text="Late-arrival grace period")
    is_night_shift = models.BooleanField(default=False, help_text="True if end_time is on the next calendar day")
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_shifts'
        verbose_name = "Shift"

    def __str__(self):
        return f"{self.shift_name} ({self.start_time}–{self.end_time})"

    def shift_duration_hours(self):
        start_dt = datetime.combine(date.today(), self.start_time)
        end_dt = datetime.combine(date.today(), self.end_time)
        if self.is_night_shift or end_dt <= start_dt:
            end_dt += timedelta(days=1)
        return round((end_dt - start_dt).total_seconds() / 3600, 2)


class EmployeeShiftAssignment(models.Model):
    """
    Which shift an employee is on, effective from a given date. A new
    row supersedes older ones (checked by effective_from ordering, not
    an explicit status flag — simpler since shift changes are common
    and don't need the audit trail an Increment does).
    """
    assignment_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(employee_model, on_delete=models.CASCADE, related_name='shift_assignments')
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='assigned_employees')
    effective_from = models.DateField()

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_employee_shift_assignment'
        ordering = ['-effective_from']
        verbose_name = "Employee Shift Assignment"

    def __str__(self):
        return f"{self.employee.name} -> {self.shift.shift_name} from {self.effective_from}"


class ShiftForm(ModelForm):
    class Meta:
        model = Shift
        fields = ['shift_name', 'start_time', 'end_time', 'grace_minutes', 'is_night_shift']
        widgets = {
            'shift_name': TextInput(attrs={'class': 'form-control'}),
            'start_time': TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'grace_minutes': NumberInput(attrs={'class': 'form-control'}),
        }


class EmployeeShiftAssignmentForm(ModelForm):
    class Meta:
        model = EmployeeShiftAssignment
        fields = ['employee', 'shift', 'effective_from']
        widgets = {
            'employee': Select(attrs={'class': 'form-control'}),
            'shift': Select(attrs={'class': 'form-control'}),
            'effective_from': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


def get_shift_for_date(employee_obj, on_date):
    """Returns the Shift active for this employee on the given date, or None."""
    assignment = EmployeeShiftAssignment.objects.filter(
        employee=employee_obj, effective_from__lte=on_date
    ).order_by('-effective_from').first()
    return assignment.shift if assignment else None


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


@login_required
def list_shifts(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    shifts = Shift.objects.filter(company=company).order_by('shift_name')
    rows = [{
        'cells': [s.shift_name, s.start_time, s.end_time, s.grace_minutes,
                  s.shift_duration_hours(), 'Active' if s.is_active else 'Inactive'],
        'actions': [{'url': reverse('alter_shift', args=[s.shift_id]), 'label': 'Edit', 'css': 'edit'}],
    } for s in shifts]

    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Shifts',
        'columns': ['Name', 'Start', 'End', 'Grace (min)', 'Duration (hrs)', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('create_shift'), 'add_label': 'Add Shift',
        'empty_message': 'No shifts defined yet.',
    })


@login_required
def create_shift(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        form = ShiftForm(request.POST)
        if form.is_valid():
            shift = form.save(commit=False)
            shift.company = company
            shift.save()
            messages.success(request, 'Shift created successfully.')
            return redirect('list_shifts')
    else:
        form = ShiftForm()

    return render(request, 'Aapp/works/create_shift.html', {'form': form, 'company': company})


@login_required
def alter_shift(request, shift_id):
    company = _company(request)
    shift = get_object_or_404(Shift, shift_id=shift_id, company=company)

    if request.method == 'POST':
        form = ShiftForm(request.POST, instance=shift)
        if form.is_valid():
            form.save()
            messages.success(request, 'Shift updated successfully.')
            return redirect('list_shifts')
    else:
        form = ShiftForm(instance=shift)

    return render(request, 'Aapp/works/alter_shift.html', {'form': form, 'shift': shift})


@login_required
def assign_shift(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        form = EmployeeShiftAssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Shift assigned successfully.')
            return redirect('list_shifts')
    else:
        form = EmployeeShiftAssignmentForm()
        form.fields['employee'].queryset = employee_model.objects.filter(CompanyID=company, is_working=True)
        form.fields['shift'].queryset = Shift.objects.filter(company=company, is_active=True)

    return render(request, 'Aapp/works/assign_shift.html', {'form': form, 'company': company})
