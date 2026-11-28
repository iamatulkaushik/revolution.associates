"""D4 - month-end checklist for a DIRECT company. Read-only: reads existing data, writes nothing.

build_checklist() returns a list of items {key, title, status, detail, names, link};
status is 'ok', 'warn' or 'info'. It is shown on its own page and as the last step before
Finalize. Warnings never block finalizing: the owner reads them and decides.
"""
import calendar
from datetime import date
from decimal import Decimal

from django.shortcuts import render
from django.urls import NoReverseMatch, reverse

from Aapp.app.attandance import attendance
from Aapp.app.employee import employee
from Aapp.app.epf_esi import EpfMonthlyEcr
from Aapp.app.labour_welfare import LabourWelfareFundContribution
from Aapp.app.loans_advances import Advance, Loan
from Aapp.app.salary_processing import YEAR_CHOICES, salary_processing, salary_slip
from Aapp.app.statutory_gates import get_company_gates, lwf_allowed
from Capp.direct.guards import direct_perm

SHOW = 8                                   # names listed per item
# Screens owned by the entry track; no link is shown until the name exists.
ENTRY_LINKS = {'attendance': 'capp_ent_attendance', 'loans': 'capp_ent_loans'}


def _link(name, *args):
    try:
        return reverse(name, args=args)
    except NoReverseMatch:
        return None


def _item(key, title, status, detail, names=None, link=None):
    names = names or []
    return {'key': key, 'title': title, 'status': status, 'detail': detail,
            'names': names[:SHOW], 'more': max(len(names) - SHOW, 0), 'link': link}


def _due_day(month, year, day):
    """Date `day` of the month after the salary month."""
    return date(year + (month == 12), month % 12 + 1, day)


def _fmt(d):
    return d.strftime('%d %b %Y')


