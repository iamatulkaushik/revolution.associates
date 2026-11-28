"""
phase5_generator.py
====================
Phase 5 — final low-frequency documents. Three shapes:

  A) Company-wide registers (all rows, no period filter):
     - Gratuity Nominee Register (Form F)   -> download_gratuity_nominee_register
     - EPF Nomination Register (Form 2)     -> download_epf_nomination_register
     - ESI Family Register (Form 1A)        -> download_esi_family_register

  B) Single-row notice/record documents:
     - Gratuity Employer Notice (A/B/C/D)   -> download_employer_notice
     - Gratuity Payment Notice (I/J)        -> download_payment_notice
     - Establishment Registration Cert      -> download_establishment_cert
     - Investment Declaration (Form 12BB)   -> download_investment_declaration

  C) Multi-employee FY export (.xlsx):
     - Form 24Q deductee prep sheet         -> download_form24q_export

Wire into Aapp/urls.py:

    from Aapp.app.phase5_generator import (
        download_gratuity_nominee_register, download_epf_nomination_register,
        download_esi_family_register, download_employer_notice,
        download_payment_notice, download_establishment_cert,
        download_investment_declaration, download_form24q_export,
    )

    path('gratuity/nominees/download/', download_gratuity_nominee_register, name='download_gratuity_nominee_register'),
    path('epf/nominations/download/', download_epf_nomination_register, name='download_epf_nomination_register'),
    path('esi/family/download/', download_esi_family_register, name='download_esi_family_register'),
    path('gratuity/employer-notices/<int:notice_id>/download/', download_employer_notice, name='download_employer_notice'),
    path('gratuity/payment-notices/<int:notice_id>/download/', download_payment_notice, name='download_payment_notice'),
    path('shops/establishments/<int:estab_id>/download/', download_establishment_cert, name='download_establishment_cert'),
    path('income-tax/investment-declaration/<int:profile_id>/download/', download_investment_declaration, name='download_investment_declaration'),
    path('income-tax/form24q-export/<str:financial_year>/download/', download_form24q_export, name='download_form24q_export'),

Add corresponding row/nav links in list_nominees, list_epf_nominations,
list_esi_family, list_employer_notices, list_payment_notices,
list_establishments. Form 24Q export has no existing list view — link it
from wherever the Form16 module's FY picker lives (Aapp/app/form16.py).
"""

import io
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


# ── A) Gratuity Nominee Register (Form F) ────────────────────────────────────

@login_required
def download_gratuity_nominee_register(request):
    from Aapp.app.services import nominations as nom
    from Aapp.app.services.statutory_files import StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    try:
        pdf, fname = nom.build_gratuity_nominee_register_pdf(company)
    except StatutoryFileError as e:
        raise Http404(str(e))
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── A) EPF Nomination Register (Form 2) ──────────────────────────────────────

@login_required
def download_epf_nomination_register(request):
    from Aapp.app.services import nominations as nom
    from Aapp.app.services.statutory_files import StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    try:
        pdf, fname = nom.build_epf_nomination_register_pdf(company)
    except StatutoryFileError as e:
        raise Http404(str(e))
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── A) ESI Family Register (Form 1A) ─────────────────────────────────────────

@login_required
def download_esi_family_register(request):
    from Aapp.app.services import nominations as nom
    from Aapp.app.services.statutory_files import StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    try:
        pdf, fname = nom.build_esi_family_register_pdf(company)
    except StatutoryFileError as e:
        raise Http404(str(e))
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Gratuity Employer Notice (Form A/B/C/D) ───────────────────────────────

@login_required
def download_employer_notice(request, notice_id):
    from Aapp.app.gratuity import gratuity_employer_notice
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    rec = get_object_or_404(gratuity_employer_notice, notice_id=notice_id, company=company)

    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Notice Type', rec.get_notice_type_display()),
        ('Notice Date', rec.notice_date.strftime('%d %b %Y')),
        ('Submitted To', rec.submitted_to or '—'),
        ('Acknowledgement No.', rec.acknowledgement_no or '—'),
        ('Remarks', rec.remarks or '—'),
    ])]

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': f'Payment of Gratuity Act 1972 — {rec.get_notice_type_display()}',
            'doc_number': rec.acknowledgement_no or f'GRAT-NOTICE-{rec.notice_id}',
        })
    except Exception as e:
        logger.exception('Gratuity employer notice PDF failed for notice_id=%s: %s', notice_id, e)
        raise Http404('Could not generate Employer Notice.')

    fname = f'Gratuity_Notice_{rec.notice_type}_{company.company_name.replace(" ", "_")}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Gratuity Payment/Rejection Notice (Form I/J) ──────────────────────────

