"""
Sapp/middleware.py
=====================
Thread-local request context so model-level signal receivers (which
have no access to the HTTP request) can still record who made a change
and from what IP — used by Sapp/app/audit_trail.py.

Per pt_upgrades.md: "anychanges in selected/mentioned tables logtable
entry for proper use/user/cause" — signals fire inside Django's model
save/delete machinery, deep below the view layer, so this is the
standard way to smuggle request-scoped data down to that level without
threading a `request` parameter through every model method.
"""

import threading

_thread_locals = threading.local()


class AuditContextMiddleware:
    """Add to MIDDLEWARE in settings.py, anywhere after AuthenticationMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = getattr(request, 'user', None)
        _thread_locals.ip_address = self._get_client_ip(request)
        try:
            response = self.get_response(request)
        finally:
            # Always clear — avoids leaking context into unrelated
            # background/management-command code running in the same
            # worker thread after the request completes.
            _thread_locals.user = None
            _thread_locals.ip_address = None
        return response

    @staticmethod
    def _get_client_ip(request):
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


def get_current_user():
    user = getattr(_thread_locals, 'user', None)
    if user and getattr(user, 'is_authenticated', False):
        return user
    return None


def get_current_ip():
    return getattr(_thread_locals, 'ip_address', '') or ''
