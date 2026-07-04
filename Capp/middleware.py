# Middleware to lock every request to the logged-in owner's single company.
# Unlike Aapp (multi-company, session-selected), a Company Owner never
# switches companies, so this is always derived straight from the profile.
class CompanyOwnerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.owner_profile = None
        request.owned_company = None
        if request.user.is_authenticated:
            profile = getattr(request.user, 'company_owner_profile', None)
            if profile is not None:
                request.owner_profile = profile
                request.owned_company = profile.company
        return self.get_response(request)
