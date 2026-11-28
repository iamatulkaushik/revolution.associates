"""D3 - challans and returns for a DIRECT company, one page per month.

Files are offered only when (a) the company has the registration (EPF/ESIC/LWF/PT number on
file, via get_company_gates) and (b) the month's payroll is finalized (APPROVED or PAID).
The file builders are the Aapp ones (Aapp/app/services/statutory_files.py, pt_schedule_pdf).
ESIC rounds up in the challan file only. Every query is scoped to request.owned_company.
"""
import calendar
from datetime import date

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from Aapp.app.employee import employee
from Aapp.app.epf_esi import EpfMonthlyEcr
from Aapp.app.labour_welfare import LabourWelfareFundContribution
from Aapp.app.pt_schedule import pt_schedule_pdf
from Aapp.app.salary_processing import YEAR_CHOICES, salary_processing
from Aapp.app.services import statutory_files as sf
from Aapp.app.statutory_gates import get_company_gates, lwf_allowed
from Capp.audit import log_action
from Capp.direct.guards import direct_perm

PERM = 'challan.download'
FINAL = ('APPROVED', 'PAID')


def _month_year(month, year):
    if not 1 <= month <= 12:
        raise Http404('Invalid month.')
    return month, year


def _gate_ok(company, scheme):
    g = get_company_gates(company)
    return {'epf': g['epf'], 'esi': g['esi'], 'pt': g['pt'], 'lwf': lwf_allowed(g)}[scheme]


def _finalized(company, month, year):
    return salary_processing.objects.filter(
        company_id=company, month=month, year=year, status__in=FINAL).exists()


def _back(month, year):
    return redirect(f"{reverse('capp_dir_challans')}?month={month}&year={year}")


def _refuse(request, company, scheme, month, year, label):
    """None when allowed, else a redirect with the reason."""
    if not _gate_ok(company, scheme):
        messages.error(request, f'{label} is not switched on: the registration number is missing '
                                'under Statutory setup.')
        return _back(month, year)
    if not _finalized(company, month, year):
        messages.warning(request, 'Finalize the payroll for this month first.')
        return _back(month, year)
    return None


def _file(request, content, fname, ctype, what, month, year):
    log_action(request, 'challan.download', None, f'{what} {month}/{year}')
    r = HttpResponse(content, content_type=ctype)
    r['Content-Disposition'] = f'attachment; filename="{fname}"'
    return r


def _lwf_period(month, year):
    """(period code, due date) for the half-year holding this month."""
    if month <= 6:
        return 'jan_jun', date(year, 7, 31)
    return 'jul_dec', date(year + 1, 1, 31)


@direct_perm(PERM)
def capp_dir_challans(request):
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

    finalized = _finalized(company, month, year)
    g = get_company_gates(company)
    ecr = EpfMonthlyEcr.objects.filter(
        company=company, salary_month=month, salary_year=year).first()
    period, _due = _lwf_period(month, year)
    lwf = LabourWelfareFundContribution.objects.filter(
        company=company, year=year, contribution_period=period).first()
    args = [year, month]

    schemes = [
        {'title': 'EPF', 'on': g['epf'], 'off_note': 'No EPF number on file. No ECR or challan is offered.',
         'actions': ([{'label': 'ECR text file', 'url': reverse('capp_dir_ecr_text', args=args)},
                      {'label': 'EPF challan (PDF)', 'url': reverse('capp_dir_epf_challan', args=args)}]
                     if ecr else []),
         'create': None if ecr else {'label': 'Generate ECR from salary', 'url': reverse('capp_dir_ecr_create')}},
        {'title': 'ESIC', 'on': g['esi'], 'off_note': 'No ESIC number on file. No ESI file is offered.',
         'actions': [{'label': 'ESI challan (PDF)', 'url': reverse('capp_dir_esi_challan', args=args)},
                     {'label': 'ESI upload file (Excel)', 'url': reverse('capp_dir_esi_upload', args=args)}],
         'create': None},
        {'title': 'Labour Welfare Fund (half-yearly)', 'on': lwf_allowed(g),
         'off_note': 'LWF needs both the Labour and the Shop Act numbers on file.',
         'actions': ([{'label': 'LWF challan (PDF)', 'url': reverse('capp_dir_lwf_challan', args=[lwf.pk])}]
                     if lwf else []),
         'create': None if lwf else {'label': 'Create LWF record for this half-year',
                                     'url': reverse('capp_dir_lwf_create')}},
        {'title': 'Professional Tax', 'on': g['pt'], 'off_note': 'No PT number on file. No PT schedule is offered.',
         'actions': [{'label': 'PT schedule (PDF)', 'url': reverse('capp_dir_pt_schedule', args=args)}],
         'create': None},
    ]
    return render(request, 'Capp/direct/challans.html', {
        'schemes': schemes, 'finalized': finalized,
        'month': month, 'year': year, 'month_name': calendar.month_name[month],
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)], 'years': YEAR_CHOICES,
    })


# -- EPF ------------------------------------------------------------------------

