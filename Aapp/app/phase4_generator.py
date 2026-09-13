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

from Aapp.app.pdf_engine import build_pdf, kv_table, INR, section_divider

logger = logging.getLogger(__name__)

HEADER_STYLE = [
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0B2545')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ('TOPPADDING', (0, 0), (-1, -1), 5),
]


def _company(request):
    from Sapp.app.company import Company
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Form I & II — CL Registration Certificate ────────────────────────────────

@login_required
def download_cl_registration_cert(request, reg_id):
    from Aapp.app.contract_labour import ContractLabourRegistration
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    rec = get_object_or_404(ContractLabourRegistration, reg_id=reg_id, company=company)

    story = [kv_table([
        ('Establishment Name', rec.establishment_name),
        ('Registration Certificate No.', rec.registration_cert_no or '—'),
        ('Registration Date', rec.registration_date.strftime('%d %b %Y') if rec.registration_date else '—'),
        ('Registering Authority', rec.registration_authority or '—'),
        ('Nature of Work', rec.nature_of_work),
        ('Max Contract Workers', str(rec.max_contract_workers)),
        ('Status', 'Active' if rec.is_active else 'Inactive'),
    ])]

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'Contract Labour (R&A) Act 1970 — Registration Certificate (Form I & II)',
            'doc_number': rec.registration_cert_no or f'CL-REG-{rec.reg_id}',
        })
    except Exception as e:
        logger.exception('CL registration cert PDF failed for reg_id=%s: %s', reg_id, e)
        raise Http404('Could not generate CL Registration Certificate.')

    fname = f'CL_Registration_{company.company_name.replace(" ", "_")}_{rec.reg_id}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── Form XIII — Contract Employment Card ─────────────────────────────────────

@login_required
def download_employment_card(request, contractor_id, card_id):
    from Aapp.app.contract_labour import ContractEmploymentCard
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    card = get_object_or_404(ContractEmploymentCard, card_id=card_id,
                              contractor_id=contractor_id, company=company)

    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Contractor', card.contractor.contractor_name),
        ('Worker Name', card.employee.name),
        ('Employee Code', card.employee.employeecode),
        ('Card No.', card.card_number or '—'),
        ('Token No.', card.token_number or '—'),
        ('Work Description', card.work_description),
        ('Work Site', card.work_site),
        ('Wage Rate', INR(card.wage_rate)),
        ('Issue Date', card.issue_date.strftime('%d %b %Y')),
        ('Validity Date', card.validity_date.strftime('%d %b %Y') if card.validity_date else '—'),
    ])]

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'Contract Labour (R&A) Act 1970 — Employment Card (Form XIII)',
            'doc_number': card.card_number or f'CL-CARD-{card.card_id}',
        })
    except Exception as e:
        logger.exception('Employment card PDF failed for card_id=%s: %s', card_id, e)
        raise Http404('Could not generate Employment Card.')

    fname = f'Employment_Card_{card.employee.employeecode}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── Form XIV — Contract Service Certificate ──────────────────────────────────

@login_required
def download_service_certificate(request, contractor_id, cert_id):
    from Aapp.app.contract_labour import ContractServiceCertificate
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    cert = get_object_or_404(ContractServiceCertificate, cert_id=cert_id,
                              contractor_id=contractor_id, company=company)

    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Contractor', cert.contractor.contractor_name),
        ('Worker Name', cert.employee.name),
        ('Employee Code', cert.employee.employeecode),
        ('Work Description', cert.work_description),
        ('Work Site', cert.work_site),
        ('Date of Employment', cert.date_of_employment.strftime('%d %b %Y')),
        ('Date of Termination', cert.date_of_termination.strftime('%d %b %Y')),
        ('Reason for Termination', cert.reason_for_termination or '—'),
        ('Last Wage Paid', INR(cert.last_wage_paid)),
        ('Certificate Date', cert.certificate_date.strftime('%d %b %Y')),
    ])]

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'Contract Labour (R&A) Act 1970 — Service Certificate (Form XIV)',
            'doc_number': f'CL-CERT-{cert.cert_id}',
        })
    except Exception as e:
        logger.exception('Service certificate PDF failed for cert_id=%s: %s', cert_id, e)
        raise Http404('Could not generate Service Certificate.')

    fname = f'Service_Certificate_{cert.employee.employeecode}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── Form 20(CL) — Half-Yearly Return ──────────────────────────────────────────

@login_required
def download_cl_return(request, return_id):
    from Aapp.app.contract_labour import ContractLabourHalfYearlyReturn
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    rec = get_object_or_404(ContractLabourHalfYearlyReturn, return_id=return_id, company=company)

    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Contractor', rec.contractor.contractor_name),
        ('Period', f'{rec.get_half_year_display()} {rec.year}'),
    ])]
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())

    rows = [
        ['Particulars', 'Value'],
        ['Total Workers Employed', str(rec.total_workers_employed)],
        ['Total Man-Days', str(rec.total_man_days)],
        ['Total Wages Paid', INR(rec.total_wages_paid)],
        ['Total Overtime Hours', str(rec.total_overtime_hours)],
        ['Total Overtime Wages', INR(rec.total_overtime_wages)],
    ]
    t = Table(rows, colWidths=[300, 150])
    t.setStyle(TableStyle(HEADER_STYLE + [('ALIGN', (1, 0), (1, -1), 'RIGHT')]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'Contract Labour (R&A) Act 1970 — Half-Yearly Return (Form 20-CL)',
            'doc_number': rec.acknowledgement_no or f'CL-RET-{rec.year}-{rec.half_year}',
        })
    except Exception as e:
        logger.exception('CL half-yearly return PDF failed for return_id=%s: %s', return_id, e)
        raise Http404('Could not generate Contract Labour Half-Yearly Return.')

    fname = f'CL_Return_{rec.contractor.contractor_name.replace(" ", "_")}_{rec.year}_{rec.half_year}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── Contractor Payment Register (full history for one contractor) ───────────

@login_required
def download_contractor_payment_register(request, contractor_id):
    from Aapp.app.contractor import contractor, contractor_payment
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    c = get_object_or_404(contractor, contractor_id=contractor_id, company=company)
    records = contractor_payment.objects.filter(contractor=c).order_by('salary_year', 'salary_month')
    if not records.exists():
        raise Http404('No payment records found for this contractor.')

    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Contractor', c.contractor_name),
        ('Licence No.', c.contractor_license_no or '—'),
    ])]
    story.append(Spacer(1, 6 * mm))

    rows = [['Month/Year', 'Amount (₹)', 'Payment Date', 'Reference', 'Remarks']]
    total = 0
    for p in records:
        rows.append([f'{p.salary_month}/{p.salary_year}', INR(p.payment_amount),
                     p.payment_date.strftime('%d-%b-%Y'), p.payment_reference or '—',
                     (p.remarks or '—')[:40]])
        total += p.payment_amount
    rows.append(['TOTAL', INR(total), '', '', ''])

    t = Table(rows, colWidths=[80, 90, 90, 100, 130])
    t.setStyle(TableStyle(HEADER_STYLE + [
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'Contractor Payment Register',
            'doc_number': f'CTR-PAY-{c.contractor_id}',
        })
    except Exception as e:
        logger.exception('Contractor payment register PDF failed for contractor_id=%s: %s', contractor_id, e)
        raise Http404('Could not generate Contractor Payment register.')

    fname = f'Contractor_Payment_Register_{c.contractor_name.replace(" ", "_")}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response
