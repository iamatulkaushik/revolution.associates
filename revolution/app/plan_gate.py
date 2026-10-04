"""
Plan gating — single source of truth for what each subscription tier unlocks.
Company.plan (Sapp.app.company.Company) drives every check here.
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

PLAN_RANK = {"copper": 0, "silver": 1, "gold": 2, "platinum": 3}

FEATURE_MIN_PLAN = {
    "overtime": "silver",
    "biometric": "silver",
    "shift_mgmt": "silver",
    "lwf": "silver",
    "loans": "silver",
    "ess_portal": "silver",
    "promotion": "gold",
    "gratuity": "gold",
    "factory_act": "gold",
    "min_wages": "gold",
    "shops_estab": "gold",
    "payment_of_wages": "gold",
    "bank_file": "gold",
    "bulk_email": "gold",
    "arrear": "gold",
    "contract_labour": "platinum",
    "bonus_act": "platinum",
    "multi_state_pt": "platinum",
    "tds": "platinum",
    "audit_trail": "platinum",
    "maker_checker": "platinum",
    "asset_expense": "platinum",
    "disbursement_api": "platinum",
    "public_profile": "platinum",
    "api_access": "platinum",
}


def has_feature(company, feature: str) -> bool:
    """Copper features (not in FEATURE_MIN_PLAN) are always allowed."""
    if company is None:
        return False
    min_plan = FEATURE_MIN_PLAN.get(feature, "copper")
    return PLAN_RANK[company.plan] >= PLAN_RANK[min_plan]


def require_feature(feature: str):
    """View decorator. Redirects to dashboard with an upgrade message
    instead of raising, so HR users don't hit a raw 403 page."""
    def deco(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            company = getattr(request, "selected_company", None)
            if not has_feature(company, feature):
                messages.warning(
                    request,
                    f"This feature needs an upgrade — your current plan "
                    f"({(company.plan if company else 'none')}) doesn't include it."
                )
                return redirect("aapp_dashboard")
            return view_func(request, *args, **kwargs)
        return wrapper
    return deco
