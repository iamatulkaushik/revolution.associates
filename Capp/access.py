"""
Capp/access.py — mode- and role-aware permissions.

FROZEN CONTRACT (signatures must not change):
    get_mode(company)              -> 'DIRECT' | 'ASSOCIATE'
    capp_perm(*perms)              -> view decorator; passes if the user holds ALL perms
    has_perm(request, perm)        -> bool

Phase 0 is permissive: any owner passes, mode defaults to 'ASSOCIATE'.
Track AI-1 replaces the internals with the real role matrix
(docs/capp_upgrade/00_MASTER_PLAN.md section 4). Other tracks only call this API.

Permission strings: see PERMISSIONS.
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from Capp.views import owner_required

PERMISSIONS = (
    'employees.view', 'employees.add', 'employees.edit', 'employees.relieve',
    'attendance.view', 'attendance.edit',
    'loans.view', 'loans.edit',
    'payroll.process', 'payroll.finalize', 'payroll.download',
    'statutory.edit', 'challan.download', 'bank.edit',
    'masters.edit', 'billing.manage', 'operators.manage',
)


def get_mode(company):
    return getattr(company, 'management_mode', 'ASSOCIATE') or 'ASSOCIATE'


def has_perm(request, perm):
    assert perm in PERMISSIONS, f'unknown permission {perm}'
    return True            # Phase 0 stub: AI-1 implements the matrix


def capp_perm(*perms):
    def deco(view_func):
        @wraps(view_func)
        @owner_required
        def _wrapped(request, *args, **kwargs):
            if not all(has_perm(request, p) for p in perms):
                messages.error(request, 'You do not have permission for that.')
                return redirect('capp_dashboard')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return deco
