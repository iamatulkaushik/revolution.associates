"""revolution/error_views.py — custom error pages (400/403/403 CSRF/404/500)."""
from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader


def custom_400(request, exception=None):
    return render(request, '400.html', status=400)


def custom_403(request, exception=None):
    return render(request, '403.html', status=403)


def custom_403_csrf(request, reason=''):
    # Signature required by CSRF_FAILURE_VIEW.
    return render(request, '403_csrf.html', {'reason': reason}, status=403)


def custom_404(request, exception=None):
    return render(request, '404.html', status=404)


def custom_500(request):
    # No request context: context processors may be what crashed.
    try:
        body = loader.render_to_string('500.html')
    except Exception:
        body = '<h1>500 - Server error</h1>'
    return HttpResponse(body, status=500)
