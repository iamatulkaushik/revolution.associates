"""
phase3_generator.py
====================
Phase 3 — Factories Act 1948 register PDFs, all factory-scoped
(not month/year scoped, unlike Phase 1/2). Two shapes:

  A) Single-record documents:
     - Factory Registration Certificate (Form 1 & 2) -> download_factory_registration_cert
     - Annual Return (Form 34)                        -> download_factory_annual_return

  B) Full-history registers, one factory's entire log:
     - Whitewash Register (Form 7)                    -> download_whitewash_register
     - Vessel Examination Register (Form 8)            -> download_vessel_examination_register
     - Accident Register (Form 26)                     -> download_accident_register
     - Leave With Wages Register (Form 15)              -> download_leave_wages_register
       (company-scoped, not factory-scoped — model has no FK to factory)

Wire into Aapp/urls.py:

    from Aapp.app.phase3_generator import (
        download_factory_registration_cert, download_factory_annual_return,
        download_whitewash_register, download_vessel_examination_register,
        download_accident_register, download_leave_wages_register,
    )

    path('factory/<int:factory_id>/certificate/download/', download_factory_registration_cert, name='download_factory_registration_cert'),
    path('factory/annual-return/<int:return_id>/download/', download_factory_annual_return, name='download_factory_annual_return'),
    path('factory/<int:factory_id>/whitewash/download/', download_whitewash_register, name='download_whitewash_register'),
    path('factory/<int:factory_id>/vessel/download/', download_vessel_examination_register, name='download_vessel_examination_register'),
    path('factory/<int:factory_id>/accident/download/', download_accident_register, name='download_accident_register'),
    path('factory/leave-wages/download/', download_leave_wages_register, name='download_leave_wages_register'),

Add corresponding row/nav links in list_factory_registration, list_annual_return,
list_whitewash_register, list_vessel_examination, list_accident_register,
list_leave_wages_register.
"""

import logging
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from reportlab.platypus import Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.lib.units import mm

from Aapp.app.pdf_engine import build_pdf, kv_table, INR, section_divider, _basefont, _basefont_bold

logger = logging.getLogger(__name__)

HEADER_STYLE = [
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0B2545')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, -1), _basefont),
    ('FONTNAME', (0, 0), (-1, 0), _basefont_bold),
    ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ('TOPPADDING', (0, 0), (-1, -1), 5),
]


def _company(request):
    from Sapp.app.company import Company
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── A) Factory Registration Certificate (Form 1 & 2) ─────────────────────────

@login_required
def download_factory_registration_cert(request, factory_id):
    from Aapp.app.factory_act import FactoryRegistration
    from Aapp.app.services import factory_registers as fr
    from Aapp.app.services.statutory_files import StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    obj = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)
    try:
        pdf, fname = fr.build_factory_certificate_pdf(company, obj)
    except StatutoryFileError as e:
        raise Http404(str(e))
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── A) Factory Annual Return (Form 34) ───────────────────────────────────────

@login_required
def download_factory_annual_return(request, return_id):
    from Aapp.app.factory_act import FactoryAnnualReturn
    from Aapp.app.services import factory_registers as fr
    from Aapp.app.services.statutory_files import StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    obj = get_object_or_404(FactoryAnnualReturn, return_id=return_id, factory__company=company)
    try:
        pdf, fname = fr.build_factory_annual_return_pdf(company, obj)
    except StatutoryFileError as e:
        raise Http404(str(e))
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Whitewash Register (Form 7) ───────────────────────────────────────────

@login_required
def download_whitewash_register(request, factory_id):
    from Aapp.app.factory_act import FactoryRegistration
    from Aapp.app.services import factory_registers as fr
    from Aapp.app.services.statutory_files import StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    obj = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)
    try:
        pdf, fname = fr.build_whitewash_register_pdf(company, obj)
    except StatutoryFileError as e:
        raise Http404(str(e))
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Vessel Examination Register (Form 8) ──────────────────────────────────

@login_required
def download_vessel_examination_register(request, factory_id):
    from Aapp.app.factory_act import FactoryRegistration
    from Aapp.app.services import factory_registers as fr
    from Aapp.app.services.statutory_files import StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    obj = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)
    try:
        pdf, fname = fr.build_vessel_register_pdf(company, obj)
    except StatutoryFileError as e:
        raise Http404(str(e))
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Accident Register (Form 26) ───────────────────────────────────────────

@login_required
def download_accident_register(request, factory_id):
    from Aapp.app.factory_act import FactoryRegistration
    from Aapp.app.services import factory_registers as fr
    from Aapp.app.services.statutory_files import StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    obj = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)
    try:
        pdf, fname = fr.build_accident_register_pdf(company, obj)
    except StatutoryFileError as e:
        raise Http404(str(e))
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Leave With Wages Register (Form 15) ───────────────────────────────────
# Company-scoped, not factory-scoped — model has no FK to FactoryRegistration.

@login_required
def download_leave_wages_register(request):
    from Aapp.app.services import nominations as nom
    from Aapp.app.services.statutory_files import StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    try:
        pdf, fname = nom.build_leave_wages_register_pdf(company)
    except StatutoryFileError as e:
        raise Http404(str(e))
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response
