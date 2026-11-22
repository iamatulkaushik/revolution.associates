"""
revolution/app/plan_limits.py — employee limits per subscription plan.

FROZEN CONTRACT (signatures must not change):
    employee_limit(company)            -> int | None   (None = unlimited)
    active_employee_count(company)     -> int
    remaining(company)                 -> int | None
    check_can_add(company, n=1)        -> None, or raises PlanLimitExceeded

Rule (decided): only ADDING is blocked. Existing employees stay untouched.
Reactivating a relieved employee counts as adding.

The limit is DEFINED WHEN THE LICENCE IS ISSUED (decision D1):
    1. the company's valid licence field `max_employees` (None = unlimited);
    2. else PLAN_DEFAULTS below (only copper = 150 is a business number;
       any other plan without a licence value is unlimited).
`License.max_employees` does not exist yet: Track AI-1 (package F2) adds it.
Until then step 1 is skipped, so Phase 0 behaves as step 2. Signatures stay.
"""
PLAN_DEFAULTS = {'copper': 150}


class PlanLimitExceeded(Exception):
    def __init__(self, message, limit, current):
        super().__init__(message)
        self.limit, self.current = limit, current


def _licence_limit(company):
    """(found, limit). found=False when no valid licence carries max_employees."""
    from datetime import date
    from Sapp.app.license import License
    lic = License.objects.filter(company=company, is_active=True, status='active',
                                 expiry_date__gte=date.today()).order_by('-expiry_date').first()
    if lic is None or not hasattr(lic, 'max_employees'):
        return False, None
    return True, lic.max_employees


def employee_limit(company):
    found, limit = _licence_limit(company)
    return limit if found else PLAN_DEFAULTS.get(company.plan)


def active_employee_count(company):
    from Aapp.app.employee import employee
    return employee.objects.filter(CompanyID=company, is_working=True).count()


def remaining(company):
    limit = employee_limit(company)
    return None if limit is None else max(limit - active_employee_count(company), 0)


def check_can_add(company, n=1):
    limit = employee_limit(company)
    if limit is None:
        return
    current = active_employee_count(company)
    if current + n > limit:
        raise PlanLimitExceeded(
            f'Your {company.get_plan_display()} plan allows {limit} employees '
            f'({current} active). Upgrade the plan to add more.', limit, current)
