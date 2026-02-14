from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from Sapp.app.license import License
from Sapp.app.user import associateuser

def license_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')  # Assuming you have a login view named 'login'

        try:
            associate = associateuser.objects.get(user=request.user)
            companies = associate.get_companies()
            if not companies:
                # Or handle as per your logic if a user must have a company
                return redirect('no_company_page') 

            has_valid = any(License.has_valid_license(company) for company in companies)

            if not has_valid:
                return redirect('license_invalid_page')  # Redirect to a page indicating invalid license

        except associateuser.DoesNotExist:
            # Handle users who are not associates, if necessary
            # For now, we can redirect them to a generic error page or the login page
            return redirect('not_an_associate_page')

        return view_func(request, *args, **kwargs)
    return _wrapped_view

def permission_required(module, action):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            if hasattr(user, 'profile') and user.profile.has_permission(module, action):
                return view_func(request, *args, **kwargs)
            else:
                return HttpResponseForbidden("You do not have permission to access this resource.")
        return _wrapped_view
    return decorator