# Context processor to make selected company available in all templates
def company_context(request):
    """Add selected company to template context"""
    if request.user.is_authenticated:
        from Sapp.app.user import get_user_type
        
        user_type, profile = get_user_type(request.user)
        companies = []
        
        if user_type == 'associate':
            companies = profile.get_companies()
        elif user_type == 'subuser':
            companies = profile.get_companies()
        
        return {
            'user_companies': companies,
            'selected_company': getattr(request, 'selected_company', None)
        }
    return {}
