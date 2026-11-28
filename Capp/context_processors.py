"""
Capp/context_processors.py
==========================
`owner_context` adds to every Capp template:
  owned_company, owner_profile, access (owner flags),
  capp_mode, capp_mode_label, capp_role, plan_usage (lazy),
  capp_nav  — menu built from Capp.foundation.nav + Capp.entry.nav + Capp.direct.nav,
              filtered by permission and mode.
"""
from django.urls import NoReverseMatch, reverse
from django.utils.functional import SimpleLazyObject

from Capp.access import has_perm
from revolution.app.plan_gate import has_feature

MODE_LABEL = {'DIRECT': 'Direct company', 'ASSOCIATE': 'Under associate'}


def _sources():
    from Capp.direct.nav import NAV as DIRECT
    from Capp.entry.nav import NAV as ENTRY
    from Capp.foundation.nav import NAV as BASE
    return list(BASE) + list(ENTRY) + list(DIRECT)


def _url(entry):
    try:
        return reverse(entry['url_name'], kwargs=entry.get('kwargs'))
    except NoReverseMatch:
        return None                                 # a track's URL not merged yet: hide, never crash


def _visible(entry, request):
    if request.capp_mode not in entry.get('modes', ('DIRECT', 'ASSOCIATE')):
        return False
    feature = entry.get('feature')            # plan gate (revolution.app.plan_gate.FEATURE_MIN_PLAN)
    if feature and not has_feature(request.owned_company, feature):
        return False
    perm = entry.get('perm')
    return perm is None or has_perm(request, perm)


def build_nav(request):
    groups = []
    for g in _sources():
        if not _visible(g, request):
            continue
        if 'items' in g:
            items = [{'label': i['label'], 'url': _url(i)} for i in g['items']
                     if _visible(i, request) and _url(i)]
            if items:
                groups.append({'id': g['id'], 'label': g['label'], 'css': g.get('css', ''),
                               'items': items})
        elif _url(g):
            groups.append({'id': g['id'], 'label': g['label'], 'css': g.get('css', ''),
                           'url': _url(g)})
    return groups


def _plan_usage(company):
    from revolution.app.plan_limits import active_employee_count, employee_limit
    limit = employee_limit(company)
    current = active_employee_count(company)
    return {'current': current, 'limit': limit,
            'text': f"{current} / {limit if limit is not None else 'unlimited'}",
            'full': limit is not None and current >= limit}


def owner_context(request):
    profile = getattr(request, 'owner_profile', None)
    company = getattr(request, 'owned_company', None)
    if not profile or not company:
        return {}
    mode = getattr(request, 'capp_mode', None)
    return {
        'owned_company': company,
        'owner_profile': profile,
        'access': profile.get_access_flags(),
        'capp_mode': mode,
        'capp_mode_label': MODE_LABEL.get(mode, ''),
        'capp_role': getattr(request, 'capp_role', None),
        'plan_usage': SimpleLazyObject(lambda: _plan_usage(company)),
        'capp_nav': build_nav(request),
    }
