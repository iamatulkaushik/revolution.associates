"""
Sapp/app/professional_tax.py
==============================
Pan-India Professional Tax (PT) slab engine.

PT is a state-levied tax, not central — slabs vary by state, some states
have zero PT (fail-closed, same "no registration/rule = no deduction"
philosophy used everywhere else: EPF, ESI, LWF).

Reference: state Professional Tax Acts. Rates below are the commonly
published monthly salary slabs as of FY 2025-26. Aatul should verify each
state's current notified slab before going live — PT slabs change via
state government notifications, not central law, and are not bundled
under the central Labour Codes.
"""

from datetime import date

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Select, TextInput, DateInput, NumberInput

from Sapp.app.state_district import State


class PTSlab(models.Model):
    """
    One monthly salary bracket for one state.
    salary_to = NULL means 'and above' (open-ended top bracket).
    """
    pt_slab_id = models.AutoField(primary_key=True)
    state = models.ForeignKey(State, related_name="pt_slabs", on_delete=models.CASCADE)
    salary_from = models.DecimalField(max_digits=10, decimal_places=2)
    salary_to = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    monthly_tax = models.DecimalField(max_digits=8, decimal_places=2)
    effective_from = models.DateField(default=date.today)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        upper = self.salary_to if self.salary_to is not None else "and above"
        return f"{self.state.name}: {self.salary_from}-{upper} -> Rs.{self.monthly_tax}"

    class Meta:
        app_label = 'Sapp'
        db_table = "sa_pt_slabs"
        verbose_name = "Professional Tax Slab"
        verbose_name_plural = "Professional Tax Slabs"
        ordering = ['state', 'salary_from']


class PTSlabForm(ModelForm):
    class Meta:
        model = PTSlab
        fields = ['state', 'salary_from', 'salary_to', 'monthly_tax', 'effective_from', 'is_active']
        widgets = {
            'state': Select(attrs={'class': 'form-control'}),
            'salary_from': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'salary_to': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'monthly_tax': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'effective_from': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


def get_pt_amount(state, gross_salary, on_date=None):
    """
    Returns the monthly PT amount (Decimal) for a given state and gross
    salary. Fail-closed: no state, no matching slab, or no active rule
    on the given date -> returns 0. Same pattern as get_company_gates()
    used for EPF/ESI/LWF everywhere in this codebase.

    on_date defaults to today; pass a specific date for backdated
    arrears/FnF calculations against the slab that was effective then.
    """
    if state is None or gross_salary is None:
        return 0

    check_date = on_date or date.today()

    slab = (
        PTSlab.objects.filter(
            state=state,
            is_active=True,
            salary_from__lte=gross_salary,
            effective_from__lte=check_date,
        )
        .filter(
            models.Q(salary_to__gte=gross_salary) | models.Q(salary_to__isnull=True)
        )
        .order_by('-effective_from')
        .first()
    )

    if not slab:
        return 0

    return slab.monthly_tax


def list_pt_states():
    """States that currently have at least one active PT slab on file."""
    return State.objects.filter(pt_slabs__is_active=True).distinct().order_by('name')
