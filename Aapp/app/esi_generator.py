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
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING

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


def _wage_rupees(v):
    """ESIC portal accepts whole-rupee wages only (no paise, no '.00')."""
    return int(Decimal(v or 0).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _ceil_rupee(v):
    """ESI Act: a fraction of a rupee in a contribution rounds UP."""
    return Decimal(v or 0).to_integral_value(rounding=ROUND_CEILING)


# ESIC "Reason for Zero Wages" is a numeric code (1-13), not free text.
ESIC_REASON_ON_LEAVE = '1'


class EsiPeriodForm(forms.Form):
    month = forms.ChoiceField(choices=[(i, calendar.month_name[i]) for i in range(1, 13)])
    year = forms.ChoiceField(choices=[(y, y) for y in range(2026, 2032)])


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
    from Aapp.app.services import statutory_files as sf

    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    try:
        pdf, fname = sf.build_esi_challan_pdf(company, month, year)
    except sf.NothingToGenerate as e:
        return _no_esi_data_response(request, month, year, str(e))
    except sf.StatutoryFileError as e:
        raise Http404(str(e))

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
    from Aapp.app.services import statutory_files as sf

    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    try:
        content, fname = sf.build_esi_upload_xlsx(company, month, year)
    except sf.NothingToGenerate as e:
        return _no_esi_data_response(request, month, year, str(e))
    except sf.StatutoryFileError as e:
        raise Http404(str(e))

    response = HttpResponse(
        content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response