"""
revolution/app/plan_limits.py — employee limits per subscription plan.

FROZEN CONTRACT (signatures must not change):
    employee_limit(company)            -> int | None   (None = unlimited)
    active_employee_count(company)     -> int
    remaining(company)                 -> int | None
    check_can_add(company, n=1)        -> None, or raises PlanLimitExceeded

Rule (decided): only ADDING is blocked. Existing employees stay untouched.
Reactivating a relieved employee counts as adding.

Phase 0 reads PLAN_EMPLOYEE_LIMITS below. Track AI-1 replaces the source with a
database-backed PlanLimit table that Sapp superadmin edits. Signatures stay.

Only copper = 150 is a business decision. The other numbers are PLACEHOLDERS
until the owner confirms them (docs/capp_upgrade/00_MASTER_PLAN.md, D1).
"""
PLAN_EMPLOYEE_LIMITS = {
    'copper': 150,
    'silver': 500,       # PLACEHOLDER - confirm (D1)
    'gold': 2000,        # PLACEHOLDER - confirm (D1)
    'platinum': None,    # PLACEHOLDER - unlimited, confirm (D1)
}


class PlanLimitExceeded(Exception):
    def __init__(self, message, limit, current):
        super().__init__(message)
        self.limit, self.current = limit, current


def employee_limit(company):
    return PLAN_EMPLOYEE_LIMITS.get(company.plan, PLAN_EMPLOYEE_LIMITS['copper'])


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
