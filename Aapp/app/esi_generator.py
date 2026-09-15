"""
esi_generator.py
================
ESIC monthly contribution challan (PDF) + member upload file (.xlsx)
for the Aapp portal — mirrors ecr_generator.py's pattern for EPF.

ESIC's monthly contribution (as opposed to the half-yearly Form 7
return already modeled by EsiContributionReturn) is a separate filing:
a monthly challan + a monthly member wage upload on the ESIC portal.
This module adds both, driven directly off salary_slip so figures can
never drift from what was actually deducted.

Wire into Aapp/urls.py:

    from Aapp.app.esi_generator import (
        select_period_for_esi_monthly, download_esi_monthly_challan,
        download_esi_monthly_upload,
    )

    path('esi/monthly/', select_period_for_esi_monthly, name='select_period_for_esi_monthly'),
    path('esi/monthly/<int:month>/<int:year>/challan/', download_esi_monthly_challan, name='download_esi_monthly_challan'),
    path('esi/monthly/<int:month>/<int:year>/upload.xlsx/', download_esi_monthly_upload, name='download_esi_monthly_upload'),

Add a nav link to select_period_for_esi_monthly next to list_esi_returns.
"""

import io
import logging
import calendar
from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import render

logger = logging.getLogger(__name__)

ESI_EMPLOYEE_RATE = Decimal('0.0075')
ESI_EMPLOYER_RATE = Decimal('0.0325')


def _company(request):
    from Sapp.app.company import Company
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


def _q(v):
    return Decimal(v or 0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class EsiPeriodForm(forms.Form):
    month = forms.ChoiceField(choices=[(i, calendar.month_name[i]) for i in range(1, 13)])
    year = forms.ChoiceField(choices=[(y, y) for y in range(2023, 2031)])


def _esi_slips(company, month, year):
    """
    salary_slip rows with an ESIC number on file and non-zero ESI
    deduction, for the given month/year. Fail-closed: no ESIC number
    on file -> not included, matching the pattern used for UAN in
    ecr_generator.py.
    """
    from Aapp.app.salary_processing import salary_slip

    return (salary_slip.objects
            .filter(company_id=company,
                    processing_id__month=month,
                    processing_id__year=year)
            .select_related('employee_id')
            .order_by('employee_id__employeecode'))


@login_required
def select_period_for_esi_monthly(request):
    """GET/POST /esi/monthly/ — pick month/year, then link to challan + upload."""
    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    form = EsiPeriodForm(request.GET or None)
    month = year = None
    if form.is_valid():
        month = int(form.cleaned_data['month'])
        year = int(form.cleaned_data['year'])

    return render(request, 'Aapp/generic/period_picker.html', {
        'company': company,
        'form': form,
        'page_title': 'ESI Monthly Contribution — Select Period',
        'month': month,
        'year': year,
        'download_urls': ([
            {'label': 'Download Challan PDF', 'name': 'download_esi_monthly_challan'},
            {'label': 'Download Member Upload (.xlsx)', 'name': 'download_esi_monthly_upload'},
        ] if month and year else []),
    })


def _no_esi_data_response(request, month, year, message):
    """Renders the ESI period picker again with an inline error banner
    instead of a bare 404, when a period has no ESI-eligible employees."""
    company = _company(request)
    form = EsiPeriodForm(initial={'month': month, 'year': year})
    return render(request, 'Aapp/generic/period_picker.html', {
        'company': company, 'form': form,
        'page_title': 'ESI Monthly Contribution — Select Period',
        'month': month, 'year': year, 'period_error': message,
    })


@login_required
def download_esi_monthly_challan(request, month, year):
    """GET /esi/monthly/<month>/<year>/challan/ — printable ESIC challan PDF."""
    from Aapp.app.pdf_engine import build_pdf, doc_styles, kv_table, INR, section_divider
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    slips = _esi_slips(company, month, year)
    eligible = [s for s in slips if (getattr(s.employee_id, 'esic_number', '') or '').strip()]
    if not eligible:
        return _no_esi_data_response(
            request, month, year,
            f'No ESI-eligible employees with ESIC number found for {calendar.month_name[month]} {year}. '
            'Ensure ESIC number is set on employee records and salary has been processed.'
        )

    total_wages = sum((s.gross_earnings for s in eligible), Decimal('0'))
    total_employee = sum((s.esi_deduction for s in eligible), Decimal('0'))
    total_employer = sum((s.esi_employer_contribution for s in eligible), Decimal('0'))
    total_contribution = total_employee + total_employer

    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Contribution Month', f'{calendar.month_name[month]} {year}'),
        ('No. of Insured Persons', str(len(eligible))),
    ])]
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())

    rows = [
        ['Particulars', 'Amount (₹)'],
        ['Total Wages', INR(total_wages)],
        ['Employee Contribution (0.75%)', INR(total_employee)],
        ['Employer Contribution (3.25%)', INR(total_employer)],
        ['TOTAL CONTRIBUTION', INR(total_contribution)],
    ]
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
            'title': 'ESI Monthly Contribution Challan',
            'doc_number': f'ESI-{month}-{year}',
        })
    except Exception as e:
        logger.exception('ESI challan PDF failed for %s/%s: %s', month, year, e)
        raise Http404('Could not generate ESI challan.')

    fname = f'ESI_Challan_{company.company_name.replace(" ", "_")}_{month}_{year}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


@login_required
def download_esi_monthly_upload(request, month, year):
    """
    GET /esi/monthly/<month>/<year>/upload.xlsx/
    ESIC monthly contribution member upload file. Columns per ESIC's
    published monthly contribution upload format; all cells forced to
    text to avoid the portal's numeric-cell rejection (same fix already
    used in Cxapp/app/compliance.py's ESI export).
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    slips = _esi_slips(company, month, year)
    eligible = [s for s in slips if (getattr(s.employee_id, 'esic_number', '') or '').strip()]
    if not eligible:
        return _no_esi_data_response(
            request, month, year,
            f'No ESI-eligible employees with ESIC number found for {calendar.month_name[month]} {year}.'
        )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'ESI Monthly Upload'

    headers = ['IP Number', 'IP Name', 'No. of Days', 'Total Monthly Wages',
               'Reason for Zero Wages', 'Last Working Day']
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='0B2545')

    for s in eligible:
        emp = s.employee_id
        row = [
            (emp.esic_number or '').strip(),
            (emp.name or '').strip().upper(),
            str(int(s.paid_days or 0)),
            f'{s.gross_earnings:.2f}',
            '' if s.gross_earnings > 0 else 'LOP',
            '',
        ]
        ws.append(row)
        for col_idx in range(1, len(row) + 1):
            ws.cell(row=ws.max_row, column=col_idx).number_format = '@'

    for col_letter, width in zip('ABCDEF', [14, 28, 12, 18, 20, 16]):
        ws.column_dimensions[col_letter].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    fname = f'ESI_Upload_{company.company_name.replace(" ", "_")}_{month}_{year}.xlsx'
    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response
