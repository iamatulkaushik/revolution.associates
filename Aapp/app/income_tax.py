"""
Aapp/app/income_tax.py
========================
Income Tax (TDS) engine — New Regime (default, Section 115BAC) and Old
Regime (with Chapter VI-A deductions), FY-wise slabs.

Fail-closed like every other statutory module here: no PAN on the
employee record -> no TDS calculated, regardless of company TAN status
or income level (per pt_upgrades.md: "if no PAN no deduction").

Company TAN gate (gates['income_tax']) is checked separately in
salary_processing.py before this module is ever called — this module
assumes the company-level gate already passed.
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Select, NumberInput, CheckboxInput

from Sapp.app.company import Company


REGIME_CHOICES = [('new', 'New Regime (115BAC)'), ('old', 'Old Regime')]

# FY 2025-26 New Regime slabs (annual, post standard deduction)
NEW_REGIME_SLABS_2025_26 = [
    (Decimal('400000'), Decimal('0.00')),
    (Decimal('800000'), Decimal('0.05')),
    (Decimal('1200000'), Decimal('0.10')),
    (Decimal('1600000'), Decimal('0.15')),
    (Decimal('2000000'), Decimal('0.20')),
    (Decimal('2400000'), Decimal('0.25')),
    (None, Decimal('0.30')),
]
NEW_REGIME_STANDARD_DEDUCTION = Decimal('75000')
NEW_REGIME_REBATE_87A_LIMIT = Decimal('1200000')     # taxable income ceiling for full rebate
NEW_REGIME_REBATE_87A_MAX = Decimal('60000')

# FY 2025-26 Old Regime slabs (annual, post standard deduction + Ch VI-A)
OLD_REGIME_SLABS_2025_26 = [
    (Decimal('250000'), Decimal('0.00')),
    (Decimal('500000'), Decimal('0.05')),
    (Decimal('1000000'), Decimal('0.20')),
    (None, Decimal('0.30')),
]
OLD_REGIME_STANDARD_DEDUCTION = Decimal('50000')
OLD_REGIME_REBATE_87A_LIMIT = Decimal('500000')
OLD_REGIME_REBATE_87A_MAX = Decimal('12500')

CESS_RATE = Decimal('0.04')  # Health & Education Cess, applies after rebate on both regimes

# Old-regime Chapter VI-A caps
SECTION_80C_CAP = Decimal('150000')
SECTION_80D_CAP_SELF = Decimal('25000')
SECTION_80D_CAP_SELF_SENIOR = Decimal('50000')
SECTION_80CCD_1B_CAP = Decimal('50000')   # NPS additional
HRA_METRO_PERCENT = Decimal('0.50')
HRA_NONMETRO_PERCENT = Decimal('0.40')


class EmployeeTaxProfile(models.Model):
    """
    One row per employee per financial year — regime choice and
    declared investments for that year. Old-regime fields are ignored
    entirely when regime='new'.
    """
    profile_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey('Aapp.employee', on_delete=models.CASCADE, related_name='tax_profiles')
    financial_year = models.CharField(max_length=9, help_text="e.g. 2025-26")
    regime = models.CharField(max_length=3, choices=REGIME_CHOICES, default='new')

    # Old-regime declarations (Chapter VI-A) — ignored under New Regime
    section_80c = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       help_text="PF, ELSS, LIC, PPF, tuition fees etc. (max 1,50,000)")
    section_80d = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       help_text="Medical insurance premium")
    section_80ccd_1b = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                            help_text="Additional NPS contribution (max 50,000)")
    home_loan_interest_24b = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                                  help_text="Section 24(b), self-occupied cap 2,00,000")
    hra_claimed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_metro = models.BooleanField(default=False, help_text="For HRA exemption calc (50% vs 40% of basic)")
    other_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                            help_text="80E, 80G, 80TTA etc. combined")

    declared_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_employee_tax_profile'
        unique_together = ('employee', 'financial_year')
        verbose_name = "Employee Tax Profile"

    def __str__(self):
        return f"{self.employee.name} - FY{self.financial_year} ({self.get_regime_display()})"


class EmployeeTaxProfileForm(ModelForm):
    class Meta:
        model = EmployeeTaxProfile
        fields = ['financial_year', 'regime', 'section_80c', 'section_80d',
                  'section_80ccd_1b', 'home_loan_interest_24b', 'hra_claimed',
                  'is_metro', 'other_deductions']
        widgets = {
            'financial_year': NumberInput(attrs={'class': 'form-control', 'placeholder': '2025-26'}),
            'regime': Select(attrs={'class': 'form-control'}),
            'section_80c': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'section_80d': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'section_80ccd_1b': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'home_loan_interest_24b': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'hra_claimed': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_metro': CheckboxInput(attrs={'class': 'form-check-input'}),
            'other_deductions': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


def _round(amount):
    return Decimal(amount).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def _apply_slabs(taxable_income, slabs):
    """Slab-wise progressive tax on a Decimal taxable_income using
    [(upper_limit_or_None, rate), ...] sorted ascending."""
    if taxable_income <= 0:
        return Decimal('0')

    tax = Decimal('0')
    lower = Decimal('0')
    for upper, rate in slabs:
        if upper is None:
            slab_amount = taxable_income - lower
        else:
            slab_amount = min(taxable_income, upper) - lower
        if slab_amount > 0:
            tax += slab_amount * rate
        if upper is not None and taxable_income <= upper:
            break
        lower = upper if upper is not None else lower
    return tax


def calculate_annual_tax(gross_annual_income, tax_profile, basic_annual=None):
    """
    Computes annual income tax payable given gross annual income and an
    EmployeeTaxProfile (or None -> defaults to New Regime, zero declarations).

    Returns dict: {taxable_income, tax_before_cess, rebate, cess, total_tax, regime}
    """
    gross_annual_income = Decimal(str(gross_annual_income))
    regime = tax_profile.regime if tax_profile else 'new'

    if regime == 'old':
        std_deduction = OLD_REGIME_STANDARD_DEDUCTION
        deductions = std_deduction
        if tax_profile:
            deductions += min(Decimal(str(tax_profile.section_80c)), SECTION_80C_CAP)
            deductions += min(Decimal(str(tax_profile.section_80d)), SECTION_80D_CAP_SELF_SENIOR)
            deductions += min(Decimal(str(tax_profile.section_80ccd_1b)), SECTION_80CCD_1B_CAP)
            deductions += min(Decimal(str(tax_profile.home_loan_interest_24b)), Decimal('200000'))
            deductions += Decimal(str(tax_profile.other_deductions))

            if basic_annual and tax_profile.hra_claimed:
                pct = HRA_METRO_PERCENT if tax_profile.is_metro else HRA_NONMETRO_PERCENT
                hra_exempt_cap = Decimal(str(basic_annual)) * pct
                deductions += min(Decimal(str(tax_profile.hra_claimed)), hra_exempt_cap)

        taxable_income = max(Decimal('0'), gross_annual_income - deductions)
        tax = _apply_slabs(taxable_income, OLD_REGIME_SLABS_2025_26)
        rebate = tax if taxable_income <= OLD_REGIME_REBATE_87A_LIMIT else Decimal('0')
        rebate = min(rebate, OLD_REGIME_REBATE_87A_MAX)
    else:
        regime = 'new'
        taxable_income = max(Decimal('0'), gross_annual_income - NEW_REGIME_STANDARD_DEDUCTION)
        tax = _apply_slabs(taxable_income, NEW_REGIME_SLABS_2025_26)
        rebate = tax if taxable_income <= NEW_REGIME_REBATE_87A_LIMIT else Decimal('0')
        rebate = min(rebate, NEW_REGIME_REBATE_87A_MAX)

    tax_after_rebate = max(Decimal('0'), tax - rebate)
    cess = tax_after_rebate * CESS_RATE
    total_tax = _round(tax_after_rebate + cess)

    return {
        'regime': regime,
        'taxable_income': _round(taxable_income),
        'tax_before_cess': _round(tax),
        'rebate': _round(rebate),
        'cess': _round(cess),
        'total_tax': total_tax,
    }


def calculate_monthly_tds(employee_obj, projected_annual_gross, tax_profile,
                           months_remaining_in_fy, basic_annual=None):
    """
    Monthly TDS = remaining annual tax liability spread evenly over the
    months left in the FY. Returns Decimal('0') if employee has no PAN
    (fail-closed) regardless of income or regime.

    `months_remaining_in_fy` should include the current month (1-12).
    """
    if not getattr(employee_obj, 'pan_number', None):
        return Decimal('0')

    result = calculate_annual_tax(projected_annual_gross, tax_profile, basic_annual)
    if months_remaining_in_fy <= 0:
        return Decimal('0')

    monthly = result['total_tax'] / Decimal(months_remaining_in_fy)
    return _round(monthly)


def current_financial_year(on_date=None):
    """India FY runs Apr-Mar. Returns e.g. '2025-26'."""
    d = on_date or date.today()
    if d.month >= 4:
        return f"{d.year}-{str(d.year + 1)[-2:]}"
    return f"{d.year - 1}-{str(d.year)[-2:]}"
