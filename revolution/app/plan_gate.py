# --- 1. Company model: one field ---
# PLAN_CHOICES = [("copper","Copper"),("silver","Silver"),("gold","Gold"),("platinum","Platinum")]
# plan = models.CharField(max_length=10, choices=PLAN_CHOICES, default="copper")

# --- 2. Feature map: single source of truth ---
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
    min_plan = FEATURE_MIN_PLAN.get(feature, "copper")
    return PLAN_RANK[company.plan] >= PLAN_RANK[min_plan]


# --- 3. View decorator ---
from functools import wraps
from django.core.exceptions import PermissionDenied

def require_feature(feature: str):
    def deco(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            company = request.user.company  # adjust to your actual accessor
            if not has_feature(company, feature):
                raise PermissionDenied(f"Upgrade required for {feature}")
            return view_func(request, *args, **kwargs)
        return wrapper
    return deco


# --- 4. Usage ---
# @require_feature("bank_file")
# def generate_bank_file(request): ...


# --- 5. Template gating: templatetags/plan_tags.py ---
# from django import template
# from ..plan_gate import has_feature as _has_feature
# register = template.Library()
#
# @register.simple_tag(takes_context=True)
# def can_use(context, feature):
#     return _has_feature(context['request'].user.company, feature)
#
# usage: {% load plan_tags %}
# {% can_use "bank_file" as can_bank %}{% if can_bank %}...{% endif %}


# --- 6. Nav menu gating ---
# base.html: wrap each nav link the same way, no per-link special-casing needed.
