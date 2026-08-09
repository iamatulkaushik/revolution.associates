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

    if sub_user is not None:
        role_perms = sub_user.get_role_permissions()
    else:
        # Owner sees everything a role-based permission would gate.
        role_perms = {'employees': True, 'attendance': True, 'wages': True,
                      'recruitment': True, 'front_desk': True}

    return {
        'cx_company':        company,
        'cx_owner_profile':  owner_profile,
        'cx_sub_user':       sub_user,
        'cx_is_owner':       sub_user is None,
        'cx_plan':           plan,
        'cx_plan_days_remaining': plan.days_remaining() if plan else 0,
        'cx_plan_expired':   (plan is None or not plan.is_valid()),
        'cx_can_employees':  role_perms.get('employees', False),
        'cx_can_attendance': role_perms.get('attendance', False),
        'cx_can_wages':      role_perms.get('wages', False),
        'cx_can_recruitment': role_perms.get('recruitment', False),
        'cx_can_front_desk': role_perms.get('front_desk', False),
    }
