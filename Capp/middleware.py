# Locks every request to the logged-in user's single company and resolves mode/role/perms.
#
# Sets: request.owner_profile   owner profile OR operator profile (duck-typed, same flags)
#       request.owned_company
#       request.capp_mode       'DIRECT' | 'ASSOCIATE' | None
#       request.capp_role       'OWNER' | 'OPERATOR' | None
#       request.capp_perms      set of permission names (empty when inactive/anonymous)
from Capp.access import compute_perms, get_mode


class CompanyOwnerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.owner_profile = None
        request.owned_company = None
        request.capp_mode = None
        request.capp_role = None
        request.capp_perms = set()

        if request.user.is_authenticated:
            profile, role = getattr(request.user, 'owner_profile', None), 'OWNER'
            if profile is None:
                profile, role = getattr(request.user, 'operator_profile', None), 'OPERATOR'
            if profile is not None:
                request.owner_profile = profile
                request.owned_company = profile.company
                request.capp_role = role
                request.capp_mode = get_mode(profile.company)
                request.capp_perms = compute_perms(request.capp_mode, role, profile)
        return self.get_response(request)
