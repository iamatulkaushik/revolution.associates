"""
Capp/views.py
=============
Company Owner portal views.

All views are read-only — owners can VIEW and DOWNLOAD, not create/edit.
Editing is reserved for the Associate (Aapp) who manages the company.
"""

import logging
from functools import wraps
from datetime import date

from django import forms
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.debug import sensitive_post_parameters

logger = logging.getLogger(__name__)


# ── Auth decorator ────────────────────────────────────────────────────────────

def owner_required(view_func):
    """Require an active CompanyOwnerProfile. Redirect to Capp login if not."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('capp_login')
        if not getattr(request, 'owner_profile', None):
            messages.error(request, 'Your account does not have owner access.')
            return redirect('capp_login')
        if not request.owner_profile.can_access_system():
            messages.error(request, 'Your account is inactive. Contact your associate.')
            return redirect('capp_login')
        return view_func(request, *args, **kwargs)
    return _wrapped


def access_required(flag):
    """Decorator: check a specific access flag from owner_profile."""
    def decorator(view_func):
        @wraps(view_func)
        @owner_required
        def _wrapped(request, *args, **kwargs):
            if not getattr(request.owner_profile, f'can_view_{flag}', False):
                messages.error(request, 'You do not have access to this section.')
                return redirect('capp_dashboard')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


# ── Login / Logout ────────────────────────────────────────────────────────────

class OwnerLoginForm(AuthenticationForm):
    username = forms.CharField(label='Username', widget=forms.TextInput(attrs={'autofocus': True}))
    password = forms.CharField(label='Password', widget=forms.PasswordInput)


@sensitive_post_parameters('password')
def capp_login(request):
    if request.user.is_authenticated and getattr(request, 'owner_profile', None):
        return redirect('capp_dashboard')

    if request.method == 'POST':
        form = OwnerLoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            try:
                from Capp.models import CompanyOwnerProfile
                profile = CompanyOwnerProfile.objects.get(user=user, is_active=True)
            except CompanyOwnerProfile.DoesNotExist:
                messages.error(request, 'No owner account found for these credentials.')
                return render(request, 'Capp/login.html', {'form': form})

            auth_login(request, user)
            # Record IP
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
            profile.last_login_ip = ip.split(',')[0].strip() if ip else None
            profile.save(update_fields=['last_login_ip'])
            logger.info("Owner login: user='%s' company='%s'", user.username, profile.company.company_name)
            return redirect('capp_dashboard')
    else:
        form = OwnerLoginForm()

    return render(request, 'Capp/login.html', {'form': form})


def capp_logout(request):
    username = request.user.username if request.user.is_authenticated else 'unknown'
    auth_logout(request)
    logger.info("Owner logout: user='%s'", username)
    return redirect('capp_login')


# ── Dashboard ─────────────────────────────────────────────────────────────────

@owner_required
def capp_dashboard(request):
    company = request.owned_company
    ctx = {'company': company}

    try:
        from Aapp.app.employee import employee
        ctx['total_employees']  = employee.objects.filter(CompanyID=company, is_working=True).count()
        ctx['total_all_emp']    = employee.objects.filter(CompanyID=company).count()
    except Exception:
        ctx['total_employees'] = ctx['total_all_emp'] = 0

    try:
        from Aapp.app.wages import wages_record
        today = date.today()
        ctx['wages_this_month'] = wages_record.objects.filter(
            company=company, salary_month=today.month, salary_year=today.year
        ).count()
    except Exception:
        ctx['wages_this_month'] = 0

    try:
        from Aapp.app.compliance_tracker import StatutoryReturnTracker
        from django.utils import timezone
        ctx['overdue_count'] = StatutoryReturnTracker.objects.filter(
            company=company, filing_status='pending', due_date__lt=timezone.now().date()
        ).count()
        ctx['pending_count'] = StatutoryReturnTracker.objects.filter(
            company=company, filing_status='pending'
        ).count()
    except Exception:
        ctx['overdue_count'] = ctx['pending_count'] = 0

    try:
        from Aapp.app.epf_esi import EpfMonthlyEcr
        today = date.today()
        ctx['last_ecr'] = EpfMonthlyEcr.objects.filter(
            company=company
        ).order_by('-salary_year', '-salary_month').first()
    except Exception:
        ctx['last_ecr'] = None

    return render(request, 'Capp/dashboard.html', ctx)


# ── Employee views (read-only) ────────────────────────────────────────────────

@access_required('employees')
def capp_employee_list(request):
    from Aapp.app.employee import employee
    company = request.owned_company
    employees = employee.objects.filter(CompanyID=company).order_by('employeecode')

    # Optional filters
    q = request.GET.get('q', '').strip()
    if q:
        employees = employees.filter(name__icontains=q) | employees.filter(employeecode__icontains=q)

    status = request.GET.get('status', 'active')
    if status == 'active':
        employees = employees.filter(is_working=True)
    elif status == 'inactive':
        employees = employees.filter(is_working=False)

    return render(request, 'Capp/employees/list.html', {
        'employees': employees,
        'q': q, 'status': status,
        'company': request.owned_company,
    })


@access_required('employees')
def capp_employee_detail(request, pk):
    from Aapp.app.employee import employee
    emp = get_object_or_404(employee, employeeid=pk, CompanyID=request.owned_company)
    return render(request, 'Capp/employees/detail.html', {'emp': emp})


# ── Attendance views (read-only) ──────────────────────────────────────────────

@access_required('attendance')
def capp_attendance_list(request):
    from Aapp.app.attandance import attendance
    company = request.owned_company
    month = int(request.GET.get('month', date.today().month))
    year  = int(request.GET.get('year',  date.today().year))
    records = attendance.objects.filter(
        companyid=company, salary_month=month, salary_year=year
    ).select_related('employee_id').order_by('employee_id__employeecode')

    return render(request, 'Capp/generic/list.html', {
        'page_title':    f'Attendance Register — {month}/{year}',
        'company':       company,
        'columns':       ['Emp Code', 'Name', 'Working Days', 'OT Hours', 'Leave Days'],
        'rows': [{
            'cells': [
                r.employee_id.employeecode if r.employee_id else r.emp_code,
                r.employee_id.name if r.employee_id else '—',
                getattr(r, 'working_days', '—'),
                getattr(r, 'overtime_hours', '—'),
                getattr(r, 'leave_days', '—'),
            ],
            'actions': [],
        } for r in records],
        'empty_message': 'No attendance records for this period.',
        'extra_links': [
            {'label': f'← Previous Month', 'url': f'?month={month-1 if month>1 else 12}&year={year if month>1 else year-1}'},
            {'label': f'Next Month →',      'url': f'?month={month+1 if month<12 else 1}&year={year if month<12 else year+1}'},
        ],
    })


@access_required('attendance')
def capp_overtime_list(request):
    from Aapp.app.shops_act import overtime_register
    company = request.owned_company
    month = int(request.GET.get('month', date.today().month))
    year  = int(request.GET.get('year',  date.today().year))
    records = overtime_register.objects.filter(
        company=company, salary_month=month, salary_year=year
    ).select_related('employee')

    return render(request, 'Capp/generic/list.html', {
        'page_title': f'Overtime Register — {month}/{year}',
        'company':    company,
        'columns':    ['Employee', 'OT Date', 'OT Hours', 'Reason', 'OT Wages'],
        'rows': [{
            'cells': [r.employee.name, r.ot_date, r.ot_hours, r.ot_reason or '—', r.ot_wages],
            'actions': [],
        } for r in records],
        'empty_message': 'No overtime records for this period.',
    })


# ── Wages views ───────────────────────────────────────────────────────────────

@access_required('wages')
def capp_wages_list(request):
    from Aapp.app.wages import wages_record
    company = request.owned_company
    month = int(request.GET.get('month', date.today().month))
    year  = int(request.GET.get('year',  date.today().year))
    records = wages_record.objects.filter(
        company=company, salary_month=month, salary_year=year
    ).select_related('employee').order_by('employee__employeecode')

    total_gross = sum(float(r.gross_wages or 0) for r in records)
    total_net   = sum(float(r.net_wages   or 0) for r in records)

    return render(request, 'Capp/wages/list.html', {
        'records':     records,
        'month':       month,
        'year':        year,
        'months':      list(range(1, 13)),
        'total_gross': total_gross,
        'total_net':   total_net,
        'company':     company,
    })


@access_required('wages')
def capp_salary_slip_select(request):
    """Month/year selector before downloading salary slips."""
    return render(request, 'Capp/wages/select_period.html', {
        'action_label': 'Download Salary Slip',
        'action_name':  'capp_salary_slip_download',
        'company':      request.owned_company,
    })


@access_required('wages')
def capp_salary_slip_download(request, wages_id):
    from Aapp.app.wages import wages_record
    from Aapp.app.salary_pdf import salary_slip_pdf
    rec = get_object_or_404(wages_record, wages_id=wages_id, company=request.owned_company)
    if not request.owner_profile.can_download_pdf:
        raise Http404('PDF download not permitted.')
    pdf = salary_slip_pdf(rec)
    fname = f'Slip_{rec.employee.employeecode}_{rec.salary_month}_{rec.salary_year}.pdf'
    return HttpResponse(pdf, content_type='application/pdf',
                        headers={'Content-Disposition': f'attachment; filename="{fname}"'})


@access_required('wages')
def capp_salary_sheet(request):
    from Aapp.app.salary_pdf import salary_sheet_pdf
    company = request.owned_company
    month = int(request.GET.get('month', date.today().month))
    year  = int(request.GET.get('year',  date.today().year))
    if not request.owner_profile.can_download_pdf:
        raise Http404('PDF download not permitted.')
    pdf   = salary_sheet_pdf(company, month, year)
    fname = f'SalarySheet_{month}_{year}.pdf'
    return HttpResponse(pdf, content_type='application/pdf',
                        headers={'Content-Disposition': f'attachment; filename="{fname}"'})


@access_required('wages')
def capp_salary_abstract(request):
    from Aapp.app.salary_pdf import salary_abstract_pdf
    company = request.owned_company
    month = int(request.GET.get('month', date.today().month))
    year  = int(request.GET.get('year',  date.today().year))
    if not request.owner_profile.can_download_pdf:
        raise Http404('PDF download not permitted.')
    pdf   = salary_abstract_pdf(company, month, year)
    fname = f'SalaryAbstract_{month}_{year}.pdf'
    return HttpResponse(pdf, content_type='application/pdf',
                        headers={'Content-Disposition': f'attachment; filename="{fname}"'})


# ── Statutory views (read-only) ───────────────────────────────────────────────

@access_required('statutory')
def capp_epf_ecr(request):
    from Aapp.app.epf_esi import EpfMonthlyEcr
    records = EpfMonthlyEcr.objects.filter(company=request.owned_company).order_by('-salary_year', '-salary_month')
    return render(request, 'Capp/generic/list.html', {
        'page_title': 'EPF Monthly ECR',
        'company':    request.owned_company,
        'columns':    ['Month/Year', 'Members', 'EPF Wages', 'Total Contribution', 'TRRN', 'Status'],
        'rows': [{
            'cells': [f'{r.salary_month}/{r.salary_year}', r.total_members,
                      r.total_epf_wages, r.total_contribution,
                      r.trrn or '—', r.get_filing_status_display()],
            'actions': [],
        } for r in records],
        'empty_message': 'No EPF ECR records found.',
    })


@access_required('statutory')
def capp_esi_returns(request):
    from Aapp.app.epf_esi import EsiContributionReturn
    records = EsiContributionReturn.objects.filter(company=request.owned_company).order_by('-year')
    return render(request, 'Capp/generic/list.html', {
        'page_title': 'ESI Contribution Returns',
        'company':    request.owned_company,
        'columns':    ['Year', 'Period', 'Covered Employees', 'Total Wages', 'Contribution', 'Status'],
        'rows': [{
            'cells': [r.year, r.get_contribution_period_display(), r.total_covered_employees,
                      r.total_wages, r.total_contribution, r.get_filing_status_display()],
            'actions': [],
        } for r in records],
        'empty_message': 'No ESI returns found.',
    })


@access_required('statutory')
def capp_gratuity(request):
    from Aapp.app.gratuity import gratuity_record
    records = gratuity_record.objects.filter(company=request.owned_company).select_related('employee')
    return render(request, 'Capp/generic/list.html', {
        'page_title': 'Gratuity Register',
        'company':    request.owned_company,
        'columns':    ['Employee', 'Date of Joining', 'Date of Leaving', 'Years', 'Amount', 'Status'],
        'rows': [{
            'cells': [r.employee.name, r.date_of_joining, r.date_of_leaving,
                      r.years_of_service, r.gratuity_amount,
                      'Paid' if r.is_paid else 'Pending'],
            'actions': [],
        } for r in records],
        'empty_message': 'No gratuity records found.',
    })


@access_required('statutory')
def capp_bonus(request):
    from Aapp.app.bonus import bonus_record
    records = bonus_record.objects.filter(company=request.owned_company).select_related('employee')
    return render(request, 'Capp/generic/list.html', {
        'page_title': 'Bonus Register',
        'company':    request.owned_company,
        'columns':    ['Employee', 'Month/Year', 'Bonus %', 'Total Bonus', 'Status'],
        'rows': [{
            'cells': [r.employee.name, f'{r.salary_month}/{r.salary_year}',
                      f'{r.bonus_percentage}%', r.total_bonus,
                      'Paid' if r.is_paid else 'Pending'],
            'actions': [],
        } for r in records],
        'empty_message': 'No bonus records found.',
    })


@access_required('statutory')
def capp_maternity(request):
    from Aapp.app.maternity import maternity_record
    records = maternity_record.objects.filter(company=request.owned_company).select_related('employee')
    return render(request, 'Capp/generic/list.html', {
        'page_title': 'Maternity Benefit Register',
        'company':    request.owned_company,
        'columns':    ['Employee', 'Expected Delivery', 'Leave Start', 'Leave End', 'Benefit Amount', 'Status'],
        'rows': [{
            'cells': [r.employee.name, r.expected_delivery_date,
                      r.maternity_leave_start, r.maternity_leave_end or '—',
                      r.maternity_benefit_amount, 'Paid' if r.is_paid else 'Pending'],
            'actions': [],
        } for r in records],
        'empty_message': 'No maternity records found.',
    })


@access_required('statutory')
def capp_lwf(request):
    from Aapp.app.labour_welfare import LabourWelfareFundContribution
    records = LabourWelfareFundContribution.objects.filter(company=request.owned_company).order_by('-year')
    return render(request, 'Capp/generic/list.html', {
        'page_title': 'Labour Welfare Fund',
        'company':    request.owned_company,
        'columns':    ['Year', 'Period', 'Employees', 'Total Contribution', 'Due Date', 'Status'],
        'rows': [{
            'cells': [r.year, r.get_contribution_period_display(), r.total_employees,
                      r.total_contribution, r.due_date or '—', r.get_filing_status_display()],
            'actions': [],
        } for r in records],
        'empty_message': 'No LWF records found.',
    })


# ── Compliance calendar (read-only) ───────────────────────────────────────────

@access_required('compliance')
def capp_compliance(request):
    from Aapp.app.compliance_tracker import StatutoryReturnTracker
    from django.utils import timezone
    company = request.owned_company
    today   = timezone.now().date()
    all_items = StatutoryReturnTracker.objects.filter(company=company)
    return render(request, 'Capp/compliance.html', {
        'overdue':        all_items.filter(filing_status='pending', due_date__lt=today),
        'upcoming':       all_items.filter(filing_status='pending', due_date__gte=today).order_by('due_date')[:15],
        'filed':          all_items.filter(filing_status='filed').order_by('-filed_date')[:10],
        'overdue_count':  all_items.filter(filing_status='pending', due_date__lt=today).count(),
        'pending_count':  all_items.filter(filing_status='pending').count(),
        'total_count':    all_items.count(),
        'company':        company,
    })


# ── Report / PDF downloads ─────────────────────────────────────────────────────

@access_required('reports')
def capp_company_profile_pdf(request):
    from Aapp.app.salary_pdf import company_profile_pdf
    if not request.owner_profile.can_download_pdf:
        raise Http404('PDF download not permitted.')
    pdf   = company_profile_pdf(request.owned_company)
    fname = f'CompanyProfile_{request.owned_company.company_name.replace(" ", "_")}.pdf'
    return HttpResponse(pdf, content_type='application/pdf',
                        headers={'Content-Disposition': f'attachment; filename="{fname}"'})


@access_required('reports')
def capp_letterhead(request, doc_type):
    """Proxy to the Aapp letterhead generator — same function, scoped to owned_company."""
    from Aapp.app.pdf_views import download_letterhead_doc
    # Override session company temporarily so pdf_views._company() returns owner's company
    request.session['selected_company_id'] = request.owned_company.company_id
    return download_letterhead_doc(request, doc_type)
