from functools import wraps
from django.shortcuts import redirect
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