@direct_perm(PERM)
@require_POST
def capp_dir_ecr_create(request):
    company = request.owned_company
    try:
        month, year = _month_year(int(request.POST['month']), int(request.POST['year']))
    except (KeyError, ValueError):
        raise Http404('Invalid period.')
    refused = _refuse(request, company, 'epf', month, year, 'EPF')
    if refused:
        return refused
    try:
        ecr = sf.create_epf_ecr(company, month, year, request.user)
    except sf.StatutoryFileError as e:
        messages.error(request, str(e))
        return _back(month, year)
    log_action(request, 'challan.ecr_create', ecr, f'{month}/{year}')
    messages.success(request, f'EPF ECR for {month}/{year} generated from the salary sheet.')
    return _back(month, year)


def _ecr(company, year, month):
    _month_year(month, year)
    return get_object_or_404(EpfMonthlyEcr, company=company, salary_month=month, salary_year=year)


@direct_perm(PERM)
def capp_dir_ecr_text(request, year, month):
    company = request.owned_company
    refused = _refuse(request, company, 'epf', month, year, 'EPF')
    if refused:
        return refused
    try:
        content, fname, _skipped = sf.build_ecr_text(company, _ecr(company, year, month))
    except sf.StatutoryFileError as e:
        messages.error(request, str(e))
        return _back(month, year)
    return _file(request, content, fname, 'text/plain', 'ECR', month, year)


@direct_perm(PERM)
def capp_dir_epf_challan(request, year, month):
    company = request.owned_company
    refused = _refuse(request, company, 'epf', month, year, 'EPF')
    if refused:
        return refused
    try:
        pdf, fname = sf.build_epf_challan_pdf(company, _ecr(company, year, month))
    except sf.StatutoryFileError as e:
        messages.error(request, str(e))
        return _back(month, year)
    return _file(request, pdf, fname, 'application/pdf', 'EPF challan', month, year)


# -- ESI ------------------------------------------------------------------------

@direct_perm(PERM)
def capp_dir_esi_challan(request, year, month):
    company = request.owned_company
    _month_year(month, year)
    refused = _refuse(request, company, 'esi', month, year, 'ESIC')
    if refused:
        return refused
    try:
        pdf, fname = sf.build_esi_challan_pdf(company, month, year)
    except sf.StatutoryFileError as e:
        messages.error(request, str(e))
        return _back(month, year)
    return _file(request, pdf, fname, 'application/pdf', 'ESI challan', month, year)


@direct_perm(PERM)
def capp_dir_esi_upload(request, year, month):
    company = request.owned_company
    _month_year(month, year)
    refused = _refuse(request, company, 'esi', month, year, 'ESIC')
    if refused:
        return refused
    try:
        content, fname = sf.build_esi_upload_xlsx(company, month, year)
    except sf.StatutoryFileError as e:
        messages.error(request, str(e))
        return _back(month, year)
    return _file(request, content, fname,
                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                 'ESI upload', month, year)


# -- LWF ------------------------------------------------------------------------

@direct_perm(PERM)
@require_POST
def capp_dir_lwf_create(request):
    company = request.owned_company
    try:
        month, year = _month_year(int(request.POST['month']), int(request.POST['year']))
    except (KeyError, ValueError):
        raise Http404('Invalid period.')
    refused = _refuse(request, company, 'lwf', month, year, 'LWF')
    if refused:
        return refused
    period, due = _lwf_period(month, year)
    if LabourWelfareFundContribution.objects.filter(
            company=company, year=year, contribution_period=period).exists():
        messages.info(request, 'An LWF record already exists for this half-year.')
        return _back(month, year)
    count = employee.objects.filter(CompanyID=company, is_working=True).count()
    ee, er = LabourWelfareFundContribution.calculate_for_employee_count(count)
    rec = LabourWelfareFundContribution.objects.create(
        company=company, year=year, contribution_period=period, total_employees=count,
        employee_contribution=ee, employer_contribution=er, due_date=due,
        created_by=request.user)
    log_action(request, 'challan.lwf_create', rec, f'{period} {year}')
    messages.success(request, 'LWF record created from the current headcount.')
    return _back(month, year)


@direct_perm(PERM)
def capp_dir_lwf_challan(request, lwf_id):
    company = request.owned_company
    rec = get_object_or_404(LabourWelfareFundContribution, pk=lwf_id, company=company)
    if not lwf_allowed(get_company_gates(company)):
        messages.error(request, 'LWF is not switched on: Labour and Shop Act numbers are needed.')
        return redirect('capp_dir_challans')
    try:
        pdf, fname = sf.build_lwf_challan_pdf(company, rec)
    except sf.StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect('capp_dir_challans')
    return _file(request, pdf, fname, 'application/pdf', 'LWF challan', rec.year, rec.contribution_period)


# -- PT -------------------------------------------------------------------------

@direct_perm(PERM)
def capp_dir_pt_schedule(request, year, month):
    company = request.owned_company
    _month_year(month, year)
    refused = _refuse(request, company, 'pt', month, year, 'Professional Tax')
    if refused:
        return refused
    pdf = pt_schedule_pdf(company, month, year)
    return _file(request, pdf, f'PT_Schedule_{company.company_name.replace(" ", "_")}_{month}_{year}.pdf',
                 'application/pdf', 'PT schedule', month, year)
