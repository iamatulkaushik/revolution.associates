"""Guard for DIRECT-only pages: owner login, company mode, then permissions.

Kept in the direct track because Capp/access.py (AI-1) exposes no mode guard yet.
It asks `get_mode`, so AI-1's real mode field is picked up with no change here.
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from Capp.access import capp_perm, get_mode
from Capp.views import owner_required

DIRECT = 'DIRECT'


def direct_perm(*perms):
    def deco(view_func):
        allowed = capp_perm(*perms)(view_func)

        @wraps(view_func)
        @owner_required
        def _wrapped(request, *args, **kwargs):
            if get_mode(request.owned_company) != DIRECT:
                messages.error(request, 'This page is only for companies that run their own payroll.')
                return redirect('capp_dashboard')
            return allowed(request, *args, **kwargs)
        return _wrapped
    return deco
