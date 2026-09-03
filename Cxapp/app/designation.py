"""
Cxapp/app/designation.py
=========================
Designation & salary structure regime for the Cxapp (self-signup Company
Owner) portal. Independent from Aapp's legacy `designation` model —
Aapp keeps its fixed-column structure untouched; Cxapp uses this
Code-on-Wages-2019-compliant structure instead.

Wage Code 2019, Section 2(y) + 1st proviso:
    Basic Pay + Dearness Allowance (+ Retaining Allowance, not modelled
    here as it's rare outside seasonal/retained roles) must be >= 50%
    of total remuneration. HRA and all other allowances are EXCLUDED
    components and must not push the excluded total past 50%.

Design:
    - CxDesignation: fixed columns for Basic and DA only. HRA is
      NOT a fixed column — it's a dynamic component like every
      other allowance/deduction.
    - CxDesignationComponent: one row per allowance or deduction
      attached to a designation. Flat amount or percentage-of-basic.
      Includes a `is_wage_code_excluded` flag so the 50% floor check
      knows which components count against the exclusion cap.
"""

from decimal import Decimal

from django.db import models
from django.core.exceptions import ValidationError

from Sapp.app.company import Company


class CxDesignation(models.Model):
    """
    Designation under the Cxapp regime. Only Basic and DA are fixed —
    every other pay component is a CxDesignationComponent row.
    """
    company             = models.ForeignKey(Company, on_delete=models.CASCADE,
                                             related_name='cx_designations',
                                             db_column='CompanyID')
    designation_name    = models.CharField(max_length=255)
    is_dailywage        = models.BooleanField(default=False)
    dailywage_rate      = models.DecimalField(max_digits=10, decimal_places=2,
                                               default=Decimal('0.00'))

    # ── Fixed, statutory wage-floor components (Wage Code 2019) ─────────────
    basic_pay           = models.DecimalField(max_digits=10, decimal_places=2,
                                               default=Decimal('0.00'))
    da                  = models.DecimalField(max_digits=10, decimal_places=2,
                                               default=Decimal('0.00'))

    is_active           = models.BooleanField(default=True)
    is_deleted          = models.BooleanField(default=False)
    created_by          = models.CharField(max_length=255)
    updated_by          = models.CharField(max_length=255)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_designation'
        ordering = ['designation_name']
        verbose_name = 'Designation (Cxapp)'
        verbose_name_plural = 'Designations (Cxapp)'
        unique_together = ('designation_name', 'company')

    def __str__(self):
        return self.designation_name

    # ── Wage Code helpers ────────────────────────────────────────────────────

    def fixed_wage_total(self):
        """Basic + DA — the statutorily protected wage floor components."""
        return self.basic_pay + self.da

    def component_totals(self):
        """
        Returns (allowance_total, deduction_total, excluded_total)
        from active dynamic components.
        """
        allowance_total = Decimal('0.00')
        deduction_total = Decimal('0.00')
        excluded_total = Decimal('0.00')

        for c in self.components.filter(is_active=True, is_deleted=False):
            amount = c.resolved_amount(self.basic_pay)
            if c.component_type == CxDesignationComponent.TYPE_ALLOWANCE:
                allowance_total += amount
                if c.is_wage_code_excluded:
                    excluded_total += amount
            else:
                deduction_total += amount

        return allowance_total, deduction_total, excluded_total

    def total_remuneration(self):
        allowance_total, _, _ = self.component_totals()
        return self.fixed_wage_total() + allowance_total

    def wage_code_compliance(self):
        """
        Checks the Section 2(y) 50% floor: excluded components
        (HRA, conveyance, etc.) must not exceed 50% of total
        remuneration. Returns a dict for display / API use.
        """
        total = self.total_remuneration()
        _, _, excluded_total = self.component_totals()

        if total <= 0:
            return {
                'compliant': True, 'total_remuneration': Decimal('0.00'),
                'excluded_total': Decimal('0.00'), 'excluded_percent': Decimal('0.00'),
                'excess_over_50pct': Decimal('0.00'),
            }

        excluded_percent = (excluded_total / total * 100).quantize(Decimal('0.01'))
        excess = max(Decimal('0.00'), excluded_total - (total / 2))

        return {
            'compliant': excluded_percent <= Decimal('50.00'),
            'total_remuneration': total,
            'excluded_total': excluded_total,
            'excluded_percent': excluded_percent,
            # Per 1st proviso: amount in excess of 50% is deemed added
            # back to wages for statutory (PF/ESI/gratuity) purposes.
            'excess_over_50pct': excess,
        }

    def clean(self):
        if self.is_dailywage and not self.dailywage_rate:
            raise ValidationError({'dailywage_rate': 'Required when designation is marked daily-wage.'})


