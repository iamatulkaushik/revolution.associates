"""
phase4_generator.py
====================
Phase 4 — Contract Labour (Regulation & Abolition) Act, 1970 documents.
All single-record or single-contractor-scoped documents (no month/year
period picker needed — statutory format is per-registration, per-card,
per-certificate, per-return, or full contractor payment history).

    Form I & II  -> ContractLabourRegistration cert -> download_cl_registration_cert
    Form XIII    -> ContractEmploymentCard           -> download_employment_card
    Form XIV     -> ContractServiceCertificate       -> download_service_certificate
    Form 20(CL)  -> ContractLabourHalfYearlyReturn   -> download_cl_return
    (no form no.)-> Contractor Payment Register      -> download_contractor_payment_register

Wire into Aapp/urls.py:

    from Aapp.app.phase4_generator import (
        download_cl_registration_cert, download_employment_card,
        download_service_certificate, download_cl_return,
        download_contractor_payment_register,
    )

    path('contract-labour/registration/<int:reg_id>/download/', download_cl_registration_cert, name='download_cl_registration_cert'),
    path('contract-labour/<int:contractor_id>/cards/<int:card_id>/download/', download_employment_card, name='download_employment_card'),
    path('contract-labour/<int:contractor_id>/certificates/<int:cert_id>/download/', download_service_certificate, name='download_service_certificate'),
    path('contract-labour/returns/<int:return_id>/download/', download_cl_return, name='download_cl_return'),
    path('contractors/<int:contractor_id>/payments/download/', download_contractor_payment_register, name='download_contractor_payment_register'),

Add corresponding row/nav links in list_cl_registration, list_employment_cards,
list_service_certificates, list_cl_returns, list_contractors.
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


def _send(pdf_fname):
    pdf, fname = pdf_fname
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


def _build(fn, *args):
    from Aapp.app.services.statutory_files import StatutoryFileError
    try:
        return _send(fn(*args))
    except StatutoryFileError as e:
        raise Http404(str(e))


# ── Form I & II — CL Registration Certificate ────────────────────────────────

@login_required
def download_cl_registration_cert(request, reg_id):
    from Aapp.app.contract_labour import ContractLabourRegistration
    from Aapp.app.services import contract_labour_registers as cl
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    rec = get_object_or_404(ContractLabourRegistration, reg_id=reg_id, company=company)
    return _build(cl.build_cl_registration_pdf, company, rec)


# ── Form XIII — Contract Employment Card ─────────────────────────────────────

@login_required
def download_employment_card(request, contractor_id, card_id):
    from Aapp.app.contract_labour import ContractEmploymentCard
    from Aapp.app.services import contract_labour_registers as cl
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    card = get_object_or_404(ContractEmploymentCard, card_id=card_id,
                              contractor_id=contractor_id, company=company)
    return _build(cl.build_employment_card_pdf, company, card)


# ── Form XIV — Contract Service Certificate ──────────────────────────────────

@login_required
def download_service_certificate(request, contractor_id, cert_id):
    from Aapp.app.contract_labour import ContractServiceCertificate
    from Aapp.app.services import contract_labour_registers as cl
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    cert = get_object_or_404(ContractServiceCertificate, cert_id=cert_id,
                              contractor_id=contractor_id, company=company)
    return _build(cl.build_service_certificate_pdf, company, cert)


# ── Form 20(CL) — Half-Yearly Return ──────────────────────────────────────────

@login_required
def download_cl_return(request, return_id):
    from Aapp.app.contract_labour import ContractLabourHalfYearlyReturn
    from Aapp.app.services import contract_labour_registers as cl
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    rec = get_object_or_404(ContractLabourHalfYearlyReturn, return_id=return_id, company=company)
    return _build(cl.build_cl_return_pdf, company, rec)


# ── Contractor Payment Register (full history for one contractor) ───────────

@login_required
def download_contractor_payment_register(request, contractor_id):
    from Aapp.app.contractor import contractor
    from Aapp.app.services import contract_labour_registers as cl
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    c = get_object_or_404(contractor, contractor_id=contractor_id, company=company)
    return _build(cl.build_contractor_payment_register_pdf, company, c)
