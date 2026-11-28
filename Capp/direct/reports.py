"""D5a - statutory reports a DIRECT company can build from its own salary data.

Wages-act reports (grand total, wages register, Form X, wages slips) come from the finalized
month's salary slips; Form 24Q prep sheet needs the company TAN. The builders are Aapp's.
Registers that depend on separately entered records (fines, deductions, overtime, nominations,
leave with wages, ...) are D5b. Tenant-scoped, audited, DIRECT-only.
"""
import calendar
import io
from datetime import date

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from Aapp.app.salary_processing import YEAR_CHOICES, salary_processing, salary_slip
from Aapp.app.services import reports as rp
from Aapp.app.services.statutory_files import StatutoryFileError
from Aapp.app.statutory.wages_act import (
    form_x_wages_register_pdf, grand_total_pdf, wages_register_pdf, wages_slip_pdf)
from Aapp.app.statutory_gates import get_company_gates
from Capp.audit import log_action
from Capp.direct.guards import direct_perm

PERM = 'challan.download'
FINAL = ('APPROVED', 'PAID')
KINDS = {
    'grand-total': ('Grand total of wages', 'Grand_Total'),
    'wages-register': ('Wages register', 'Wages_Register'),
    'form-x': ('Form X wages register (Minimum Wages)', 'Form_X'),
    'wages-slips': ('Wages slips, all employees', 'Wages_Slips'),
}


def _final_batch(company, month, year):
    return salary_processing.objects.filter(
        company_id=company, month=month, year=year, status__in=FINAL).first()


def _back(month, year):
    return redirect(f"{reverse('capp_dir_reports')}?month={month}&year={year}")


def _pdf(request, content, name, what, month, year):
    log_action(request, 'report.download', None, f'{what} {month}/{year}')
    r = HttpResponse(content, content_type='application/pdf')
    r['Content-Disposition'] = f'attachment; filename="{name}"'
    return r


def _bulk_slips_pdf(company, slips):
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    for slip in slips:
        for page in PdfReader(io.BytesIO(wages_slip_pdf(company, slip))).pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _fy_choices(today):
    start = today.year if today.month >= 4 else today.year - 1
    return [f'{y}-{str(y + 1)[2:]}' for y in (start, start - 1, start - 2)]


@direct_perm(PERM)
def capp_dir_reports(request):
    company = request.owned_company
    today = date.today()
    pm = today.month - 1 or 12
    try:
        month = int(request.GET.get('month', pm))
        year = int(request.GET.get('year', today.year if today.month > 1 else today.year - 1))
    except ValueError:
        month, year = pm, today.year
    if not 1 <= month <= 12:
        month = pm
    g = get_company_gates(company)
    return render(request, 'Capp/direct/reports.html', {
        'finalized': bool(_final_batch(company, month, year)),
        'kinds': [(k, v[0], reverse('capp_dir_report', args=[year, month, k])) for k, v in KINDS.items()],
        'tan_on': g['income_tax'], 'fys': [(f, reverse('capp_dir_form24q', args=[f])) for f in _fy_choices(today)],
        'month': month, 'year': year, 'month_name': calendar.month_name[month],
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)], 'years': YEAR_CHOICES,
    })


@direct_perm(PERM)
def capp_dir_report(request, year, month, kind):
    company = request.owned_company
    if kind not in KINDS or not 1 <= month <= 12:
        raise Http404('Unknown report.')
    batch = _final_batch(company, month, year)
    if not batch:
        messages.warning(request, 'Finalize the payroll for this month first.')
        return _back(month, year)
    slips = list(salary_slip.objects.filter(processing_id=batch)
                 .select_related('employee_id', 'designation_id')
                 .order_by('employee_id__employeecode'))
    if not slips:
        messages.warning(request, 'No salary slips for this month.')
        return _back(month, year)
    if kind == 'grand-total':
        pdf = grand_total_pdf(company, slips, month, year)
    elif kind == 'wages-register':
        pdf = wages_register_pdf(company, slips, month, year)
    elif kind == 'form-x':
        pdf = form_x_wages_register_pdf(company, slips, month, year)
    else:
        pdf = _bulk_slips_pdf(company, slips)
    label, prefix = KINDS[kind]
    return _pdf(request, pdf, f'{prefix}_{month}_{year}.pdf', label, month, year)


@direct_perm(PERM)
def capp_dir_form24q(request, financial_year):
    company = request.owned_company
    if financial_year not in _fy_choices(date.today()):
        raise Http404('Unknown financial year.')
    if not get_company_gates(company)['income_tax']:
        messages.error(request, 'Income tax is not switched on: the company TAN is missing. '
                                'Add it under Company details.')
        return redirect('capp_dir_reports')
    try:
        content, fname = rp.build_form24q_xlsx(company, financial_year)
    except StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect('capp_dir_reports')
    log_action(request, 'report.download', None, f'Form 24Q {financial_year}')
    r = HttpResponse(content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    r['Content-Disposition'] = f'attachment; filename="{fname}"'
    return r
