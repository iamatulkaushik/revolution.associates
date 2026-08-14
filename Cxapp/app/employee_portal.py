"""
Cxapp/app/employee_portal.py
==============================
Employee self-service login for the Cxapp (self-signup Company Owner)
portal. Completely separate identity/session track from the Owner/
Sub-user system in Cxapp/middleware.py — an employee is NOT a Django
User, has no request.cx_owner_profile/cx_sub_user, and cannot reach
any Owner/HR-only view. Session-only auth, scoped to a single purpose:
viewing/downloading their OWN salary slip.

Login: PAN number + password.
  - PAN is looked up via CxEmployeeKYC.pan_number_hash (SHA-256,
    uppercased — same shadow-column pattern as the rest of this
    codebase; the encrypted PAN itself is never brute-force scanned).
  - Password is a separate credential (CxEmployeeAuth), hashed with
    Django's standard make_password/check_password — no custom crypto,
    per this codebase's stated principle that field encryption uses
    established libraries, not bespoke schemes.
  - An employee has ONE login regardless of how many months of salary
    exist; CxEmployeeAuth is 1:1 with CxEmployee.

Scope of access for a logged-in employee: their own CxSalary records
only (list + PDF). No employee data, no other employees' records, no
company/HR/Owner views.
"""

from django.contrib.auth.hashers import make_password, check_password
from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from functools import wraps

from Cxapp.app.employee import CxEmployee, _hash_value


# ── Credential table (separate from CxEmployeeKYC — keeps KYC untouched) ──────

class CxEmployeeAuth(models.Model):
    """
    Login credential for employee self-service. 1:1 with CxEmployee.
    Password hashed with Django's standard hasher — never stored or
    compared in plaintext.
    """
    employee        = models.OneToOneField(CxEmployee, on_delete=models.CASCADE, related_name='auth')
    password_hash   = models.CharField(max_length=255)
    is_active       = models.BooleanField(default=True)
    last_login_at   = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_employee_auth'
        verbose_name = 'Employee Login Credential'
        verbose_name_plural = 'Employee Login Credentials'

    def __str__(self):
        return f'Login — {self.employee.employee_code}'

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password_hash)


# ── Session-based auth decorator (independent of CxCompanyMiddleware) ─────────

def emp_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        employee_id = request.session.get('cx_emp_id')
        if not employee_id:
            return redirect('cxapp_emp_login')
        try:
            employee = CxEmployee.objects.get(employee_id=employee_id, is_deleted=False, is_working=True)
        except CxEmployee.DoesNotExist:
            request.session.pop('cx_emp_id', None)
            return redirect('cxapp_emp_login')
        request.cx_employee = employee
        return view_func(request, *args, **kwargs)
    return wrapper


# ── Login / logout ──────────────────────────────────────────────────────────

def cxapp_emp_login(request):
    if request.session.get('cx_emp_id'):
        return redirect('cxapp_emp_dashboard')

    if request.method == 'POST':
        pan = request.POST.get('pan', '').strip()
        password = request.POST.get('password', '')
        pan_hash = _hash_value(pan)

        kyc = None
        if pan_hash:
            from Cxapp.app.employee import CxEmployeeKYC
            kyc = CxEmployeeKYC.objects.filter(pan_number_hash=pan_hash).select_related('employee').first()

        employee = kyc.employee if kyc else None
        auth = getattr(employee, 'auth', None) if employee else None

        if not employee or not employee.is_working or employee.is_deleted or not auth \
                or not auth.is_active or not auth.check_password(password):
            messages.error(request, 'Invalid PAN or password.')
            return render(request, 'Cxapp/employee_portal/login.html')

        from django.utils import timezone
        auth.last_login_at = timezone.now()
        auth.save(update_fields=['last_login_at'])

        request.session['cx_emp_id'] = employee.employee_id
        return redirect('cxapp_emp_dashboard')

    return render(request, 'Cxapp/employee_portal/login.html')


def cxapp_emp_logout(request):
    request.session.pop('cx_emp_id', None)
    return redirect('cxapp_emp_login')


# ── Employee dashboard: own salary slips only ──────────────────────────────────

@emp_login_required
def cxapp_emp_dashboard(request):
    from Cxapp.app.process import CxSalary
    salaries = (CxSalary.objects
                .filter(employee=request.cx_employee)
                .order_by('-salary_year', '-salary_month'))
    return render(request, 'Cxapp/employee_portal/dashboard.html', {
        'employee': request.cx_employee,
        'salaries': salaries,
    })


@emp_login_required
def cxapp_emp_salary_slip_pdf(request, salary_id):
    from Cxapp.app.process import CxSalary
    from Cxapp.app.salary_pdf import cx_salary_slip_pdf

    salary = get_object_or_404(CxSalary, salary_id=salary_id, employee=request.cx_employee)
    pdf_bytes = cx_salary_slip_pdf(salary)
    filename = f'Salary_Slip_{salary.employee_code}_{salary.salary_month}_{salary.salary_year}.pdf'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
