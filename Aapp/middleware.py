# Middleware to inject selected company into request object
class CompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            company_id = request.session.get('selected_company_id')
            if company_id:
                from Sapp.app.company import Company
                try:
                    request.selected_company = Company.objects.get(company_id=company_id)
                except Company.DoesNotExist:
                    request.selected_company = None
            else:
                request.selected_company = None
        else:
            request.selected_company = None
        return self.get_response(request)
