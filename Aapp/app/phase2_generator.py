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
from django import forms
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, render
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


class PeriodForm(forms.Form):
    month = forms.ChoiceField(choices=[(i, i) for i in range(1, 13)])
    year = forms.ChoiceField(choices=[(y, y) for y in range(2023, 2031)])


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
def download_minwages_return(request, return_id):
    from Aapp.app.wage_compliance import MinimumWagesAnnualReturn
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    rec = get_object_or_404(MinimumWagesAnnualReturn, return_id=return_id, company=company)

    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Return Year', str(rec.year)),
        ('Category of Work', rec.category_of_work),
        ('Employees (M/F)', f'{rec.total_employees_male} / {rec.total_employees_female}'),
    ])]
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())

    rows = [
        ['Particulars', 'Amount (₹)'],
        ['Min Wage Rate — Unskilled', INR(rec.min_wage_rate_unskilled)],
        ['Min Wage Rate — Semi-skilled', INR(rec.min_wage_rate_semiskilled)],
        ['Min Wage Rate — Skilled', INR(rec.min_wage_rate_skilled)],
        ['Total Wages Paid', INR(rec.total_wages_paid)],
        ['Total OT Hours', str(rec.total_ot_hours)],
        ['Total OT Wages', INR(rec.total_ot_wages)],
        ['Total Fines Imposed', INR(rec.total_fines_imposed)],
        ['Total Deductions', INR(rec.total_deductions)],
    ]
    t = Table(rows, colWidths=[300, 150])
    t.setStyle(TableStyle(HEADER_STYLE + [('ALIGN', (1, 0), (1, -1), 'RIGHT')]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={'title': 'Minimum Wages Act — Annual Return (Form V)',
                                                    'doc_number': rec.acknowledgement_no or f'MW-{rec.year}'})
    except Exception as e:
        logger.exception('Min wages return PDF failed for return_id=%s: %s', return_id, e)
        raise Http404('Could not generate Minimum Wages return.')

    fname = f'MinWages_Form_V_{company.company_name.replace(" ", "_")}_{rec.year}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── A) Bonus Annual Return (Form D) ──────────────────────────────────────────

@login_required
def download_bonus_return(request, return_id):
    from Aapp.app.bonus import bonus_annual_return
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    rec = get_object_or_404(bonus_annual_return, return_id=return_id, company=company)

    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Return Year', str(rec.year)),
        ('Total Employees', str(rec.total_employees)),
        ('Payment Date', rec.payment_date.strftime('%d %b %Y') if rec.payment_date else '—'),
    ])]
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())

    rows = [
        ['Particulars', 'Amount (₹)'],
        ['Total Wages (for bonus calc)', INR(rec.total_wages)],
        ['Allocable Surplus', INR(rec.allocable_surplus)],
        ['Bonus Percentage', f'{rec.bonus_percentage}%'],
        ['Total Bonus Paid', INR(rec.total_bonus_paid)],
    ]
    t = Table(rows, colWidths=[300, 150])
    t.setStyle(TableStyle(HEADER_STYLE + [('ALIGN', (1, 0), (1, -1), 'RIGHT')]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={'title': 'Payment of Bonus Act — Annual Return (Form D)',
                                                    'doc_number': rec.acknowledgement_no or f'BONUS-{rec.year}'})
    except Exception as e:
        logger.exception('Bonus return PDF failed for return_id=%s: %s', return_id, e)
        raise Http404('Could not generate Bonus annual return.')

    fname = f'Bonus_Form_D_{company.company_name.replace(" ", "_")}_{rec.year}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── A) Bonus Set-On/Set-Off Register (Form B) ────────────────────────────────

@login_required
def download_set_on_set_off(request, record_id):
    from Aapp.app.bonus import bonus_set_on_set_off
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    rec = get_object_or_404(bonus_set_on_set_off, record_id=record_id, company=company)

    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Accounting Year', str(rec.year)),
    ])]
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())

    rows = [
        ['Particulars', 'Amount (₹)'],
        ['Allocable Surplus', INR(rec.allocable_surplus)],
        ['Total Wages for Bonus', INR(rec.total_wages_for_bonus)],
        ['Minimum Bonus (8.33%)', INR(rec.min_bonus_amount)],
        ['Maximum Bonus (20%)', INR(rec.max_bonus_amount)],
        ['Bonus Paid', INR(rec.bonus_paid)],
        ['Set-On Amount', INR(rec.set_on_amount)],
        ['Set-Off Amount', INR(rec.set_off_amount)],
        ['Cumulative Set-On Balance', INR(rec.cumulative_set_on)],
    ]
    t = Table(rows, colWidths=[300, 150])
    t.setStyle(TableStyle(HEADER_STYLE + [('ALIGN', (1, 0), (1, -1), 'RIGHT')]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={'title': 'Payment of Bonus Act — Set-On/Set-Off Register (Form B)',
                                                    'doc_number': f'SETONOFF-{rec.year}'})
    except Exception as e:
        logger.exception('Set-on/off PDF failed for record_id=%s: %s', record_id, e)
        raise Http404('Could not generate Set-On/Set-Off register.')

    fname = f'Bonus_FormB_SetOnOff_{company.company_name.replace(" ", "_")}_{rec.year}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Fines Register (Form I) ───────────────────────────────────────────────

@login_required
def select_period_for_fines(request):
    return _period_picker(request, 'Fines Register (Form I) — Select Period', 'download_fines_register')


@login_required
def download_fines_register(request, month, year):
    from Aapp.app.wages import wages_fine
    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    records = (wages_fine.objects
               .filter(company=company, salary_month=month, salary_year=year)
               .select_related('employee').order_by('employee__name', 'fine_date'))
    if not records.exists():
        raise Http404(f'No fines recorded for {month}/{year}.')

    story = [kv_table([('Establishment Name', company.company_name), ('Period', f'{month}/{year}')])]
    story.append(Spacer(1, 6 * mm))

    rows = [['Employee', 'Date', 'Reason', 'Amount (₹)']]
    total = 0
    for f in records:
        rows.append([f.employee.name, f.fine_date.strftime('%d-%b-%Y'), f.fine_reason, INR(f.fine_amount)])
        total += f.fine_amount
    rows.append(['', '', 'TOTAL', INR(total)])

    t = Table(rows, colWidths=[140, 80, 200, 90])
    t.setStyle(TableStyle(HEADER_STYLE + [
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={'title': 'Fines Register (Form I)', 'doc_number': f'FINES-{month}-{year}'})
    except Exception as e:
        logger.exception('Fines register PDF failed for %s/%s: %s', month, year, e)
        raise Http404('Could not generate Fines register.')

    fname = f'Fines_Register_{company.company_name.replace(" ", "_")}_{month}_{year}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Deductions Register (Form II) ─────────────────────────────────────────

@login_required
def select_period_for_deductions(request):
    return _period_picker(request, 'Deductions Register (Form II) — Select Period', 'download_deductions_register_wages')


@login_required
def download_deductions_register_wages(request, month, year):
    from Aapp.app.wages import wages_deduction
    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    records = (wages_deduction.objects
               .filter(company=company, salary_month=month, salary_year=year)
               .select_related('employee').order_by('employee__name'))
    if not records.exists():
        raise Http404(f'No deductions recorded for {month}/{year}.')

    story = [kv_table([('Establishment Name', company.company_name), ('Period', f'{month}/{year}')])]
    story.append(Spacer(1, 6 * mm))

    rows = [['Employee', 'Type', 'Reason', 'Amount (₹)']]
    total = 0
    for d in records:
        rows.append([d.employee.name, d.get_deduction_type_display(), d.reason, INR(d.deduction_amount)])
        total += d.deduction_amount
    rows.append(['', '', 'TOTAL', INR(total)])

    t = Table(rows, colWidths=[140, 100, 180, 90])
    t.setStyle(TableStyle(HEADER_STYLE + [
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={'title': 'Deductions Register (Form II)', 'doc_number': f'DEDUCT-{month}-{year}'})
    except Exception as e:
        logger.exception('Deductions register PDF failed for %s/%s: %s', month, year, e)
        raise Http404('Could not generate Deductions register.')

    fname = f'Deductions_Register_{company.company_name.replace(" ", "_")}_{month}_{year}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Overtime Register (Form IV, Shops Act) ────────────────────────────────

@login_required
def select_period_for_ot_register(request):
    return _period_picker(request, 'Overtime Register (Form IV) — Select Period', 'download_ot_register')


@login_required
def download_ot_register(request, month, year):
    from Aapp.app.attandance import MinimumWagesOvertimeRegister, attendance
    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    records = (MinimumWagesOvertimeRegister.objects
               .filter(attendance__companyid=company,
                       attendance__salary_month=month, attendance__salary_year=year)
               .select_related('attendance').order_by('attendance__emp_code', 'ot_date'))
    if not records.exists():
        raise Http404(f'No overtime records found for {month}/{year}.')

    story = [kv_table([('Establishment Name', company.company_name), ('Period', f'{month}/{year}')])]
    story.append(Spacer(1, 6 * mm))

    rows = [['Emp Code', 'OT Date', 'Hours', 'Ordinary Rate', 'OT Rate', 'OT Wages Paid']]
    total = 0
    for r in records:
        rows.append([r.attendance.emp_code, r.ot_date.strftime('%d-%b-%Y'),
                     str(r.overtime_hours), INR(r.ordinary_rate), INR(r.ot_rate), INR(r.ot_wages_paid)])
        total += r.ot_wages_paid
    rows.append(['', '', '', '', 'TOTAL', INR(total)])

    t = Table(rows, colWidths=[80, 80, 60, 90, 90, 100])
    t.setStyle(TableStyle(HEADER_STYLE + [
        ('ALIGN', (2, 0), (5, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={'title': 'Overtime Register (Form IV)', 'doc_number': f'OT-{month}-{year}'})
    except Exception as e:
        logger.exception('OT register PDF failed for %s/%s: %s', month, year, e)
        raise Http404('Could not generate Overtime register.')

    fname = f'Overtime_Register_{company.company_name.replace(" ", "_")}_{month}_{year}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Bonus Register (Form C) ───────────────────────────────────────────────

@login_required
def select_period_for_bonus_register(request):
    return _period_picker(request, 'Bonus Register (Form C) — Select Period', 'download_bonus_register')


@login_required
def download_bonus_register(request, month, year):
    from Aapp.app.bonus import bonus_record
    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    records = (bonus_record.objects
               .filter(company=company, salary_month=month, salary_year=year)
               .select_related('employee').order_by('employee__name'))
    if not records.exists():
        raise Http404(f'No bonus records found for {month}/{year}.')

    story = [kv_table([('Establishment Name', company.company_name), ('Period', f'{month}/{year}')])]
    story.append(Spacer(1, 6 * mm))

    rows = [['Employee', 'Basic Bonus', 'Perf. Bonus', 'Festival Bonus', 'Other', 'Total', 'Paid']]
    total = 0
    for b in records:
        rows.append([b.employee.name, INR(b.basic_bonus), INR(b.performance_bonus),
                     INR(b.festival_bonus), INR(b.other_bonus), INR(b.total_bonus),
                     'Yes' if b.is_paid else 'No'])
        total += b.total_bonus
    rows.append(['', '', '', '', 'TOTAL', INR(total), ''])

    t = Table(rows, colWidths=[110, 75, 75, 80, 65, 80, 45])
    t.setStyle(TableStyle(HEADER_STYLE + [
        ('ALIGN', (1, 0), (5, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={'title': 'Bonus Register (Form C)', 'doc_number': f'BONUS-REG-{month}-{year}'})
    except Exception as e:
        logger.exception('Bonus register PDF failed for %s/%s: %s', month, year, e)
        raise Http404('Could not generate Bonus register.')

    fname = f'Bonus_Register_{company.company_name.replace(" ", "_")}_{month}_{year}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response
