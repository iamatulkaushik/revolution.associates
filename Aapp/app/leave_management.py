"""
Leave management — now reads/writes the leave fields that already live on
Aapp.app.attandance.attendance (casual_leaves, earned_leaves, sick_leaves,
comp_leaves) plus the leave_lapsed/leave_encashed/leave_encashment_amount/
leave_wages_paid fields absorbed there from the old, now-deleted
employee_leave model.

No separate leave record is stored — attendance is the single source of
truth for a given employee/month/year, avoiding two tables drifting out
of sync with each other.

Leave balances are gated on Shop & Establishments Act registration: with
no shop_act on file, attendance.leave_balance() returns None and this
module surfaces that as "Not available" rather than a numeric zero.
"""

from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from Sapp.app.company import Company
from Sapp.app.user import associateuser
from Aapp.app.employee import employee
from Aapp.app.attandance import attendance, MONTH_CHOICES, YEAR_CHOICES
from Aapp.app.statutory_gates import get_company_gates


# ── Associate-only guard ──────────────────────────────────────────────────────

def _get_associate(request):
    try:
        return associateuser.objects.get(user=request.user)
    except associateuser.DoesNotExist:
        return None

def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None

def _guard(request):
    """Returns (associate, company) or (None, None) with error message set."""
    associate = _get_associate(request)
    if not associate:
        messages.error(request, 'Access restricted to associates only.')
        return None, None
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return None, None
    return associate, company


# ── Form ──────────────────────────────────────────────────────────────────────

class LeaveForm(forms.ModelForm):
    class Meta:
        model  = attendance
        fields = ['salary_month', 'salary_year', 'casual_leaves', 'earned_leaves',
                  'sick_leaves', 'comp_leaves', 'leave_lapsed', 'leave_encashed',
                  'leave_encashment_amount', 'leave_wages_paid']
        widgets = {
            'salary_month': forms.Select(choices=MONTH_CHOICES),
            'salary_year':  forms.NumberInput(attrs={'min': 2026, 'max': 2032}),
        }


# ── list ──────────────────────────────────────────────────────────────────────

@login_required
def list_leave(request):
    associate, company = _guard(request)
    if not associate:
        return redirect('aapp_dashboard')

    gates = get_company_gates(company)
    if not gates['shop_act']:
        messages.warning(
            request,
            'Shop & Establishments Act registration not on file — '
            'leave balances are not available for this company.'
        )

    records = attendance.objects.filter(companyid=company).select_related('employee_id')

    month = request.GET.get('month')
    year = request.GET.get('year')
    if month:
        records = records.filter(salary_month=month)
    if year:
        records = records.filter(salary_year=year)

    rows = [{
        'cells': [
            r.emp_code, r.get_salary_month_display(), r.salary_year,
            r.leave_earned_total() if gates['shop_act'] else 'N/A',
            (r.leave_earned_total() - (r.leave_balance() or 0)) if gates['shop_act'] else 'N/A',
            r.leave_balance() if gates['shop_act'] else 'N/A',
            r.leave_wages_paid,
        ],
        'actions': [
            {'url': reverse('update_leave', args=[r.attendanceid]), 'label': 'Edit', 'css': 'edit'},
            {'url': reverse('delete_leave', args=[r.attendanceid]), 'label': 'Delete', 'css': 'delete'},
        ],
    } for r in records]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Employee Leave Records',
        'columns': ['Employee Code', 'Month', 'Year', 'Earned', 'Availed', 'Balance', 'Wages Paid'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_leave'), 'add_label': 'Add Leave Record',
        'empty_message': 'No leave records yet.',
    })


# ── add ───────────────────────────────────────────────────────────────────────

