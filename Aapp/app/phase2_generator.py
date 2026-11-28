"""
phase2_generator.py
====================
Phase 2 high-frequency register PDFs, all built on the shared
Aapp/app/pdf_engine.py. Two shapes:

  A) Single annual-record documents (header totals only, no line file):
     - Minimum Wages Register (Form V)          -> download_minwages_return
     - Bonus Annual Return (Form D)              -> download_bonus_return
     - Set-On/Set-Off Register (Form B)          -> download_set_on_set_off

  B) Period registers (multi-row, month/year filtered):
     - Fines Register (Form I)                   -> download_fines_register
     - Deductions Register (Form II)              -> download_deductions_register_wages
       (named _wages to avoid clashing with the existing Form16
        download_deductions_report in urls.py)
     - Overtime Register (Form IV, Shops Act)     -> select_period_for_ot_register,
                                                      download_ot_register
     - Bonus Register (Form C)                    -> select_period_for_bonus_register,
                                                      download_bonus_register

Wire into Aapp/urls.py:

    from Aapp.app.phase2_generator import (
        download_minwages_return, download_bonus_return, download_set_on_set_off,
        select_period_for_fines, download_fines_register,
        select_period_for_deductions, download_deductions_register_wages,
        select_period_for_ot_register, download_ot_register,
        select_period_for_bonus_register, download_bonus_register,
    )

    path('wages/minimum-wages-returns/<int:return_id>/download/', download_minwages_return, name='download_minwages_return'),
    path('bonus/annual-returns/<int:return_id>/download/', download_bonus_return, name='download_bonus_return'),
    path('bonus/set-on-set-off/<int:record_id>/download/', download_set_on_set_off, name='download_set_on_set_off'),

    path('wages/fines/report/', select_period_for_fines, name='select_period_for_fines'),
    path('wages/fines/report/<int:month>/<int:year>/download/', download_fines_register, name='download_fines_register'),

    path('wages/deductions/report/', select_period_for_deductions, name='select_period_for_deductions'),
    path('wages/deductions/report/<int:month>/<int:year>/download/', download_deductions_register_wages, name='download_deductions_register_wages'),

    path('attendance/overtime-register/report/', select_period_for_ot_register, name='select_period_for_ot_register'),
    path('attendance/overtime-register/report/<int:month>/<int:year>/download/', download_ot_register, name='download_ot_register'),

    path('bonus/report/', select_period_for_bonus_register, name='select_period_for_bonus_register'),
    path('bonus/report/<int:month>/<int:year>/download/', download_bonus_register, name='download_bonus_register'),

Add corresponding row/nav actions in list_minwages_returns, list_bonus_returns,
list_set_on_set_off, list_fines, list_deductions, list_overtime_register, list_bonus.
"""

import logging
import calendar
from django import forms
from django.contrib.auth.decorators import login_required
from revolution.app.plan_gate import require_feature
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, render
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


def _no_data_response(request, picker_view_name, page_title, month, year, message):
    """Renders the period picker page again with an inline error banner,
    instead of a bare 404, when a period has no records to report."""
    from django import forms as _forms
    company = _company(request)
    form = PeriodForm(initial={'month': month, 'year': year})
    return render(request, 'Aapp/generic/period_picker.html', {
        'company': company, 'form': form, 'page_title': page_title,
        'month': month, 'year': year, 'period_error': message,
    })


class PeriodForm(forms.Form):
    month = forms.ChoiceField(choices=[(i, calendar.month_name[i]) for i in range(1, 13)])
    year = forms.ChoiceField(choices=[(y, y) for y in range(2026, 2032)])


def _period_picker(request, page_title, download_url_name):
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    form = PeriodForm(request.GET or None)
    month = year = None
    if form.is_valid():
        month = int(form.cleaned_data['month'])
        year = int(form.cleaned_data['year'])
    return render(request, 'Aapp/generic/period_picker.html', {
        'company': company, 'form': form, 'page_title': page_title,
        'month': month, 'year': year,
        'download_urls': ([{'label': 'Download PDF', 'name': download_url_name}] if month and year else []),
    })


# ── A) Minimum Wages Annual Return (Form V) ──────────────────────────────────

@login_required
@require_feature("min_wages")
def download_minwages_return(request, return_id):
    from Aapp.app.wage_compliance import MinimumWagesAnnualReturn
    from Aapp.app.services.wage_returns import build_minwages_return_pdf
    from Aapp.app.services.statutory_files import StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    rec = get_object_or_404(MinimumWagesAnnualReturn, return_id=return_id, company=company)
    try:
        pdf, fname = build_minwages_return_pdf(company, rec)
    except StatutoryFileError as e:
        raise Http404(str(e))
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── A) Bonus Annual Return (Form D) ──────────────────────────────────────────

