"""
Cxapp/app/arrear.py
======================
Employee Arrear for the Cxapp portal — mirrors Aapp.app.arrear but
scoped to CxOwnerProfile/CxEmployee/CxSalary, since Cxapp has its own
independent model tree and statutory-deduction engine.

Statutory recompute here uses Cxapp's fixed rates (EPF 12% flat on
Basic+DA, ESI 0.75% flat on gross, Labour flat Rs.20) — matching
CxSalary.process()'s hardcoded rates exactly, unlike Aapp's
per-designation percentage fields. No PT/IT recompute — Cxapp's salary
engine doesn't compute Professional Tax or Income Tax at all yet, so
there's nothing to recompute for those on an arrear.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Select, NumberInput, Textarea

from Cxapp.app.employee import CxEmployee

EPF_RATE = Decimal('0.12')
ESI_RATE = Decimal('0.0075')
LABOUR_FLAT = Decimal('20.00')  # matches CxSalary.process() — flat, not recomputed on shortfall


def _round(v):
    return Decimal(v).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class CxArrear(models.Model):
    arrear_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(CxEmployee, on_delete=models.CASCADE, related_name='arrears')
    company = models.ForeignKey('Cxapp.CxOwnerProfile', on_delete=models.CASCADE)
    increment = models.ForeignKey('Cxapp.CxIncrement', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='arrears')

    arrear_month = models.PositiveSmallIntegerField()
    arrear_year = models.PositiveIntegerField()

    old_basic_paid = models.DecimalField(max_digits=10, decimal_places=2)
    old_da_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    revised_basic = models.DecimalField(max_digits=10, decimal_places=2)
    revised_da = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    gross_shortfall = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    epf_recompute = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    esi_recompute = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    net_arrear_payable = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    payout_month = models.PositiveSmallIntegerField()
    payout_year = models.PositiveIntegerField()

    is_paid = models.BooleanField(default=False)
    remarks = models.CharField(max_length=500, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, blank=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_arrears'
        ordering = ['-arrear_year', '-arrear_month']
        verbose_name = "Employee Arrear"

    def __str__(self):
        return f"Arrear #{self.arrear_id} - {self.employee.name} - {self.arrear_month}/{self.arrear_year}"

    def compute(self):
        """Recomputes shortfall + statutory recompute. Does not save — caller saves after."""
        from Cxapp.app.process import CxSalary

        old_gross = self.old_basic_paid + self.old_da_paid
        new_gross = self.revised_basic + self.revised_da
        self.gross_shortfall = new_gross - old_gross

        old_salary = CxSalary.objects.filter(
            employee=self.employee, salary_month=self.arrear_month, salary_year=self.arrear_year
        ).first()

        eligibility = {}
        if hasattr(self.employee, 'statutory'):
            eligibility = self.employee.statutory.deduction_eligibility()

        if eligibility.get('epf'):
            self.epf_recompute = _round(self.gross_shortfall * EPF_RATE)
        else:
            self.epf_recompute = Decimal('0')

        if eligibility.get('esi'):
            self.esi_recompute = _round(self.gross_shortfall * ESI_RATE)
        else:
            self.esi_recompute = Decimal('0')

        # Labour Welfare Fund is a flat per-employee amount, not
        # proportional to pay — no recompute against a shortfall applies.

        total_recompute = self.epf_recompute + self.esi_recompute
        self.net_arrear_payable = self.gross_shortfall - total_recompute


class CxArrearForm(ModelForm):
    class Meta:
        model = CxArrear
        fields = ['employee', 'increment', 'arrear_month', 'arrear_year',
                  'old_basic_paid', 'old_da_paid', 'revised_basic', 'revised_da',
                  'payout_month', 'payout_year', 'remarks']
        widgets = {
            'employee': Select(attrs={'class': 'form-control'}),
            'increment': Select(attrs={'class': 'form-control'}),
            'arrear_month': NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            'arrear_year': NumberInput(attrs={'class': 'form-control'}),
            'old_basic_paid': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'old_da_paid': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'revised_basic': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'revised_da': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payout_month': NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            'payout_year': NumberInput(attrs={'class': 'form-control'}),
            'remarks': Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


def generate_arrears_for_increment(increment_obj, from_month, from_year, to_month, to_year, payout_month, payout_year):
    """Bulk-generates one CxArrear per already-processed month in range."""
    from Cxapp.app.process import CxSalary

    created = []
    y, m = from_year, from_month
    while (y, m) <= (to_year, to_month):
        salary = CxSalary.objects.filter(
            employee=increment_obj.employee, salary_month=m, salary_year=y
        ).first()
        if salary:
            basic_line = salary.lines.filter(component_name='Basic Pay').first()
            da_line = salary.lines.filter(component_name='Dearness Allowance').first()
            old_basic = basic_line.resolved_amount if basic_line else Decimal('0')
            old_da = da_line.resolved_amount if da_line else Decimal('0')

            arrear = CxArrear(
                employee=increment_obj.employee,
                company=increment_obj.company,
                increment=increment_obj,
                arrear_month=m,
                arrear_year=y,
                old_basic_paid=old_basic,
                old_da_paid=old_da,
                revised_basic=increment_obj.new_basic_pay,
                revised_da=increment_obj.new_da or old_da,
                payout_month=payout_month,
                payout_year=payout_year,
            )
            arrear.compute()
            arrear.save()
            created.append(arrear)
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return created


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


def cxapp_list_arrears(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_list_arrears)(request)


def _list_arrears(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to view arrears.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    arrears = CxArrear.objects.filter(company=owner_profile).select_related('employee').order_by(
        '-arrear_year', '-arrear_month'
    )
    return render(request, 'Cxapp/increment_arrear/arrear_list.html', {'arrears': arrears})


def cxapp_create_arrear(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_create_arrear)(request)


def _create_arrear(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to manage arrears.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    if request.method == 'POST':
        form = CxArrearForm(request.POST)
        if form.is_valid():
            arrear = form.save(commit=False)
            arrear.company = owner_profile
            arrear.created_by = getattr(request.cx_sub_user, 'username', 'Owner')
            arrear.compute()
            arrear.save()
            messages.success(request, 'Arrear computed and saved successfully.')
            return redirect('cxapp_list_arrears')
    else:
        form = CxArrearForm()
        form.fields['employee'].queryset = CxEmployee.objects.filter(company=owner_profile, is_working=True)
        from Cxapp.app.increment import CxIncrement
        form.fields['increment'].queryset = CxIncrement.objects.filter(company=owner_profile)
        form.fields['increment'].required = False

    return render(request, 'Cxapp/increment_arrear/create_arrear.html', {'form': form})


def cxapp_view_arrear(request, arrear_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_view_arrear)(request, arrear_id)


def _view_arrear(request, arrear_id):
    owner_profile = request.cx_owner_profile
    arrear = get_object_or_404(CxArrear, arrear_id=arrear_id, company=owner_profile)
    return render(request, 'Cxapp/increment_arrear/arrear_detail.html', {'arrear': arrear})
