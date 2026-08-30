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


# ── Password reset (PAN + registered email, no django.contrib.auth.User) ──────
# Employees aren't a User, so Sapp.app.password_reset doesn't apply here.
# Identity is PAN (hashed lookup, same pattern as login above); the reset
# link additionally requires the email on file to match, since PAN alone
# isn't secret enough to gate a password change.

from django.conf import settings as _settings
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.mail import send_mail as _send_mail
from django.contrib.auth.password_validation import validate_password as _validate_password
from django.core.exceptions import ValidationError as _ValidationError

_EMP_RESET_SALT = 'cxapp.emp_password_reset'
_EMP_RESET_MAX_AGE = 60 * 60 * 2  # 2 hours
_emp_reset_signer = TimestampSigner(salt=_EMP_RESET_SALT)


def cxapp_emp_password_reset_request(request):
    if request.method == 'POST':
        pan = request.POST.get('pan', '').strip()
        email = request.POST.get('email', '').strip()
        pan_hash = _hash_value(pan)

        from Cxapp.app.employee import CxEmployeeKYC
        kyc = CxEmployeeKYC.objects.filter(pan_number_hash=pan_hash).select_related('employee').first()
        employee = kyc.employee if kyc else None
        contact_email = getattr(getattr(employee, 'contact', None), 'email', '') if employee else ''

        if employee and contact_email and contact_email.lower() == email.lower() and hasattr(employee, 'auth'):
            try:
                token = _emp_reset_signer.sign(str(employee.employee_id))
                parent_host = getattr(_settings, 'PARENT_HOST', 'localhost:8000')
                scheme = 'https' if request.is_secure() else 'http'
                link = f'{scheme}://cxapp.{parent_host}/employee/reset/{token}/'
                _send_mail(
                    subject='Reset your password — Revolution Associates',
                    message=f'Click the link below to reset your password.\n\n{link}\n\n'
                            f'This link expires in 2 hours.',
                    from_email=_settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[contact_email],
                    fail_silently=False,
                )
            except Exception:
                logging.getLogger('Cxapp').exception(
                    "Failed to send employee password reset email: employee_id='%s'",
                    getattr(employee, 'employee_id', None))

        # Same message regardless of match — don't reveal registration status.
        messages.success(request, 'If those details match our records, a reset link has been sent.')
        return redirect('cxapp_emp_login')

    return render(request, 'Cxapp/employee_portal/password_reset_request.html')


def cxapp_emp_password_reset_confirm(request, token):
    try:
        employee_id = _emp_reset_signer.unsign(token, max_age=_EMP_RESET_MAX_AGE)
    except SignatureExpired:
        messages.error(request, 'This reset link has expired. Please request a new one.')
        return redirect('cxapp_emp_password_reset_request')
    except BadSignature:
        messages.error(request, 'Invalid reset link.')
        return redirect('cxapp_emp_login')

    employee = CxEmployee.objects.filter(employee_id=employee_id, is_deleted=False).first()
    auth = getattr(employee, 'auth', None) if employee else None
    if not auth:
        messages.error(request, 'Invalid reset link.')
        return redirect('cxapp_emp_login')

    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'Cxapp/employee_portal/password_reset_confirm.html')
        try:
            _validate_password(password1)
        except _ValidationError as e:
            for err in e.messages:
                messages.error(request, err)
            return render(request, 'Cxapp/employee_portal/password_reset_confirm.html')

        auth.set_password(password1)
        auth.save(update_fields=['password_hash'])
        messages.success(request, 'Password updated. Please log in.')
        return redirect('cxapp_emp_login')

    return render(request, 'Cxapp/employee_portal/password_reset_confirm.html')


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
