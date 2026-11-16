"""
statutory_rates.py
==================
Date-aware statutory constants shared by Aapp, Capp and Cxapp.

EPF wage ceiling (EPF / EPS / EDLI):
    up to 16 Sep 2026 : Rs 15,000
    from 17 Sep 2026  : Rs 25,000   (Notification S.O. 5109(E), 17-Sep-2026,
                                     Code on Social Security 2020, s.2(89))

September 2026 straddles the change. The notification gives no daily
ceiling, and the widely preferred reading is to apply Rs 25,000 for the
whole month. Choose with settings.PF_CEILING_SEPT_2026:
    'full'      -> 25000  (default)
    'old'       -> 15000
    'prorated'  -> 19667  (15000 for 1-16 Sep + 25000 for 17-30 Sep, blended)

ESIC's Rs 21,000 ceiling is unchanged and is NOT handled here.
"""
from decimal import Decimal

PF_CEILING_OLD = Decimal('15000')
PF_CEILING_NEW = Decimal('25000')
PF_CEILING_PRORATED_SEP_2026 = Decimal('19667')


def pf_wage_ceiling(month=None, year=None):
    """EPF/EPS/EDLI wage ceiling for the given salary month. No date -> latest."""
    if not month or not year:
        return PF_CEILING_NEW
    key = (int(year), int(month))
    if key < (2026, 9):
        return PF_CEILING_OLD
    if key == (2026, 9):
        from django.conf import settings
        mode = getattr(settings, 'PF_CEILING_SEPT_2026', 'full')
        return {
            'old': PF_CEILING_OLD,
            'prorated': PF_CEILING_PRORATED_SEP_2026,
        }.get(mode, PF_CEILING_NEW)
    return PF_CEILING_NEW


# ---------------------------------------------------------------------------
# Haryana Labour Welfare Fund (monthly)
#   employee = 0.2% of wages, capped; employer = 2 x employee (cap doubles).
#   Cap: Rs 31 (to Dec-2024) -> Rs 34 (2025) -> Rs 35 (from 1-Jan-2026,
#   notification HLWB/REV/2026/3436 of 8-May-2026).
# ---------------------------------------------------------------------------
from decimal import ROUND_HALF_UP

LWF_RATE = Decimal('0.002')


def haryana_lwf_cap(month=None, year=None):
    if not year or int(year) >= 2026:
        return Decimal('35')
    if int(year) == 2025:
        return Decimal('34')
    return Decimal('31')


def haryana_lwf(wages, month=None, year=None):
    """(employee, employer) LWF in whole rupees for the given wages."""
    wages = Decimal(wages or 0)
    if wages <= 0:
        return Decimal('0'), Decimal('0')
    cap = haryana_lwf_cap(month, year)
    emp_raw = min(wages * LWF_RATE, cap)
    one = Decimal('1')
    emp = emp_raw.quantize(one, rounding=ROUND_HALF_UP)
    empr = min(emp_raw * 2, cap * 2).quantize(one, rounding=ROUND_HALF_UP)
    return emp, empr