def build_checklist(company, month, year):
    g = get_company_gates(company)
    staff = list(employee.objects.filter(CompanyID=company, is_working=True).order_by('employeecode'))
    label = f'{calendar.month_name[month]} {year}'
    items = []

    # 1. Attendance
    have = set(attendance.objects.filter(companyid=company, salary_month=month, salary_year=year)
               .values_list('employee_id_id', flat=True))
    missing = [f'{e.employeecode} {e.name}' for e in staff if e.pk not in have]
    items.append(_item(
        'attendance', 'Attendance entered',
        'ok' if not missing else 'warn',
        (f'All {len(staff)} working employees have attendance for {label}.' if not missing else
         f'{len(missing)} of {len(staff)} working employees have no attendance for {label}.'),
        missing, _link(ENTRY_LINKS['attendance'])))

    # 2. Batch and slips
    batch = salary_processing.objects.filter(company_id=company, month=month, year=year).first()
    if not batch:
        items.append(_item('batch', 'Payroll batch', 'warn', f'No batch for {label} yet.',
                           link=_link('capp_dir_payroll')))
        slips = []
    else:
        slips = list(salary_slip.objects.filter(processing_id=batch).select_related('employee_id'))
        slipped = {s.employee_id_id for s in slips}
        no_slip = [f'{e.employeecode} {e.name}' for e in staff if e.pk not in slipped]
        items.append(_item(
            'batch', 'Payroll batch', 'ok' if batch.status != 'DRAFT' and not no_slip else 'warn',
            f'Status {batch.status}: {batch.total_employees} employees, net pay {batch.total_net}.'
            + (f' {len(no_slip)} working employees have no salary slip.' if no_slip else ''),
            no_slip, _link('capp_dir_payroll_detail', batch.pk)))

    # 3. Loans and advances applied
    slip_by_emp = {s.employee_id_id: s for s in slips}
    differs = []
    due_rows = 0
    for model, field in ((Loan, 'loan_deduction'), (Advance, 'advance_deduction')):
        due = {}
        for rec in model.objects.filter(company=company, status='active').select_related('employee'):
            amt = rec.get_due_deduction_for_month(month, year)
            if amt:
                due_rows += 1
                due[rec.employee_id] = due.get(rec.employee_id, Decimal('0')) + amt
        for emp_id, amt in due.items():
            slip = slip_by_emp.get(emp_id)
            got = getattr(slip, field, Decimal('0')) if slip else Decimal('0')
            if got != amt:
                e = next((x for x in staff if x.pk == emp_id), None)
                who = f'{e.employeecode} {e.name}' if e else f'Employee {emp_id}'
                differs.append(f'{who}: {field.split("_")[0]} due {amt}, deducted {got}')
    items.append(_item(
        'loans', 'Loans and advances applied',
        'ok' if not differs else 'warn',
        (f'{due_rows} instalment(s) due this month; all match the salary slips.' if due_rows and not differs else
         'No loan or advance instalment is due this month.' if not due_rows else
         f'{len(differs)} deduction(s) differ from the schedule. Process again if a loan was added or changed.'),
        differs, _link(ENTRY_LINKS['loans'])))

    # 4. Registrations vs employee numbers (fail-closed visibility)
    notes = []
    if not g['epf'] and any((e.uan_number or '').strip() for e in staff):
        notes.append('Employees have a UAN but the company has no EPF number: no EPF is deducted.')
    if not g['esi'] and any((e.esic_number or '').strip() for e in staff):
        notes.append('Employees have an ESIC number but the company has no ESIC number: no ESI is deducted.')
    on = [n for n, ok in (('EPF', g['epf']), ('ESIC', g['esi']), ('LWF', lwf_allowed(g)),
                          ('PT', g['pt'])) if ok]
    items.append(_item(
        'gates', 'Statutory registrations', 'ok' if not notes else 'warn',
        'Switched on: ' + (', '.join(on) if on else 'none') + '.', notes, _link('capp_dir_statutory')))

    # 5. Challans
    final = bool(batch and batch.status in ('APPROVED', 'PAID'))
    todo = []
    if g['epf'] and not EpfMonthlyEcr.objects.filter(
            company=company, salary_month=month, salary_year=year).exists():
        todo.append('EPF ECR is not generated yet.')
    if lwf_allowed(g) and not LabourWelfareFundContribution.objects.filter(
            company=company, year=year,
            contribution_period='jan_jun' if month <= 6 else 'jul_dec').exists():
        todo.append('LWF record for this half-year is not created yet.')
    if not final:
        items.append(_item('challans', 'Challans and returns', 'info',
                           'Available after payroll is finalized.', link=_link('capp_dir_challans')))
    else:
        items.append(_item('challans', 'Challans and returns', 'ok' if not todo else 'warn',
                           'All offered files are ready to download.' if not todo else
                           'Some files still need to be generated.', todo,
                           f"{reverse('capp_dir_challans')}?month={month}&year={year}"))

    # 6. Bank file
    items.append(_item('bank', 'Bank payment file', 'info',
                       'Download it after finalizing, once the figures are confirmed.',
                       link=_link('capp_bank_file')))

    # 7. Due dates
    dues = []
    if g['epf']:
        dues.append(f'EPF ECR and challan: {_fmt(_due_day(month, year, 15))}')
    if g['esi']:
        dues.append(f'ESIC contribution: {_fmt(_due_day(month, year, 15))}')
    if lwf_allowed(g):
        dues.append('LWF: ' + (f'31 Jul {year}' if month <= 6 else f'31 Jan {year + 1}'))
    items.append(_item('due', 'Due dates', 'info',
                       'Statutory payments for this month.' if dues else 'No statutory payment is due.', dues))
    return items


@direct_perm('payroll.process')
def capp_dir_checklist(request):
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
    items = build_checklist(company, month, year)
    return render(request, 'Capp/direct/checklist.html', {
        'items': items, 'warnings': sum(i['status'] == 'warn' for i in items),
        'month': month, 'year': year, 'month_name': calendar.month_name[month],
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)], 'years': YEAR_CHOICES,
    })
