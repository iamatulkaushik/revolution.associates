"""
Cxapp/context_processors.py
============================
Injects `cx_company`, `cx_owner_profile`, `cx_sub_user`, `cx_is_owner`
into every template rendered within the Cxapp (self-signup owner) portal.

Add to TEMPLATES context_processors in settings.py:
    'Cxapp.context_processors.cx_context',
"""


def cx_context(request):
    company = getattr(request, 'cx_company', None)
    owner_profile = getattr(request, 'cx_owner_profile', None)
    sub_user = getattr(request, 'cx_sub_user', None)

    if not company:
        return {}

    plan = getattr(owner_profile, 'plan', None)

    return {
        'cx_company':        company,
        'cx_owner_profile':  owner_profile,
        'cx_sub_user':       sub_user,
        'cx_is_owner':       sub_user is None,
        'cx_plan':           plan,
        'cx_plan_days_remaining': plan.days_remaining() if plan else 0,
        'cx_plan_expired':   (plan is None or not plan.is_valid()),
    }