class CxDesignationComponent(models.Model):
    """
    One dynamic allowance or deduction line attached to a designation.
    Flat amount or percentage-of-basic-pay; percentage resolves at
    read-time via resolved_amount().
    """
    TYPE_ALLOWANCE = 'allowance'
    TYPE_DEDUCTION = 'deduction'
    COMPONENT_TYPES = [
        (TYPE_ALLOWANCE, 'Allowance'),
        (TYPE_DEDUCTION, 'Deduction'),
    ]

    CALC_FLAT = 'flat'
    CALC_PERCENT_OF_BASIC = 'percent_basic'
    CALC_MODES = [
        (CALC_FLAT, 'Flat Amount'),
        (CALC_PERCENT_OF_BASIC, '% of Basic Pay'),
    ]

    designation             = models.ForeignKey(CxDesignation, on_delete=models.CASCADE,
                                                 related_name='components')
    component_name          = models.CharField(max_length=100)
    component_type          = models.CharField(max_length=10, choices=COMPONENT_TYPES)
    calculation_mode        = models.CharField(max_length=20, choices=CALC_MODES, default=CALC_FLAT)
    amount                  = models.DecimalField(max_digits=10, decimal_places=2,
                                                   help_text='Flat ₹ value, or % value (e.g. 40.00 for 40%) '
                                                              'depending on calculation_mode.')

    # Wage Code 2019 classification — only meaningful for allowances.
    # HRA, conveyance, special allowance, etc. are normally excluded
    # (True). Retaining allowance, if ever modelled as a component,
    # would be False (counts toward the wage floor).
    is_wage_code_excluded   = models.BooleanField(
        default=True,
        help_text='True if this allowance is an "excluded component" under Wage Code Sec 2(y) '
                   '(HRA, conveyance, etc). Leave True for nearly all allowances.'
    )
    is_taxable              = models.BooleanField(default=True)

    is_active               = models.BooleanField(default=True)
    is_deleted               = models.BooleanField(default=False)
    display_order            = models.PositiveSmallIntegerField(default=0)
    created_at               = models.DateTimeField(auto_now_add=True)
    updated_at               = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_designation_component'
        ordering = ['display_order', 'component_name']
        verbose_name = 'Designation Component'
        verbose_name_plural = 'Designation Components'
        unique_together = ('designation', 'component_name')

    def __str__(self):
        return f'{self.designation.designation_name} — {self.component_name}'

    def resolved_amount(self, basic_pay):
        if self.calculation_mode == self.CALC_PERCENT_OF_BASIC:
            return (basic_pay * self.amount / 100).quantize(Decimal('0.01'))
        return self.amount

    def clean(self):
        if self.component_type == self.TYPE_DEDUCTION and self.is_wage_code_excluded:
            raise ValidationError({
                'is_wage_code_excluded': 'Wage Code exclusion applies only to allowances.'
            })


# ── Form ─────────────────────────────────────────────────────────────────────

from django import forms as _forms


