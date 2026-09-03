import logging
from functools import wraps

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

logger = logging.getLogger(__name__)


def owner_required(view_func):
    """
    Restricts a view to authenticated Company Owner users
    (Capp.models.CompanyOwnerProfile) who are active and not suspended.
    Requires CompanyOwnerMiddleware to have run first.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('capp_login')
        profile = getattr(request, 'owner_profile', None)
        if profile is None:
            logger.warning(
                "Non-owner user '%s' attempted Capp access: %s",
                request.user.username, request.path,
            )
            return HttpResponseForbidden("You do not have access to the Company Owner portal.")
        if not profile.can_access_system():
            messages.error(request, 'Your account is suspended or disabled. Contact your associate.')
            return redirect('capp_login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