@login_required
@require_feature("bonus_act")
def download_bonus_return(request, return_id):
    from Aapp.app.bonus import bonus_annual_return
    from Aapp.app.services.bonus_returns import build_bonus_return_pdf
    from Aapp.app.services.statutory_files import StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    rec = get_object_or_404(bonus_annual_return, return_id=return_id, company=company)
    try:
        pdf, fname = build_bonus_return_pdf(company, rec)
    except StatutoryFileError as e:
        raise Http404(str(e))
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── A) Bonus Set-On/Set-Off Register (Form B) ────────────────────────────────

@login_required
@require_feature("bonus_act")
def download_set_on_set_off(request, record_id):
    from Aapp.app.bonus import bonus_set_on_set_off
    from Aapp.app.services.bonus_returns import build_set_on_set_off_pdf
    from Aapp.app.services.statutory_files import StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    rec = get_object_or_404(bonus_set_on_set_off, record_id=record_id, company=company)
    try:
        pdf, fname = build_set_on_set_off_pdf(company, rec)
    except StatutoryFileError as e:
        raise Http404(str(e))
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Fines Register (Form I) ───────────────────────────────────────────────

@login_required
@require_feature("payment_of_wages")
def select_period_for_fines(request):
    return _period_picker(request, 'Fines Register (Form I) — Select Period', 'download_fines_register')


@login_required
@require_feature("payment_of_wages")
def download_fines_register(request, month, year):
    from Aapp.app.services import registers as rg
    from Aapp.app.services.statutory_files import NothingToGenerate, StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    try:
        pdf, fname = rg.build_fines_register_pdf(company, month, year)
    except NothingToGenerate as e:
        return _no_data_response(request, 'select_period_for_fines', 'Fines Register (Form I) — Select Period',
                                  month, year, str(e))
    except StatutoryFileError as e:
        raise Http404(str(e))

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Deductions Register (Form II) ─────────────────────────────────────────

@login_required
@require_feature("payment_of_wages")
def select_period_for_deductions(request):
    return _period_picker(request, 'Deductions Register (Form II) — Select Period', 'download_deductions_register_wages')


@login_required
@require_feature("payment_of_wages")
def download_deductions_register_wages(request, month, year):
    from Aapp.app.services import registers as rg
    from Aapp.app.services.statutory_files import NothingToGenerate, StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    try:
        pdf, fname = rg.build_deductions_register_pdf(company, month, year)
    except NothingToGenerate as e:
        return _no_data_response(request, 'select_period_for_deductions', 'Deductions Register (Form II) — Select Period',
                                  month, year, str(e))
    except StatutoryFileError as e:
        raise Http404(str(e))

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Overtime Register (Form IV, Shops Act) ────────────────────────────────

@login_required
@require_feature("overtime")
def select_period_for_ot_register(request):
    return _period_picker(request, 'Overtime Register (Form IV) — Select Period', 'download_ot_register')


@login_required
@require_feature("overtime")
def download_ot_register(request, month, year):
    from Aapp.app.services import registers as rg
    from Aapp.app.services.statutory_files import NothingToGenerate, StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    try:
        pdf, fname = rg.build_ot_register_pdf(company, month, year)
    except NothingToGenerate as e:
        return _no_data_response(request, 'select_period_for_ot_register', 'Overtime Register (Form IV) — Select Period',
                                  month, year, str(e))
    except StatutoryFileError as e:
        raise Http404(str(e))

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Bonus Register (Form C) ───────────────────────────────────────────────

@login_required
@require_feature("bonus_act")
def select_period_for_bonus_register(request):
    return _period_picker(request, 'Bonus Register (Form C) — Select Period', 'download_bonus_register')


@login_required
@require_feature("bonus_act")
def download_bonus_register(request, month, year):
    from Aapp.app.services.bonus_returns import build_bonus_register_pdf
    from Aapp.app.services.statutory_files import NothingToGenerate, StatutoryFileError
    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    try:
        pdf, fname = build_bonus_register_pdf(company, month, year)
    except NothingToGenerate as e:
        return _no_data_response(request, 'select_period_for_bonus_register', 'Bonus Register (Form C) — Select Period',
                                  month, year, str(e))
    except StatutoryFileError as e:
        raise Http404(str(e))

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response
