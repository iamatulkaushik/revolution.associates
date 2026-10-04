from django import template

from revolution.app.plan_gate import has_feature as _has_feature

register = template.Library()


@register.simple_tag(takes_context=True)
def can_use(context, feature):
    request = context.get("request")
    company = getattr(request, "selected_company", None) if request else None
    return _has_feature(company, feature)
