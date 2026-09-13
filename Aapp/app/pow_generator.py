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
    from Aapp.app.pdf_engine import build_pdf, doc_styles, kv_table, INR, section_divider
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    rec = get_object_or_404(PaymentOfWagesAnnualReturn, return_id=return_id, company=company)

    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Return Year', str(rec.year)),
        ('Total Persons Employed', str(rec.total_employed)),
        ('Wage Period', rec.get_wage_period_display()),
        ('Mode of Payment', rec.get_payment_mode_display()),
    ])]
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())

    rows = [
        ['Particulars', 'Amount (₹)'],
        ['Total Wages Paid', INR(rec.total_wages_paid)],
        ['Total Fines Imposed', INR(rec.total_fines_imposed)],
        ['Total Fines Realised', INR(rec.total_fines_realised)],
        ['Total Deductions (other than fines)', INR(rec.total_deductions)],
    ]
    t = Table(rows, colWidths=[300, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0B2545')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'Payment of Wages Act — Annual Return (Form IV)',
            'doc_number': rec.acknowledgement_no or f'POW-{rec.year}',
        })
    except Exception as e:
        logger.exception('POW return PDF failed for return_id=%s: %s', return_id, e)
        raise Http404('Could not generate Payment of Wages return.')

    fname = f'POW_Form_IV_{company.company_name.replace(" ", "_")}_{rec.year}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response