@login_required
def download_payment_notice(request, notice_id):
    from Aapp.app.gratuity import gratuity_payment_notice
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    rec = get_object_or_404(gratuity_payment_notice, notice_id=notice_id, company=company)

    fields = [
        ('Establishment Name', company.company_name),
        ('Employee', rec.employee.name),
        ('Notice Type', rec.get_notice_type_display()),
        ('Notice Date', rec.notice_date.strftime('%d %b %Y')),
        ('Gratuity Amount', INR(rec.gratuity_amount)),
    ]
    if rec.notice_type == 'I':
        fields.append(('Payment Due Date', rec.payment_due_date.strftime('%d %b %Y') if rec.payment_due_date else '—'))
    else:
        fields.append(('Rejection Reason', rec.rejection_reason or '—'))

    story = [kv_table(fields)]

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': f'Payment of Gratuity Act 1972 — {rec.get_notice_type_display()}',
            'doc_number': f'GRAT-PAYNOTICE-{rec.notice_id}',
        })
    except Exception as e:
        logger.exception('Gratuity payment notice PDF failed for notice_id=%s: %s', notice_id, e)
        raise Http404('Could not generate Payment Notice.')

    fname = f'Gratuity_PaymentNotice_{rec.employee.employeecode}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Establishment Registration Certificate ────────────────────────────────

@login_required
def download_establishment_cert(request, estab_id):
    from Aapp.app.shops_act import establishment_details
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    e = get_object_or_404(establishment_details, estab_id=estab_id, company=company)

    story = [kv_table([
        ('Establishment Name', e.establishment_name),
        ('Registration No.', e.registration_number or '—'),
        ('Registration Date', e.registration_date.strftime('%d %b %Y') if e.registration_date else '—'),
        ('Renewal Due', e.renewal_date.strftime('%d %b %Y') if e.renewal_date else '—'),
        ('Working Hours', f'{e.opening_time.strftime("%I:%M %p")} – {e.closing_time.strftime("%I:%M %p")}'),
        ('Weekly Off', e.get_weekly_off_day_display()),
        ('Manager', e.manager_name or '—'),
        ('Address', e.address or '—'),
    ])]

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'Shops & Establishments Act — Registration Certificate',
            'doc_number': e.registration_number or f'ESTAB-{e.estab_id}',
        })
    except Exception as ex:
        logger.exception('Establishment cert PDF failed for estab_id=%s: %s', estab_id, ex)
        raise Http404('Could not generate Establishment Certificate.')

    fname = f'Establishment_Cert_{e.establishment_name.replace(" ", "_")}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Investment Declaration (Form 12BB) ────────────────────────────────────

@login_required
def download_investment_declaration(request, profile_id):
    from Aapp.app.income_tax import EmployeeTaxProfile
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    profile = get_object_or_404(EmployeeTaxProfile, profile_id=profile_id, employee__CompanyID=company)
    emp = profile.employee

    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Employee', emp.name),
        ('Employee Code', emp.employeecode),
        ('PAN', getattr(emp, 'pan_number', '') or '—'),
        ('Financial Year', profile.financial_year),
        ('Tax Regime Chosen', profile.get_regime_display()),
    ])]
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())

    if profile.regime == 'old':
        rows = [
            ['Declaration (Form 12BB) — Section', 'Amount (₹)'],
            ['80C — PF/ELSS/LIC/PPF/Tuition (max 1,50,000)', INR(profile.section_80c)],
            ['80D — Medical Insurance Premium', INR(profile.section_80d)],
            ['80CCD(1B) — Additional NPS (max 50,000)', INR(profile.section_80ccd_1b)],
            ['24(b) — Home Loan Interest (self-occ. cap 2,00,000)', INR(profile.home_loan_interest_24b)],
            ['HRA Claimed', INR(profile.hra_claimed)],
            ['Other Deductions (80E/80G/80TTA etc.)', INR(profile.other_deductions)],
        ]
        t = Table(rows, colWidths=[330, 120])
        t.setStyle(TableStyle(HEADER_STYLE + [('ALIGN', (1, 0), (1, -1), 'RIGHT')]))
        story.append(t)
    else:
        from reportlab.platypus import Paragraph
        from Aapp.app.pdf_engine import doc_styles
        story.append(Paragraph(
            'Employee has opted for the New Tax Regime — Chapter VI-A deductions '
            'are not applicable under this regime.', doc_styles()['Normal']))

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'Investment Declaration (Form 12BB)',
            'doc_number': f'12BB-{emp.employeecode}-{profile.financial_year}',
        })
    except Exception as e:
        logger.exception('Investment declaration PDF failed for profile_id=%s: %s', profile_id, e)
        raise Http404('Could not generate Investment Declaration.')

    fname = f'Investment_Declaration_{emp.employeecode}_{profile.financial_year}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── C) Form 24Q Deductee Prep Sheet (.xlsx) ──────────────────────────────────

@login_required
def download_form24q_export(request, financial_year):
    """
    GET /income-tax/form24q-export/<financial_year>/download/
    Uses the existing tds_filing_helper_rows() from Aapp/app/form16.py —
    only wraps it in an .xlsx so it can actually be handed to a filer,
    per the docstring's own note ("ready to hand to an Excel export").
    """
    from Aapp.app.services import reports as rp
    from Aapp.app.services.statutory_files import StatutoryFileError

    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    try:
        content, fname = rp.build_form24q_xlsx(company, financial_year)
    except StatutoryFileError as e:
        raise Http404(str(e))

    response = HttpResponse(
        content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response