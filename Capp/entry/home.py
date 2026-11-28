"""Capp/entry/home.py — the operator's home block (track AI-3, package E5).

Plain numbers and links for the current month: what I did, what is still missing, whether
entry is open, and how much of the plan is used. Only links the operator may use.
"""
import calendar
from datetime import date

from django.urls import reverse

from Capp.access import has_perm
from Capp.entry.gates import batch_for, entry_lock_reason
from revolution.app.plan_gate import has_feature


def operator_home(request):
    company, today = request.owned_company, date.today()
    month, year = today.month, today.year
    from Aapp.app.attandance import attendance
    from Aapp.app.employee import employee
    from Capp.foundation.models import CappAuditLog

    active = employee.objects.filter(CompanyID=company, is_working=True)
    entered = attendance.objects.filter(companyid=company, salary_month=month, salary_year=year,
                                        employee_id__in=active).count()
    month_start = today.replace(day=1)
    mine = CappAuditLog.objects.filter(company=company, user=request.user, at__date__gte=month_start)
    batch = batch_for(company, month, year)
    lock = entry_lock_reason(company, request.capp_mode, month, year)
    home = {
        'month_label': f'{calendar.month_name[month]} {year}',
        'batch_status': batch.status if batch else 'not created',
        'entry_open': lock is None, 'lock_reason': lock,
        'employees_added': mine.filter(action='create', model='employee').count(),
        'attendance_entered': entered, 'attendance_missing': max(active.count() - entered, 0),
        'links': [],
    }
    if has_feature(company, 'loans'):
        from Aapp.app.loans_advances import Advance, Loan
        home['loans_entered'] = (
            Loan.objects.filter(company=company, created_by=request.user.username,
                                created_at__date__gte=month_start).count()
            + Advance.objects.filter(company=company, created_by=request.user.username,
                                     created_at__date__gte=month_start).count())
    for perm, label, name, kw in (
            ('employees.add', 'Add employee', 'capp_ent_emp_add', None),
            ('attendance.edit', 'Enter attendance', 'capp_ent_att_grid', None),
            ('loans.edit', 'Add loan or advance', 'capp_ent_loan_add', {'kind': 'loans'}),
            ('payroll.download', 'Downloads', 'capp_ent_dl_hub', None)):
        if has_perm(request, perm) and (name != 'capp_ent_loan_add' or has_feature(company, 'loans')):
            home['links'].append({'label': label, 'url': reverse(name, kwargs=kw)})
    return home
