"""
Cxapp/app/statutory.py
========================
Company statutory registration update page for the Cxapp (self-signup
Company Owner) portal. Edits the SAME Sapp.app.company.company_statury
row Aapp/Sapp read from — this is the single source of truth for every
statutory gate check in the codebase (get_company_gates in
Cxapp/app/statutory_gates.py, Aapp's equivalent, etc.). Updating it
here immediately changes what CxSalary.process() deducts and what
Cxapp/app/compliance.py is able to export — no separate Cxapp-only
copy of this data exists.

Owner-only: this is company-wide compliance data, not scoped to an
individual employee, so no sub-user role gets write access — even HR.
Sub-users can view the read-only gate status (already surfaced on the
employee detail page and compliance dashboard) but not edit source
registration numbers.
"""

from django import forms
from django.contrib import messages
from django.shortcuts import render, redirect

from Sapp.app.company import company_statury


class CxCompanyStatutoryForm(forms.ModelForm):
    class Meta:
        model = company_statury
        fields = [
            'epfo', 'epfo_date',
            'esic', 'esic_date',
            'gst', 'gst_date',
            'shop_act', 'shop_act_date',
            'labour', 'labour_from', 'labour_to',
            'psara', 'psara_from', 'psara_to',
            'factory', 'factory_from', 'factory_to',
        ]
        widgets = {
            'epfo_date': forms.DateInput(attrs={'type': 'date'}),
            'esic_date': forms.DateInput(attrs={'type': 'date'}),
            'gst_date': forms.DateInput(attrs={'type': 'date'}),
            'shop_act_date': forms.DateInput(attrs={'type': 'date'}),
            'labour_from': forms.DateInput(attrs={'type': 'date'}),
            'labour_to': forms.DateInput(attrs={'type': 'date'}),
            'psara_from': forms.DateInput(attrs={'type': 'date'}),
            'psara_to': forms.DateInput(attrs={'type': 'date'}),
            'factory_from': forms.DateInput(attrs={'type': 'date'}),
            'factory_to': forms.DateInput(attrs={'type': 'date'}),
        }


def cxapp_company_statutory(request):
    from Cxapp.views import owner_only
    return owner_only(_company_statutory)(request)


def _company_statutory(request):
    company = request.cx_company
    instance = company_statury.objects.filter(company=company).first()

    if request.method == 'POST':
        form = CxCompanyStatutoryForm(request.POST, instance=instance)
        if form.is_valid():
            record = form.save(commit=False)
            record.company = company
            record.updated_by = request.user.username
            if instance is None:
                record.created_by = request.user.username
            record.save()
            messages.success(request, 'Statutory registration details updated.')
            return redirect('cxapp_company_statutory')
    else:
        form = CxCompanyStatutoryForm(instance=instance)

    from Cxapp.app.statutory_gates import get_company_gates
    gates = get_company_gates(company)

    return render(request, 'Cxapp/company_statutory.html', {
        'form': form,
        'gates': gates,
    })
