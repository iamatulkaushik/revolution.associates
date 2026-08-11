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

Minimum Wages Act / Code on Wages 2019:
    Skill-band minimum wage reference table (`CxMinWageRate`) is
    maintained globally. Designations can be tagged with a `skill_level`
    to enforce that `basic_pay + da` (or `dailywage_rate` for daily-wage
    roles) does not fall below the notified statutory floor.

Design:
    - CxMinWageRate: Global skill-band minimum-wage reference table.
    - CxDesignation: Fixed columns for Basic and DA only. HRA is
      NOT a fixed column — it's a dynamic component like every
      other allowance/deduction. Includes optional `skill_level` link.
    - CxDesignationComponent: One row per allowance or deduction
      attached to a designation. Flat amount or percentage-of-basic.
      Includes a `is_wage_code_excluded` flag so the 50% floor check
      knows which components count against the exclusion cap.
"""

from datetime import date as _date
from decimal import Decimal

from django.db import models
from django.core.exceptions import ValidationError

from Sapp.app.company import Company


# ── Models ───────────────────────────────────────────────────────────────────

class CxMinWageRate(models.Model):
    """
    Statutory minimum-wage reference table (skill-band-wise).

    These rates are NOT per-company — they represent the State-notified
    floor under the Minimum Wages Act / Code on Wages 2019. They are
    surfaced in the Company-Owner portal as a compliance reference
    and used to validate that `basic_pay + da` on a CxDesignation
    tagged with a skill level does not fall below the floor.

    Daily rate is the prevailing notified rate; monthly rate is
    treated as the source of truth for the monthly regime
    (daily × 26 is the de-facto conversion used by most State
    notifications, with notified rounding on top).
    """
    SKILL_UNSKILLED       = 'unskilled'
    SKILL_SEMI_SKILLED    = 'semi_skilled'
    SKILL_SKILLED         = 'skilled'
    SKILL_HIGHLY_SKILLED  = 'highly_skilled'
    SKILL_LEVELS = [
        (SKILL_UNSKILLED,      'Unskilled'),
        (SKILL_SEMI_SKILLED,   'Semi-Skilled'),
        (SKILL_SKILLED,        'Skilled'),
        (SKILL_HIGHLY_SKILLED, 'Highly-Skilled'),
    ]

    skill_level      = models.CharField(max_length=20, choices=SKILL_LEVELS, unique=True)
    monthly_rate     = models.DecimalField(max_digits=10, decimal_places=2)
    daily_rate       = models.DecimalField(max_digits=10, decimal_places=2)
    effective_from   = models.DateField(default=_date.today)
    is_active        = models.BooleanField(default=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label            = 'Cxapp'
        db_table             = 'cx_min_wage_rate'
        ordering             = ['skill_level']
        verbose_name         = 'Minimum Wage Rate'
        verbose_name_plural  = 'Minimum Wage Rates'

    def __str__(self):
        return f'{self.get_skill_level_display()} — ₹{self.monthly_rate}/mo, ₹{self.daily_rate}/day'

    # ── Helpers ────────────────────────────────────────────────────────────
    @classmethod
    def get_rate(cls, skill_level: str) -> 'CxMinWageRate | None':
        """Return the currently-active row for a given skill band."""
        return cls.objects.filter(skill_level=skill_level, is_active=True).first()

    def round_rates(self):
        """Two-place quantize — useful after bulk loads."""
        two = Decimal('0.01')
        self.monthly_rate = Decimal(self.monthly_rate).quantize(two)
        self.daily_rate  = Decimal(self.daily_rate).quantize(two)


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

    # ── Minimum Wage Skill Band Mapping ─────────────────────────────────────
    skill_level = models.CharField(
        max_length=20,
        choices=CxMinWageRate.SKILL_LEVELS,
        blank=True, default='',
        help_text='Optional. When set, basic + da for this designation '
                  'cannot fall below the notified minimum for the band.'
    )

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

    # ── Minimum-wage floor ────────────────────────────────────────────────
    def minimum_wage_check(self):
        """
        Returns a dict describing whether the designation meets the
        notified minimum for its skill band (if any).
        Returns compliant=True when no skill level is tagged — minimum
        wage compliance then falls back to statutory configuration
        outside this portal (e.g., by employer locale).
        """
        if not self.skill_level:
            return {
                'compliant': True,
                'skill_level': '',
                'required_monthly': Decimal('0.00'),
                'required_daily':  Decimal('0.00'),
                'actual_monthly':  self.fixed_wage_total(),
                'actual_daily':     self.dailywage_rate if self.is_dailywage else Decimal('0.00'),
                'shortfall':        Decimal('0.00'),
            }

        rate = CxMinWageRate.get_rate(self.skill_level)
        actual_monthly = self.fixed_wage_total()
        actual_daily   = self.dailywage_rate if self.is_dailywage else Decimal('0.00')

        if rate is None:
            return {
                'compliant': False,
                'skill_level': self.skill_level,
                'required_monthly': Decimal('0.00'),
                'required_daily':  Decimal('0.00'),
                'actual_monthly':  actual_monthly,
                'actual_daily':    actual_daily,
                'shortfall':       Decimal('0.00'),
                'note': 'Minimum-wage rate for this skill band is not configured.'
            }

        if self.is_dailywage:
            shortfall = max(Decimal('0.00'), rate.daily_rate - actual_daily)
            compliant = actual_daily >= rate.daily_rate
        else:
            shortfall = max(Decimal('0.00'), rate.monthly_rate - actual_monthly)
            compliant = actual_monthly >= rate.monthly_rate

        return {
            'compliant': compliant,
            'skill_level':  self.skill_level,
            'required_monthly': rate.monthly_rate,
            'required_daily':   rate.daily_rate,
            'actual_monthly':   actual_monthly,
            'actual_daily':     actual_daily,
            'shortfall':        shortfall,
        }

    def clean(self):
        super().clean()
        if self.is_dailywage and not self.dailywage_rate:
            raise ValidationError({'dailywage_rate': 'Required when designation is marked daily-wage.'})

        if self.skill_level:
            chk = self.minimum_wage_check()
            if not chk['compliant'] and chk.get('shortfall', Decimal('0')) > 0:
                unit = 'day' if self.is_dailywage else 'month'
                req_rate = chk['required_daily'] if self.is_dailywage else chk['required_monthly']
                field_name = 'dailywage_rate' if self.is_dailywage else 'basic_pay'
                raise ValidationError({
                    field_name: f"{self.get_skill_level_display()} minimum is "
                                f"₹{req_rate}/{unit}; "
                                f"current fixed wage falls short by ₹{chk['shortfall']}."
                })


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


# ── Forms ────────────────────────────────────────────────────────────────────

from django import forms as _forms


class CxDesignationForm(_forms.ModelForm):
    class Meta:
        model = CxDesignation
        fields = ['designation_name', 'skill_level', 'is_dailywage', 'dailywage_rate', 'basic_pay', 'da']
        widgets = {
            'designation_name': _forms.TextInput(attrs={'class': 'form-control'}),
            'skill_level': _forms.Select(attrs={'class': 'form-control'}),
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


# ── Base database initialization ────────────────────────────────────────────
# Canonical notified rates (per the portal's compliance baseline).
# Daily rates are stored exactly as notified; monthly rates likewise.
# Replace these arrays when the State revises the notification — the
# table will then have multiple rows per skill band keyed by
# effective_from; this initializer only inserts rows when the band
# has zero existing rows, so re-running after a notification update
# won't overwrite anything.

DEFAULT_MIN_WAGE_RATES = [
    # (skill_level,                      monthly,             daily)
    (CxMinWageRate.SKILL_UNSKILLED,      Decimal('15220.71'), Decimal('585.41')),
    (CxMinWageRate.SKILL_SEMI_SKILLED,   Decimal('16780.74'), Decimal('645.41')),
    (CxMinWageRate.SKILL_SKILLED,        Decimal('18500.81'), Decimal('711.56')),
    (CxMinWageRate.SKILL_HIGHLY_SKILLED, Decimal('19425.85'), Decimal('747.14')),
]


def initialize_minimum_wages(verbose: bool = False) -> dict:
    """
    Seed cx_min_wage_rate with the four notified skill bands.

    Idempotent: a band is only inserted when no active row exists for it.
    Safe to call from a data migration, a management command, or
    AppConfig.ready() (with the migration-state guard).

    Returns a summary dict:
        {'created': [...], 'skipped': [...], 'updated': [...]}
    """
    created, skipped, updated = [], [], []
    for skill_level, monthly, daily in DEFAULT_MIN_WAGE_RATES:
        obj, was_created = CxMinWageRate.objects.get_or_create(
            skill_level=skill_level,
            defaults={
                'monthly_rate':   monthly,
                'daily_rate':     daily,
                'effective_from': _date.today(),
                'is_active':      True,
            },
        )
        if was_created:
            created.append(skill_level)
            if verbose:
                print(f'[CxMinWageRate] created {skill_level}: ₹{monthly}/mo, ₹{daily}/day')
        else:
            # If rates differ from the canonical seed, refresh in place —
            # only touches the running row, preserving the band's history
            # via the effective_from field if you later switch to versioned rows.
            changed = False
            if obj.monthly_rate != monthly:
                obj.monthly_rate = monthly
                changed = True
            if obj.daily_rate != daily:
                obj.daily_rate = daily
                changed = True
            if changed:
                obj.save(update_fields=['monthly_rate', 'daily_rate', 'updated_at'])
                updated.append(skill_level)
            else:
                skipped.append(skill_level)
    return {'created': created, 'skipped': skipped, 'updated': updated}
