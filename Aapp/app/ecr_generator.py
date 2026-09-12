"""
ecr_generator.py
================
EPFO ECR-2.0 text file generator + EPF Challan PDF.

Wire into Aapp/urls.py:

    from Aapp.app.ecr_generator import download_ecr_text, download_epf_challan

    path('epf/ecr/<int:ecr_id>/download/', download_ecr_text, name='download_ecr_text'),
    path('epf/ecr/<int:ecr_id>/challan/',  download_epf_challan, name='download_epf_challan'),

Add these two links next to the 'Edit' action in list_epf_ecr's row['actions'].

ECR-2.0 line format (per EPFO spec, '#~#' delimited, one line per member):
UAN#~#MemberName#~#GrossWages#~#EPFWages#~#EPSWages#~#EDLIWages#~#EPFContriRemitted
    #~#EPSContriRemitted#~#EPFEPSDiffRemitted#~#NCPDays#~#Refund

This module derives GrossWages/EPFWages from salary_slip and splits the
company-level EpfMonthlyEcr totals proportionally is NOT done — instead it
computes each member's contribution directly from their own salary_slip
row for the matching month/year, which is more accurate than allocating
an aggregate. The EpfMonthlyEcr record supplies the header totals only.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)

EPS_WAGE_CEILING = Decimal('15000')


def _company(request):
    from Sapp.app.company import Company
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


def _r2(v):
    return Decimal(v).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _r0(v):
    return int(Decimal(v).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _member_lines(company, month, year):
    """
    Build one ECR-2.0 line per employee with a salary_slip for this
    month/year and a UAN on file. Skips employees without UAN (not
    EPF-enrolled) — matches the fail-closed statutory gate pattern
    used everywhere else (see Aapp/app/statutory_gates.py).
    """
    from Aapp.app.salary_processing import salary_slip

    slips = (salary_slip.objects
             .filter(company_id=company,
                     processing_id__month=month,
                     processing_id__year=year)
             .select_related('employee_id')
             .order_by('employee_id__employeecode'))

    lines = []
    skipped = []
    for s in slips:
        emp = s.employee_id
        uan = (getattr(emp, 'uan_number', '') or '').strip()
        if not uan:
            skipped.append(emp.employeecode)
            continue

        epf_wages = _r0(s.basic_earned)
        eps_wages = _r0(min(Decimal(epf_wages), EPS_WAGE_CEILING))
        edli_wages = eps_wages
        gross_wages = _r0(s.gross_earnings)

        epf_contri_remitted = _r0(s.pf_deduction)          # employee 12%
        # Employer side: EPS 8.33% (capped) + EPF diff goes to employer EPF a/c
        eps_contri = _r0((Decimal(eps_wages) * Decimal('0.0833')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        epf_eps_diff = _r0(s.pf_employer_contribution) - eps_contri
        if epf_eps_diff < 0:
            epf_eps_diff = 0

        ncp_days = 0  # Non-Contributory Period days — LOP days; wire to attendance if tracked separately
        refund = 0

        line = '#~#'.join(str(x) for x in [
            uan,
            (emp.name or '').strip(),
            gross_wages,
            epf_wages,
            eps_wages,
            edli_wages,
            epf_contri_remitted,
            eps_contri,
            epf_eps_diff,
            ncp_days,
            refund,
        ])
        lines.append(line)

    return lines, skipped


@login_required
def download_ecr_text(request, ecr_id):
    """
    GET /epf/ecr/<ecr_id>/download/
    Downloads the ECR-2.0 .txt file ready for EPFO unified portal upload.
    """
    from Aapp.app.epf_esi import EpfMonthlyEcr

    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    ecr = get_object_or_404(EpfMonthlyEcr, ecr_id=ecr_id, company=company)

    lines, skipped = _member_lines(company, ecr.salary_month, ecr.salary_year)
    if not lines:
        raise Http404(
            'No EPF-enrolled employees with salary slips found for '
            f'{ecr.salary_month}/{ecr.salary_year}. Ensure UAN is set on '
            'employee records and salary has been processed for this period.'
        )

    if skipped:
        logger.warning(
            'ECR %s/%s for %s: skipped %d employee(s) with no UAN: %s',
            ecr.salary_month, ecr.salary_year, company.company_name,
            len(skipped), ', '.join(skipped)
        )

    content = '\n'.join(lines) + '\n'
    fname = f'ECR_{company.company_name.replace(" ", "_")}_{ecr.salary_month}_{ecr.salary_year}.txt'

    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    if skipped:
        response['X-ECR-Skipped-Count'] = str(len(skipped))
    return response


@login_required
def download_epf_challan(request, ecr_id):
    """
    GET /epf/ecr/<ecr_id>/challan/
    Downloads a printable EPF combined challan PDF (A/C 1, 2, 10, 21, 22)
    summarizing the amounts to remit, using the EpfMonthlyEcr header totals.
    """
    from Aapp.app.epf_esi import EpfMonthlyEcr
    from Aapp.app.pdf_engine import build_pdf, doc_styles, kv_table, INR, section_divider
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    ecr = get_object_or_404(EpfMonthlyEcr, ecr_id=ecr_id, company=company)
    styles = doc_styles()

    story = []
    story.append(kv_table([
        ('Establishment Name', company.company_name),
        ('Wage Month', f'{ecr.salary_month}/{ecr.salary_year}'),
        ('Total Members', str(ecr.total_members)),
    ]))
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())

    rows = [
        ['A/C No.', 'Particulars', 'Amount (₹)'],
        ['1',  'EPF Contribution (Employee 12% + Employer 3.67%)',
         INR(Decimal(ecr.employee_epf) + Decimal(ecr.employer_epf))],
        ['2',  'EPF Admin Charges (0.5%, min ₹500)', INR(ecr.admin_charges)],
        ['10', 'EPS Contribution (Employer 8.33%)',  INR(ecr.employer_eps)],
        ['21', 'EDLI Contribution (0.5%)',            INR(ecr.edli_contribution)],
        ['22', 'EDLI Admin Charges',                  INR(Decimal('0.00'))],
        ['',   'TOTAL REMITTANCE',                    INR(ecr.total_contribution)],
    ]
    t = Table(rows, colWidths=[60, 300, 120])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0B2545')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEBELOW', (0, -2), (-1, -2), 1, colors.black),
        ('GRID', (0, 0), (-1, -2), 0.4, colors.HexColor('#CBD5E1')),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'EPF Combined Challan',
            'doc_number': ecr.challan_no or f'ECR-{ecr.salary_month}-{ecr.salary_year}',
        })
    except Exception as e:
        logger.exception('EPF challan PDF failed for ecr_id=%s: %s', ecr_id, e)
        raise Http404('Could not generate EPF challan.')

    fname = f'EPF_Challan_{company.company_name.replace(" ", "_")}_{ecr.salary_month}_{ecr.salary_year}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response
