from .registry import REGISTRY, CATEGORIES


def owner_context(request):
    if not request.user.is_authenticated:
        return {}
    nav = [
        {'category': cat, 'modules': [e for e in REGISTRY if e.category == cat]}
        for cat in CATEGORIES
    ]
    return {
        'nav_categories': nav,
        'owned_company': getattr(request, 'owned_company', None),
        'owner_profile': getattr(request, 'owner_profile', None),
    }
