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
    from Aapp.app.pdf_engine import build_pdf, doc_styles, kv_table, INR, section_divider
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    rec = get_object_or_404(LabourWelfareFundContribution, lwf_id=lwf_id, company=company)

    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Contribution Period', f'{rec.get_contribution_period_display()} {rec.year}'),
        ('Total Employees', str(rec.total_employees)),
        ('Due Date', rec.due_date.strftime('%d %b %Y') if rec.due_date else '—'),
    ])]
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())

    rows = [
        ['Particulars', 'Amount (₹)'],
        ['Employee Contribution', INR(rec.employee_contribution)],
        ['Employer Contribution', INR(rec.employer_contribution)],
    ]
    if rec.is_late and rec.late_interest_amount:
        rows.append(['Late Interest (Sec. 9A @ 12%)', INR(rec.late_interest_amount)])
    rows.append(['TOTAL CONTRIBUTION', INR(rec.total_contribution + (rec.late_interest_amount if rec.is_late else 0))])

    t = Table(rows, colWidths=[300, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0B2545')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEBELOW', (0, -2), (-1, -2), 1, colors.black),
        ('GRID', (0, 0), (-1, -2), 0.4, colors.HexColor('#CBD5E1')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'Labour Welfare Fund Challan',
            'doc_number': rec.challan_no or f'LWF-{rec.contribution_period}-{rec.year}',
        })
    except Exception as e:
        logger.exception('LWF challan PDF failed for lwf_id=%s: %s', lwf_id, e)
        raise Http404('Could not generate LWF challan.')

    fname = f'LWF_Challan_{company.company_name.replace(" ", "_")}_{rec.contribution_period}_{rec.year}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response
