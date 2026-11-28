"""
pow_generator.py
================
Payment of Wages Act, 1936 — Form IV (Rule 18) Annual Return PDF,
generated from a recorded PaymentOfWagesAnnualReturn. Header-totals
based, single-record document — no per-employee line file required
by the statutory format.

Wire into Aapp/urls.py:

    from Aapp.app.pow_generator import download_pow_return

    path('wages/payment-of-wages-returns/<int:return_id>/download/', download_pow_return, name='download_pow_return'),

Add to list_pow_returns's row['actions'].
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
def download_pow_return(request, return_id):
    """GET /wages/payment-of-wages-returns/<return_id>/download/ — Form IV PDF."""
    from Aapp.app.wage_compliance import PaymentOfWagesAnnualReturn
    from Aapp.app.services.wage_returns import build_pow_return_pdf
    from Aapp.app.services.statutory_files import StatutoryFileError

    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    rec = get_object_or_404(PaymentOfWagesAnnualReturn, return_id=return_id, company=company)
    try:
        pdf, fname = build_pow_return_pdf(company, rec)
    except StatutoryFileError as e:
        raise Http404(str(e))
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response
