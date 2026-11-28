"""
lwf_generator.py
================
Punjab LWF Act 1965 (Haryana) — printable challan PDF for a recorded
LabourWelfareFundContribution. LWF is a flat per-head rate (not
wage-based), so unlike EPF/ESI this needs no per-employee line file —
the header totals on the record are the complete filing figure.

Wire into Aapp/urls.py:

    from Aapp.app.lwf_generator import download_lwf_challan

    path('labour-welfare-fund/<int:lwf_id>/challan/', download_lwf_challan, name='download_lwf_challan'),

Add to list_lwf's row['actions'].
"""

import logging
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)


def _company(request):
    from Sapp.app.company import Company
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


@login_required
def download_lwf_challan(request, lwf_id):
    """GET /labour-welfare-fund/<lwf_id>/challan/ — printable LWF challan PDF."""
    from Aapp.app.labour_welfare import LabourWelfareFundContribution

    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    from django.contrib import messages
    from django.shortcuts import redirect
    from Aapp.app.statutory_gates import get_company_gates, labour_required
    ok, msg = labour_required(get_company_gates(company), 'LWF challan')
    if not ok:
        messages.error(request, msg)
        return redirect('list_lwf')

    rec = get_object_or_404(LabourWelfareFundContribution, lwf_id=lwf_id, company=company)

    from Aapp.app.services import statutory_files as sf
    try:
        pdf, fname = sf.build_lwf_challan_pdf(company, rec)
    except sf.StatutoryFileError as e:
        raise Http404(str(e))

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response