"""
Cxapp/middleware.py
=====================
Two responsibilities, both must run on every Cxapp request:

1. CxCompanyMiddleware  — resolves request.cx_owner_profile / cx_sub_user
   / cx_company, same as before.
2. CxLicenseMiddleware  — enforces the 7-day trial. Once the owner's
   CxPlan has expired, every view except company profile and plan
   purchase redirects to plan purchase. Runs AFTER CxCompanyMiddleware
   in MIDDLEWARE (settings.py), since it needs request.cx_owner_profile
   to already be resolved.

Both must be listed in settings.py MIDDLEWARE in this order:
    'Cxapp.middleware.CxCompanyMiddleware',
    'Cxapp.middleware.CxLicenseMiddleware',
"""

from django.shortcuts import redirect
from django.urls import resolve, Resolver404


# URL names reachable regardless of plan status. Login/signup/logout are
# included because an unauthenticated or newly-registering owner has no
# plan yet to check. Company profile stays open per the "always visible"
# requirement even after trial expiry.
ALWAYS_ALLOWED_NAMES = {
    'cxapp_login',
    'cxapp_signup',
    'cxapp_logout',
    'cxapp_company_profile',
    'cxapp_plan_purchase',
}


class CxCompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.cx_owner_profile = None
        request.cx_sub_user = None
        request.cx_company = None

        if request.user.is_authenticated:
            from Cxapp.models import CxOwnerProfile
            from Cxapp.app.sub_user import CxSubUser

            owner_profile = getattr(request.user, 'cx_owner_profile', None)
            if owner_profile is not None:
                request.cx_owner_profile = owner_profile
                request.cx_company = owner_profile.company
            else:
                sub_user = getattr(request.user, 'cx_sub_user', None)
                if sub_user is not None:
                    request.cx_sub_user = sub_user
                    request.cx_owner_profile = sub_user.owner
                    request.cx_company = sub_user.owner.company

        return self.get_response(request)


class CxLicenseMiddleware:
    """
    Blocks every Cxapp view once the owner's trial/plan has expired,
    except the always-allowed set above. Applies to sub-users too —
    a sub-user under an expired owner is equally blocked, since their
    access derives entirely from the owner's plan.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        owner_profile = getattr(request, 'cx_owner_profile', None)

        if owner_profile is not None:
            try:
                url_name = resolve(request.path_info).url_name
            except Resolver404:
                url_name = None

            if url_name not in ALWAYS_ALLOWED_NAMES:
                plan = getattr(owner_profile, 'plan', None)
                if plan is None or not plan.is_valid():
                    return redirect('cxapp_plan_purchase')

        return self.get_response(request)
