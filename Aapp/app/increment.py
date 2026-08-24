"""
Aapp/app/increment.py
=======================
Employee-level salary Increment — per pt_upgrades.md: "saprate module/
process for arrear and increment", "two different files, Arrear |
Increment". This is the Increment half.

An Increment is a per-employee override of basic/HRA/allowances,
effective from a given month/year, distinct from the shared Designation
pay scale. calculate_employee_salary() in salary_processing.py checks
for an active increment before falling back to designation.basicpay/hra
for that employee/month.

Backdating: if effective_from is a past month relative to when the
increment is entered, the Arrear module (Aapp/app/arrear.py) computes
the shortfall for already-processed months — Increment itself only
changes what future/unprocessed months pay.
"""

from datetime import date
from decimal import Decimal

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Select, NumberInput, DateInput, Textarea

from Aapp.app.employee import employee as employee_model
from Sapp.app.company import Company


STATUS_CHOICES = [
    ('active', 'Active'),
    ('superseded', 'Superseded by Later Increment'),
    ('cancelled', 'Cancelled'),
]


class Increment(models.Model):
    """
    One row per increment event. Only 'active' increments are
    considered live; when a newer increment is created for the same
    employee, the older one should be marked 'superseded' (done in the
    create view, not via signal — matches this codebase's explicit
    management-over-signals pattern).
    """
    increment_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(employee_model, on_delete=models.CASCADE, related_name='increments')
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    effective_from_month = models.PositiveSmallIntegerField()
    effective_from_year = models.PositiveIntegerField()

    old_basicpay = models.DecimalField(max_digits=10, decimal_places=2, help_text="Snapshot at time of increment")
    old_hra = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    new_basicpay = models.DecimalField(max_digits=10, decimal_places=2)
    new_hra = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    new_da = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
    new_conveyance = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
    new_special_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)

    reason = models.CharField(max_length=255, blank=True, help_text="e.g. Annual increment, Promotion, Performance")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='active')

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_increments'
        ordering = ['-effective_from_year', '-effective_from_month']
        verbose_name = "Employee Increment"

    def __str__(self):
        return f"Increment #{self.increment_id} - {self.employee.name} - eff. {self.effective_from_month}/{self.effective_from_year}"

    @property
    def basic_increase(self):
        return self.new_basicpay - self.old_basicpay

    @property
    def increase_percent(self):
        if not self.old_basicpay:
            return Decimal('0')
        return ((self.new_basicpay - self.old_basicpay) / self.old_basicpay * Decimal('100')).quantize(Decimal('0.01'))

    def applies_to(self, month, year):
        """True if this increment is in effect for the given month/year."""
        if self.status != 'active':
            return False
        return (year, month) >= (self.effective_from_year, self.effective_from_month)


class IncrementForm(ModelForm):
    class Meta:
        model = Increment
        fields = ['employee', 'effective_from_month', 'effective_from_year',
                  'old_basicpay', 'old_hra', 'new_basicpay', 'new_hra',
                  'new_da', 'new_conveyance', 'new_special_allowance', 'reason']
        widgets = {
            'employee': Select(attrs={'class': 'form-control'}),
            'effective_from_month': NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            'effective_from_year': NumberInput(attrs={'class': 'form-control'}),
            'old_basicpay': NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': True}),
            'old_hra': NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': True}),
            'new_basicpay': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'new_hra': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'new_da': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'new_conveyance': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'new_special_allowance': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'reason': Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


def get_active_increment(employee_obj, month, year):
    """
    Returns the most recent 'active' Increment applicable to this
    employee for the given month/year, or None if none applies —
    caller falls back to designation pay scale in that case.
    """
    candidates = Increment.objects.filter(
        employee=employee_obj, status='active'
    ).order_by('-effective_from_year', '-effective_from_month')

    for inc in candidates:
        if inc.applies_to(month, year):
            return inc
    return None


def get_effective_pay(employee_obj, desig, month, year):
    """
    Returns a dict of {basicpay, hra, da, conveyance, specialallowance}
    — from the active Increment if one applies, otherwise straight from
    the designation. Used by salary_processing.calculate_employee_salary
    in place of reading desig fields directly for these five components.
    """
    inc = get_active_increment(employee_obj, month, year)
    if inc:
        return {
            'basicpay': inc.new_basicpay,
            'hra': inc.new_hra,
            'da': inc.new_da if inc.new_da else Decimal(str(desig.da)),
            'conveyance': inc.new_conveyance if inc.new_conveyance else Decimal(str(desig.conveyance)),
            'specialallowance': inc.new_special_allowance if inc.new_special_allowance else Decimal(str(desig.specialallowance)),
        }
    return {
        'basicpay': Decimal(str(desig.basicpay)),
        'hra': Decimal(str(desig.hra)),
        'da': Decimal(str(desig.da)),
        'conveyance': Decimal(str(desig.conveyance)),
        'specialallowance': Decimal(str(desig.specialallowance)),
    }


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
def list_increments(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    increments = Increment.objects.filter(company=company).select_related('employee').order_by(
        '-effective_from_year', '-effective_from_month'
    )
    rows = [{
        'cells': [
            i.increment_id, i.employee.employeecode, i.employee.name,
            f"{i.effective_from_month}/{i.effective_from_year}",
            f"Rs. {i.old_basicpay}", f"Rs. {i.new_basicpay}", f"{i.increase_percent}%",
            i.get_status_display(),
        ],
        'actions': [
            {'url': reverse('view_increment_schedule', args=[i.increment_id]), 'label': 'Schedule', 'css': 'edit'},
        ],
    } for i in increments]

    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Employee Increments',
        'columns': ['ID', 'Emp Code', 'Name', 'Effective (M/Y)', 'Old Basic', 'New Basic', 'Increase %', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('create_increment'), 'add_label': 'Add Increment',
        'empty_message': 'No increments on record yet.',
    })


@login_required
def create_increment(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        form = IncrementForm(request.POST)
        if form.is_valid():
            inc = form.save(commit=False)
            inc.company = company
            inc.created_by = request.user.username

            # Supersede any prior active increment for this employee
            Increment.objects.filter(
                employee=inc.employee, company=company, status='active'
            ).update(status='superseded')

            inc.save()
            messages.success(request, 'Increment recorded successfully. Check Arrear module if backdated.')
            return redirect('list_increments')
    else:
        form = IncrementForm()
        form.fields['employee'].queryset = employee_model.objects.filter(CompanyID=company, is_working=True)

    return render(request, 'Aapp/works/create_increment.html', {'form': form, 'company': company})


@login_required
def view_increment_schedule(request, increment_id):
    """Print/record view — per pt_upgrades.md 'saprate schedule for print and record'."""
    company = _company(request)
    inc = get_object_or_404(Increment, increment_id=increment_id, company=company)
    return render(request, 'Aapp/works/increment_schedule.html', {
        'increment': inc,
        'download_url': reverse('download_increment_schedule', args=[increment_id]),
    })


@login_required
def download_increment_schedule(request, increment_id):
    from django.http import HttpResponse
    from Aapp.app.increment_pdf import increment_schedule_pdf

    company = _company(request)
    inc = get_object_or_404(Increment, increment_id=increment_id, company=company)
    pdf_bytes = increment_schedule_pdf(inc)
    return HttpResponse(pdf_bytes, content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="increment_{increment_id}.pdf"'
    })
