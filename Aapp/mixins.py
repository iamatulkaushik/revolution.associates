# Mixin to filter querysets by selected company
from django.shortcuts import redirect
from django.contrib import messages

class CompanyFilterMixin:
    """Mixin to automatically filter querysets by selected company"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if company is selected
        if not hasattr(request, 'selected_company') or not request.selected_company:
            messages.warning(request, 'Please select a company first.')
            return redirect('Aapp:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        if hasattr(self.request, 'selected_company') and self.request.selected_company:
            return queryset.filter(company=self.request.selected_company)
        return queryset.none()


class CompanyFormMixin:
    """Mixin to automatically set company on form save"""
    
    def form_valid(self, form):
        if hasattr(self.request, 'selected_company') and self.request.selected_company:
            form.instance.company = self.request.selected_company
        return super().form_valid(form)
