"""
Cxapp/app/increment.py
=========================
Employee-level salary Increment for the Cxapp portal — mirrors
Aapp.app.increment but scoped to CxOwnerProfile/CxEmployee/CxDesignation,
since Cxapp maintains its own independent model tree.

CxSalary.process() checks for an active increment before falling back
to designation.basic_pay/da for that employee/month — same override
pattern as Aapp's calculate_employee_salary().

DA override is optional here (new_da=0 means "use designation's DA
unchanged") since DA is typically Wage-Code-fixed rather than
individually negotiated, unlike basic pay.
"""

from decimal import Decimal

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Select, NumberInput, Textarea

from Cxapp.app.employee import CxEmployee


STATUS_CHOICES = [
    ('active', 'Active'),
    ('superseded', 'Superseded by Later Increment'),
    ('cancelled', 'Cancelled'),
]


class CxIncrement(models.Model):
    increment_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(CxEmployee, on_delete=models.CASCADE, related_name='increments')
    company = models.ForeignKey('Cxapp.CxOwnerProfile', on_delete=models.CASCADE)

    effective_from_month = models.PositiveSmallIntegerField()
    effective_from_year = models.PositiveIntegerField()

    old_basic_pay = models.DecimalField(max_digits=10, decimal_places=2, help_text="Snapshot at time of increment")
    new_basic_pay = models.DecimalField(max_digits=10, decimal_places=2)
    new_da = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True,
                                  help_text="0 = keep designation's DA unchanged")

    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='active')

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_increments'
        ordering = ['-effective_from_year', '-effective_from_month']
        verbose_name = "Employee Increment"

    def __str__(self):
        return f"Increment #{self.increment_id} - {self.employee.name} - eff. {self.effective_from_month}/{self.effective_from_year}"

    @property
    def basic_increase(self):
        return self.new_basic_pay - self.old_basic_pay

    @property
    def increase_percent(self):
        if not self.old_basic_pay:
            return Decimal('0')
        return ((self.new_basic_pay - self.old_basic_pay) / self.old_basic_pay * Decimal('100')).quantize(Decimal('0.01'))

    def applies_to(self, month, year):
        if self.status != 'active':
            return False
        return (year, month) >= (self.effective_from_year, self.effective_from_month)


class CxIncrementForm(ModelForm):
    class Meta:
        model = CxIncrement
        fields = ['employee', 'effective_from_month', 'effective_from_year',
                  'old_basic_pay', 'new_basic_pay', 'new_da', 'reason']
        widgets = {
            'employee': Select(attrs={'class': 'form-control'}),
            'effective_from_month': NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            'effective_from_year': NumberInput(attrs={'class': 'form-control'}),
            'old_basic_pay': NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': True}),
            'new_basic_pay': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'new_da': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'reason': Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


def get_active_increment(employee_obj, month, year):
    candidates = CxIncrement.objects.filter(
        employee=employee_obj, status='active'
    ).order_by('-effective_from_year', '-effective_from_month')

    for inc in candidates:
        if inc.applies_to(month, year):
            return inc
    return None


def get_effective_basic_da(employee_obj, designation, month, year):
    """
    Returns (basic_pay, da) — from the active CxIncrement if one
    applies, otherwise straight from the designation. Used by
    CxSalary.process() in place of reading designation.basic_pay/da
    directly.
    """
    inc = get_active_increment(employee_obj, month, year)
    if inc:
        da = inc.new_da if inc.new_da else (designation.da or Decimal('0.00'))
        return inc.new_basic_pay, da
    return designation.basic_pay or Decimal('0.00'), designation.da or Decimal('0.00')


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


def cxapp_list_increments(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_list_increments)(request)


def _list_increments(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to view increments.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    increments = CxIncrement.objects.filter(company=owner_profile).select_related('employee').order_by(
        '-effective_from_year', '-effective_from_month'
    )
    return render(request, 'Cxapp/increment_arrear/increment_list.html', {'increments': increments})


def cxapp_create_increment(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_create_increment)(request)


def _create_increment(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to manage increments.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    if request.method == 'POST':
        form = CxIncrementForm(request.POST)
        if form.is_valid():
            inc = form.save(commit=False)
            inc.company = owner_profile
            inc.created_by = getattr(request.cx_sub_user, 'username', 'Owner')

            CxIncrement.objects.filter(
                employee=inc.employee, company=owner_profile, status='active'
            ).update(status='superseded')

            inc.save()
            messages.success(request, 'Increment recorded successfully. Check Arrear module if backdated.')
            return redirect('cxapp_list_increments')
    else:
        form = CxIncrementForm()
        form.fields['employee'].queryset = CxEmployee.objects.filter(company=owner_profile, is_working=True)

    return render(request, 'Cxapp/increment_arrear/create_increment.html', {'form': form})


def cxapp_view_increment(request, increment_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_view_increment)(request, increment_id)


def _view_increment(request, increment_id):
    owner_profile = request.cx_owner_profile
    inc = get_object_or_404(CxIncrement, increment_id=increment_id, company=owner_profile)
    return render(request, 'Cxapp/increment_arrear/increment_detail.html', {'increment': inc})