class CxDesignationForm(_forms.ModelForm):
    class Meta:
        model = CxDesignation
        fields = ['designation_name', 'is_dailywage', 'dailywage_rate', 'basic_pay', 'da']
        widgets = {
            'designation_name': _forms.TextInput(attrs={'class': 'form-control'}),
            'is_dailywage': _forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'dailywage_rate': _forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'basic_pay': _forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'da': _forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('is_dailywage') and not cleaned.get('dailywage_rate'):
            self.add_error('dailywage_rate', 'Required when marked daily-wage.')
        return cleaned


class CxDesignationComponentForm(_forms.ModelForm):
    class Meta:
        model = CxDesignationComponent
        fields = ['component_name', 'component_type', 'calculation_mode', 'amount',
                  'is_wage_code_excluded', 'is_taxable', 'display_order']
        widgets = {
            'component_name': _forms.TextInput(attrs={'class': 'form-control'}),
            'component_type': _forms.Select(attrs={'class': 'form-control'}),
            'calculation_mode': _forms.Select(attrs={'class': 'form-control'}),
            'amount': _forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_wage_code_excluded': _forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_taxable': _forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'display_order': _forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('component_type') == CxDesignationComponent.TYPE_DEDUCTION:
            cleaned['is_wage_code_excluded'] = False
        return cleaned


# ── Views ────────────────────────────────────────────────────────────────────
# Owner-only mostly; auth decorators imported lazily from Cxapp.views to
# avoid a circular import (Cxapp.views doesn't depend on this module).

from django.contrib import messages as _messages
from django.shortcuts import render as _render, redirect as _redirect, get_object_or_404 as _get_object_or_404


def cxapp_designation_list(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_designation_list)(request)


def _designation_list(request):
    designations = CxDesignation.objects.filter(
        company=request.cx_company, is_deleted=False
    ).order_by('designation_name')
    return _render(request, 'Cxapp/designation/designation_list.html', {'designations': designations})


def cxapp_designation_create(request):
    from Cxapp.views import owner_only
    return owner_only(_designation_create)(request)


def _designation_create(request):
    if request.method == 'POST':
        form = CxDesignationForm(request.POST)
        if form.is_valid():
            designation = form.save(commit=False)
            designation.company = request.cx_company
            designation.created_by = request.user.username
            designation.updated_by = request.user.username
            designation.save()
            _messages.success(request, f"Designation '{designation.designation_name}' created.")
            return _redirect('cxapp_designation_components', designation_id=designation.id)
    else:
        form = CxDesignationForm()

    return _render(request, 'Cxapp/designation/designation_form.html', {'form': form, 'is_new': True})


def cxapp_designation_edit(request, designation_id):
    from Cxapp.views import owner_only
    return owner_only(_designation_edit)(request, designation_id)


def _designation_edit(request, designation_id):
    designation = _get_object_or_404(CxDesignation, id=designation_id, company=request.cx_company)

    if request.method == 'POST':
        form = CxDesignationForm(request.POST, instance=designation)
        if form.is_valid():
            designation = form.save(commit=False)
            designation.updated_by = request.user.username
            designation.save()
            _messages.success(request, 'Designation updated.')
            return _redirect('cxapp_designation_components', designation_id=designation.id)
    else:
        form = CxDesignationForm(instance=designation)

    return _render(request, 'Cxapp/designation/designation_form.html', {
        'form': form, 'is_new': False, 'designation': designation,
    })


def cxapp_designation_delete(request, designation_id):
    from Cxapp.views import owner_only
    return owner_only(_designation_delete)(request, designation_id)


def _designation_delete(request, designation_id):
    designation = _get_object_or_404(CxDesignation, id=designation_id, company=request.cx_company)
    if request.method == 'POST':
        designation.is_deleted = True
        designation.is_active = False
        designation.save(update_fields=['is_deleted', 'is_active'])
        _messages.success(request, f"'{designation.designation_name}' deleted.")
        return _redirect('cxapp_designation_list')
    return _render(request, 'Cxapp/designation/designation_delete.html', {'designation': designation})


def cxapp_designation_components(request, designation_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_designation_components)(request, designation_id)


def _designation_components(request, designation_id):
    """Manage dynamic allowances/deductions + live Wage Code compliance check."""
    designation = _get_object_or_404(CxDesignation, id=designation_id, company=request.cx_company)
    is_owner = getattr(request, 'cx_sub_user', None) is None

    if request.method == 'POST' and is_owner:
        form = CxDesignationComponentForm(request.POST)
        if form.is_valid():
            component = form.save(commit=False)
            component.designation = designation
            component.save()
            _messages.success(request, f"Component '{component.component_name}' added.")
            return _redirect('cxapp_designation_components', designation_id=designation.id)
    else:
        form = CxDesignationComponentForm()

    components = designation.components.filter(is_deleted=False).order_by('display_order', 'component_name')
    for c in components:
        c.resolved = c.resolved_amount(designation.basic_pay)
    compliance = designation.wage_code_compliance()

    return _render(request, 'Cxapp/designation/designation_components.html', {
        'designation': designation,
        'components': components,
        'form': form,
        'compliance': compliance,
        'is_owner': is_owner,
    })


def cxapp_component_delete(request, component_id):
    from Cxapp.views import owner_only
    return owner_only(_component_delete)(request, component_id)


def _component_delete(request, component_id):
    component = _get_object_or_404(
        CxDesignationComponent, id=component_id, designation__company=request.cx_company
    )
    designation_id = component.designation_id
    if request.method == 'POST':
        component.is_deleted = True
        component.is_active = False
        component.save(update_fields=['is_deleted', 'is_active'])
        _messages.success(request, f"'{component.component_name}' removed.")
    return _redirect('cxapp_designation_components', designation_id=designation_id)
