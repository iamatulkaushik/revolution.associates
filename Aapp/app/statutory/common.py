"""
Aapp/app/statutory/common.py
=============================
Shared helpers used by every statutory-act PDF report module
(wages_act.py, factory_act.py, shop_act.py, ...).

Keep this file to pure presentation/aggregation helpers only — no
act-specific business logic belongs here.
"""

import calendar
from decimal import Decimal


def month_name(month):
    return calendar.month_name[int(month)]


def sum_field(slips, field):
    """Sum a Decimal field across a list of salary_slip rows, treating
    None as zero."""
    return sum((getattr(s, field) or Decimal('0')) for s in slips)


def letterhead_kwargs(company):
    """Use company's configured letterhead mode if available, else default."""
    fn = getattr(company, 'pdf_letterhead_kwargs', None)
    return fn() if callable(fn) else {}
