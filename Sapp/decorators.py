import logging
from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from Sapp.app.license import License
from Sapp.app.user import associateuser

logger = logging.getLogger(__name__)


def superadmin_required(view_func):
    """
    Restricts a view to superusers (Django is_superuser flag) only.
    Any logged-in non-superuser is shown a 403. Unauthenticated users
    are redirected to the login page.

    Apply to ALL Sapp views so that Associates and SubUsers cannot access
    the admin panel even if they know the URL.

    Usage:
        @superadmin_required
        def my_view(request): ...
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_superuser:
            logger.warning(
                "Unauthorised admin panel access attempt by user '%s' (id=%s) for %s",
                request.user.username, request.user.pk, request.path,
            )
            return HttpResponseForbidden(
                "You do not have permission to access this page. "
                "This incident has been logged."
            )
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def license_required(view_func):
    """
    Ensures the logged-in associate has at least one valid license
    across their assigned companies.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            associate = associateuser.objects.get(user=request.user)
            companies = associate.get_companies()
            if not companies:
                return redirect('no_company_page')
            has_valid = any(License.has_valid_license(company) for company in companies)
            if not has_valid:
                return redirect('license_invalid_page')
        except associateuser.DoesNotExist:
            return redirect('not_an_associate_page')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def permission_required(module, action):
    """
    Checks role-based permissions from ROLE_PERMISSIONS for the given
    module and action. Requires user to have a UserProfile.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            if hasattr(user, 'profile') and user.profile.has_permission(module, action):
                return view_func(request, *args, **kwargs)
            logger.warning(
                "Permission denied for user '%s': module=%s action=%s",
                user.username, module, action,
            )
            return HttpResponseForbidden("You do not have permission to access this resource.")
        return _wrapped_view
    return decorator