@login_required
def add_leave(request):
    associate, company = _guard(request)
    if not associate:
        return redirect('aapp_dashboard')

    gates = get_company_gates(company)
    if not gates['shop_act']:
        messages.error(
            request,
            'Shop & Establishments Act registration not on file — '
            'leave records cannot be created for this company.'
        )
        return redirect('list_leave')

    employees = employee.objects.filter(CompanyID=company, is_working=True).order_by('name')

    if request.method == 'POST':
        p = request.POST
        emp = get_object_or_404(employee, employeeid=p.get('employee_id'), CompanyID=company)
        month = int(p.get('salary_month', 0))
        year = int(p.get('salary_year', 0))

        rec, created = attendance.objects.get_or_create(
            employee_id=emp, salary_month=month, salary_year=year,
            defaults={'emp_code': emp.employeecode, 'companyid': company, 'created_by': request.user},
        )
        if not created and (rec.casual_leaves or rec.earned_leaves or rec.sick_leaves):
            messages.warning(
                request,
                f"Attendance record for {emp.name} — {month}/{year} already has leave data; updating it."
            )
        try:
            rec.casual_leaves = p.get('casual_leaves', 0) or 0
            rec.earned_leaves = p.get('earned_leaves', 0) or 0
            rec.sick_leaves = p.get('sick_leaves', 0) or 0
            rec.comp_leaves = p.get('comp_leaves', 0) or 0
            rec.leave_lapsed = p.get('leave_lapsed', 0) or 0
            rec.leave_encashed = p.get('leave_encashed', 0) or 0
            rec.leave_encashment_amount = p.get('leave_encashment_amount', 0) or 0
            rec.leave_wages_paid = p.get('leave_wages_paid', 0) or 0
            rec.updated_by = request.user
            rec.save()
            messages.success(request, f"Leave record for {emp.name} saved.")
            return redirect('list_leave')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'Aapp/generic/form.html', {
        'form': LeaveForm(), 'employees': employees, 'company': company,
        'page_title': 'Add Leave Record',
        'cancel_url': reverse('list_leave'),
    })


# ── update ────────────────────────────────────────────────────────────────────

@login_required
def update_leave(request, leave_id):
    associate, company = _guard(request)
    if not associate:
        return redirect('aapp_dashboard')

    gates = get_company_gates(company)
    if not gates['shop_act']:
        messages.error(
            request,
            'Shop & Establishments Act registration not on file — '
            'leave records cannot be edited for this company.'
        )
        return redirect('list_leave')

    rec = get_object_or_404(attendance, attendanceid=leave_id, companyid=company)

    if request.method == 'POST':
        p = request.POST
        try:
            rec.salary_month = int(p.get('salary_month', rec.salary_month))
            rec.salary_year = int(p.get('salary_year', rec.salary_year))
            rec.casual_leaves = p.get('casual_leaves', rec.casual_leaves) or rec.casual_leaves
            rec.earned_leaves = p.get('earned_leaves', rec.earned_leaves) or rec.earned_leaves
            rec.sick_leaves = p.get('sick_leaves', rec.sick_leaves) or rec.sick_leaves
            rec.comp_leaves = p.get('comp_leaves', rec.comp_leaves) or rec.comp_leaves
            rec.leave_lapsed = p.get('leave_lapsed', rec.leave_lapsed) or rec.leave_lapsed
            rec.leave_encashed = p.get('leave_encashed', rec.leave_encashed) or rec.leave_encashed
            rec.leave_encashment_amount = (
                p.get('leave_encashment_amount', rec.leave_encashment_amount) or rec.leave_encashment_amount
            )
            rec.leave_wages_paid = p.get('leave_wages_paid', rec.leave_wages_paid) or rec.leave_wages_paid
            rec.updated_by = request.user
            rec.save()
            messages.success(request, "Leave record updated.")
            return redirect('list_leave')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    form = LeaveForm(instance=rec)
    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'rec': rec, 'company': company,
        'page_title': f'Edit Leave Record — {rec.emp_code}',
        'cancel_url': reverse('list_leave'),
    })


# ── delete ────────────────────────────────────────────────────────────────────
# NOTE: clears the leave fields on the attendance row rather than deleting
# the row itself — the row also carries working_days/overtime data that
# must not be lost.

@login_required
def delete_leave(request, leave_id):
    associate, company = _guard(request)
    if not associate:
        return redirect('aapp_dashboard')

    rec = get_object_or_404(attendance, attendanceid=leave_id, companyid=company)

    if request.method == 'POST':
        rec.casual_leaves = 0
        rec.earned_leaves = 0
        rec.sick_leaves = 0
        rec.comp_leaves = 0
        rec.leave_lapsed = 0
        rec.leave_encashed = 0
        rec.leave_encashment_amount = 0
        rec.leave_wages_paid = 0
        rec.save()
        messages.success(request, "Leave record cleared.")
        return redirect('list_leave')

    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Delete Leave Record',
        'confirm_message': f'Clear leave data for <strong>{rec.emp_code}</strong> — '
                            f'{rec.get_salary_month_display()} {rec.salary_year}?',
        'cancel_url': reverse('list_leave'),
    })
