# Middleware to lock every request to the logged-in owner's single company.
# Unlike Aapp (multi-company, session-selected), a Company Owner never
# switches companies, so this is always derived straight from the profile.
from django.utils.deprecation import MiddlewareMixin

class CompanyOwnerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.owner_profile = None
        request.owned_company = None
        if request.user.is_authenticated:
            profile = getattr(request.user, 'owner_profile', None)
            if profile is not None:
                request.owner_profile = profile
                request.owned_company = profile.company
        return self.get_response(request)
    
    def process_request(self, request):
        request.owner_profile = None
        request.owned_company = None

        if not request.user.is_authenticated:
            return

        try:
            from Capp.models import CompanyOwnerProfile
            profile = CompanyOwnerProfile.objects.select_related('company').get(
                user=request.user, is_active=True
            )
            request.owner_profile = profile
            request.owned_company = profile.company
        except Exception:
            pass  # Not an owner — silently pass
