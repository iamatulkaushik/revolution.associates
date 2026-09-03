"""
Cxapp/app/employee.py
=======================
Employee module for the Cxapp (self-signup Company Owner) portal.

Company-level statutory gates are imported from Sapp (Sapp.app.company.
company_statury — same table Aapp reads) via Cxapp/app/statutory_gates.py,
which mirrors Aapp's rule exactly: no registration on file, no deduction.
UAN/ESI/Labour ID fields on the employee stay visible/editable regardless
of gate state — the GATE decides whether payroll actually deducts, not
whether the number can be recorded. Employment cannot be marked ESI/EPF/
Labour "active" via helper methods below unless the matching company gate
is open; this keeps data entry honest without blocking record-keeping.

TABLE SPLIT — sensitivity-driven, not just "one big employee row":
    Employee            — core identity, low-sensitivity, everyone with
                           employee-read access hits this constantly
    EmployeeAddress      — address block, low sensitivity, 1:1
    EmployeeStatutory     — UAN/ESI/Labour IDs, medium sensitivity, 1:1
    EmployeeContact       — mobile/phone/email, low sensitivity, 1:1
    EmployeeKYC           — Aadhaar/PAN/Passport/DL/VoterID, HIGH
                           sensitivity, encrypted, 1:1, rarely queried
    EmployeeBanking        — account/IFSC/bank, HIGH sensitivity,
                           encrypted, 1:1, only touched by payroll
    EmployeeEmployment    — employment type + dates, low-medium
                           sensitivity, 1:1
    EmployeeNominee        — nominee/nomination, one employee can have
                           MULTIPLE nominees (percentage-split gratuity/
                           PF nomination), HIGH sensitivity (contains
                           nominee Aadhaar), encrypted, 1:many

Aadhaar/PAN/bank account use secure_crypto.py's `EncryptedCharField` (AES-256-GCM /
XChaCha20-Poly1305 authenticated encryption, keyed off settings.FIELD_ENCRYPTION_KEY).
Companion `_hash` columns (SHA-256, not reversible) are kept so the app
can still filter/lookup by exact value without decrypting every row —
same shadow-column strategy used elsewhere in this codebase.
"""

import hashlib

from django import forms
from django.db import models, transaction
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from revolution.secure_crypto import EncryptedCharField

from Sapp.app.state_district import State, District
from Sapp.app import bank
from Cxapp.app.designation import CxDesignation
from Cxapp.app.statutory_gates import get_company_gates


def _hash_value(value: str) -> str:
    """One-way hash for exact-match lookups on encrypted fields."""
    if not value:
        return ''
    return hashlib.sha256(value.strip().upper().encode('utf-8')).hexdigest()


GENDER_CHOICES = [('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')]
MARITAL_CHOICES = [('Single', 'Single'), ('Married', 'Married'),
                    ('Divorced', 'Divorced'), ('Widowed', 'Widowed')]
EMPLOYMENT_TYPE_CHOICES = [('Permanent', 'Permanent'), ('Contract', 'Contract'), ('Intern', 'Intern')]
NOMINEE_RELATION_CHOICES = [
    ('Spouse', 'Spouse'), ('Son', 'Son'), ('Daughter', 'Daughter'),
    ('Father', 'Father'), ('Mother', 'Mother'), ('Brother', 'Brother'),
    ('Sister', 'Sister'), ('Other', 'Other'),
]


# ── Core table ───────────────────────────────────────────────────────────────

class CxEmployee(models.Model):
    """
    Core identity row. Low sensitivity — safe for broad sub-user read
    access (HR, Front Desk, Operator all touch this routinely).
    """
    employee_id      = models.AutoField(primary_key=True)
    company           = models.ForeignKey('Cxapp.CxOwnerProfile', on_delete=models.PROTECT,
                                          related_name='employees')
    employee_code     = models.CharField(max_length=20, unique=True)
    designation       = models.ForeignKey(CxDesignation, on_delete=models.PROTECT,
                                          related_name='employees')

    name              = models.CharField(max_length=255)
    father_husband_name = models.CharField(max_length=255, blank=True)
    mother_name       = models.CharField(max_length=255, blank=True)
    gender            = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth     = models.DateField()
    blood_group       = models.CharField(max_length=10, blank=True)
    religion          = models.CharField(max_length=100, blank=True)
    marital_status    = models.CharField(max_length=20, choices=MARITAL_CHOICES, blank=True)
    employee_pic      = models.ImageField(upload_to='cx_employee_pics/', blank=True, null=True)

    is_working        = models.BooleanField(default=True)
    is_deleted        = models.BooleanField(default=False)
    created_at        = models.DateTimeField(auto_now_add=True)
    created_by        = models.CharField(max_length=50, blank=True)
    updated_at        = models.DateTimeField(auto_now=True)
    updated_by        = models.CharField(max_length=50, blank=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_employee'
        ordering = ['name']
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'

    def __str__(self):
        return f'{self.employee_code} — {self.name}'

    def statutory_gates(self):
        """Company-level gates — same source of truth as Aapp."""
        return get_company_gates(self.company.company)


# ── Address (1:1, low sensitivity) ────────────────────────────────────────────

class CxEmployeeAddress(models.Model):
    employee   = models.OneToOneField(CxEmployee, on_delete=models.CASCADE, related_name='address')
    address    = models.TextField()
    state      = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True)
    district   = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, blank=True)
    pin        = models.CharField(max_length=10)
    country    = models.CharField(max_length=100, default='India')

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_employee_address'
        verbose_name = 'Employee Address'

    def __str__(self):
        return f'Address — {self.employee.name}'


# ── Contact (1:1, low sensitivity) ────────────────────────────────────────────

class CxEmployeeContact(models.Model):
    employee = models.OneToOneField(CxEmployee, on_delete=models.CASCADE, related_name='contact')
    mobile   = models.CharField(max_length=15, unique=True)
    phone    = models.CharField(max_length=15, blank=True)
    email    = models.EmailField(blank=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_employee_contact'
        verbose_name = 'Employee Contact'

    def __str__(self):
        return f'Contact — {self.employee.name}'


# ── Statutory IDs (1:1, medium sensitivity) ───────────────────────────────────

class CxEmployeeStatutory(models.Model):
    """
    UAN/ESI/Labour identifiers. Recording a number here does NOT mean
    payroll deducts for it — deduction is gated by the COMPANY's own
    registration status (get_company_gates), same rule as Aapp.
    """
    employee     = models.OneToOneField(CxEmployee, on_delete=models.CASCADE, related_name='statutory')
    uan_number   = models.CharField(max_length=50, blank=True, verbose_name='UAN')
    esi_number   = models.CharField(max_length=20, blank=True, verbose_name='ESI Number')
    labour_id    = models.CharField(max_length=50, blank=True, verbose_name='Labour ID')

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_employee_statutory'
        verbose_name = 'Employee Statutory IDs'

    def __str__(self):
        return f'Statutory — {self.employee.name}'

    def deduction_eligibility(self):
        """
        Returns {'epf': bool, 'esi': bool, 'labour': bool} — True only if
        BOTH the employee has the ID on file AND the company gate is open.
        Mirrors Aapp.statutory_gates: no registration, no deduction.
        """
        gates = get_company_gates(self.employee.company.company)
        return {
            'epf':    bool(self.uan_number) and gates.get('epf', False),
            'esi':    bool(self.esi_number) and gates.get('esi', False),
            'labour': bool(self.labour_id) and gates.get('labour', False),
        }


# ── KYC (1:1, HIGH sensitivity, encrypted) ────────────────────────────────────

class CxEmployeeKYC(models.Model):
    """
    Identity documents. Aadhaar and PAN are encrypted at rest via
    secure_crypto.EncryptedCharField (AEAD, XChaCha20-Poly1305 by
    default); companion `_hash` columns enable exact-match
    lookup/uniqueness without decrypting every row (shadow-column
    pattern, same as elsewhere in this codebase).

    Access to this table should be restricted to Owner + HR role only.
    """
    employee            = models.OneToOneField(CxEmployee, on_delete=models.CASCADE, related_name='kyc')

    aadhar_number         = EncryptedCharField(max_length=500)
    aadhar_number_hash     = models.CharField(max_length=64, unique=True, editable=False)

    pan_number            = EncryptedCharField(max_length=500, blank=True, null=True)
    pan_number_hash        = models.CharField(max_length=64, blank=True, editable=False)

    passport_number        = EncryptedCharField(max_length=500, blank=True, null=True)
    passport_number_hash    = models.CharField(max_length=64, blank=True, editable=False)

    driving_license_number = EncryptedCharField(max_length=500, blank=True, null=True)
    driving_license_number_hash = models.CharField(max_length=64, blank=True, editable=False)

    voter_id               = EncryptedCharField(max_length=500, blank=True, null=True)
    voter_id_hash           = models.CharField(max_length=64, blank=True, editable=False)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_employee_kyc'
        verbose_name = 'Employee KYC'

    def __str__(self):
        return f'KYC — {self.employee.name}'

    def save(self, *args, **kwargs):
        self.aadhar_number_hash = _hash_value(str(self.aadhar_number))
        self.pan_number_hash = _hash_value(str(self.pan_number))
        self.passport_number_hash = _hash_value(str(self.passport_number))
        self.driving_license_number_hash = _hash_value(str(self.driving_license_number))
        self.voter_id_hash = _hash_value(str(self.voter_id))
        super().save(*args, **kwargs)


# ── Banking (1:1, HIGH sensitivity, encrypted) ────────────────────────────────

class CxEmployeeBanking(models.Model):
    employee       = models.OneToOneField(CxEmployee, on_delete=models.CASCADE, related_name='banking')
    account_number  = EncryptedCharField(max_length=500)
    account_number_hash = models.CharField(max_length=64, unique=True, editable=False)
    bank           = models.ForeignKey(bank.bank_name, on_delete=models.PROTECT, related_name='cx_employee_banking',
                                       verbose_name='Bank Name', null=True, blank=True)
    bank_ifsc       = models.CharField(max_length=11)
    bank_address    = models.TextField(blank=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_employee_banking'
        verbose_name = 'Employee Banking'

    def __str__(self):
        return f'Banking — {self.employee.name}'

    def save(self, *args, **kwargs):
        self.account_number_hash = _hash_value(str(self.account_number))
        super().save(*args, **kwargs)


# ── Employment (1:1, low-medium sensitivity) ──────────────────────────────────

class CxEmployeeEmployment(models.Model):
    employee              = models.OneToOneField(CxEmployee, on_delete=models.CASCADE, related_name='employment')
    employment_type        = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default='Permanent')
    date_of_joining         = models.DateField()
    doj_esi                = models.DateField(null=True, blank=True, verbose_name='ESI Date of Joining')
    doj_epf                = models.DateField(null=True, blank=True, verbose_name='EPF Date of Joining')
    date_of_retirement      = models.DateField(null=True, blank=True)
    date_of_leaving         = models.DateField(null=True, blank=True)
    leaving_reason          = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_employee_employment'
        verbose_name = 'Employee Employment'

    def __str__(self):
        return f'Employment — {self.employee.name}'


# ── Nominee (1:many, HIGH sensitivity — contains nominee Aadhaar) ────────────

class CxEmployeeNominee(models.Model):
    """
    An employee may have multiple nominees (gratuity/PF nomination
    splits by percentage). Kept as its own table since it's naturally
    one-to-many and carries a second Aadhaar per row.
    """
    employee        = models.ForeignKey(CxEmployee, on_delete=models.CASCADE, related_name='nominees')
    nominee_name     = models.CharField(max_length=255)
    aadhar_number     = EncryptedCharField(max_length=500)
    aadhar_number_hash = models.CharField(max_length=64, editable=False)
    relation         = models.CharField(max_length=20, choices=NOMINEE_RELATION_CHOICES)
    date_of_birth     = models.DateField()
    address          = models.TextField(blank=True)
    percentage       = models.DecimalField(max_digits=5, decimal_places=2,
                                            help_text='Share of nomination, e.g. 50.00 for 50%')

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_employee_nominee'
        verbose_name = 'Employee Nominee'
        verbose_name_plural = 'Employee Nominees'

    def __str__(self):
        return f'{self.nominee_name} ({self.percentage}%) — {self.employee.name}'

    def save(self, *args, **kwargs):
        self.aadhar_number_hash = _hash_value(str(self.aadhar_number))
        super().save(*args, **kwargs)

    @staticmethod
    def total_percentage(employee):
        agg = CxEmployeeNominee.objects.filter(employee=employee).aggregate(models.Sum('percentage'))
        return agg['percentage__sum'] or 0


# ── Forms ────────────────────────────────────────────────────────────────────

class CxEmployeeForm(forms.ModelForm):
    class Meta:
        model = CxEmployee
        fields = ['employee_code', 'designation', 'name', 'father_husband_name',
                  'mother_name', 'gender', 'date_of_birth', 'blood_group',
                  'religion', 'marital_status', 'employee_pic']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company is not None:
            self.fields['designation'].queryset = CxDesignation.objects.filter(
                company=company, is_deleted=False, is_active=True
            )


class CxEmployeeAddressForm(forms.ModelForm):
    class Meta:
        model = CxEmployeeAddress
        fields = ['address', 'state', 'district', 'pin', 'country']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Scope district choices to the currently selected state so a
        # stale full list never round-trips as valid on submit. Checks
        # POST data first (form re-render after a validation error),
        # then falls back to the bound instance's state (initial GET).
        state_id = self.data.get(self.add_prefix('state')) if self.is_bound else None
        if not state_id and self.instance and self.instance.pk and self.instance.state_id:
            state_id = self.instance.state_id
        if state_id:
            self.fields['district'].queryset = District.objects.filter(state_id=state_id).order_by('name')
        else:
            self.fields['district'].queryset = District.objects.none()


class CxEmployeeContactForm(forms.ModelForm):
    class Meta:
        model = CxEmployeeContact
        fields = ['mobile', 'phone', 'email']


class CxEmployeeStatutoryForm(forms.ModelForm):
    class Meta:
        model = CxEmployeeStatutory
        fields = ['uan_number', 'esi_number', 'labour_id']


class CxEmployeeKYCForm(forms.Form):
    """
    Plain Form, not ModelForm — EncryptedCharField sets editable=False,
    which ModelForm refuses to include even when named explicitly.
    Views assign cleaned_data onto the model instance manually.
    """
    aadhar_number           = forms.CharField(max_length=12)
    pan_number              = forms.CharField(max_length=10, required=False)
    passport_number         = forms.CharField(max_length=20, required=False)
    driving_license_number  = forms.CharField(max_length=20, required=False)
    voter_id                = forms.CharField(max_length=20, required=False)

    def clean_aadhar_number(self):
        value = self.cleaned_data['aadhar_number']
        if len(value) != 12 or not value.isdigit():
            raise forms.ValidationError('Aadhaar must be exactly 12 digits.')
        return value

    def clean_pan_number(self):
        value = self.cleaned_data.get('pan_number', '')
        if value:
            value = value.upper()
            if len(value) != 10:
                raise forms.ValidationError('PAN must be exactly 10 characters.')
        return value


class CxEmployeeBankingForm(forms.Form):
    """Plain Form — see CxEmployeeKYCForm docstring."""
    account_number = forms.CharField(max_length=30)
    bank           = forms.ModelChoiceField(queryset=bank.bank_name.objects.all().order_by('name'), label='Bank Name')
    bank_ifsc      = forms.CharField(max_length=11)
    bank_address   = forms.CharField(widget=forms.Textarea, required=False)


class CxEmployeeEmploymentForm(forms.ModelForm):
    class Meta:
        model = CxEmployeeEmployment
        fields = ['employment_type', 'date_of_joining', 'doj_esi', 'doj_epf',
                  'date_of_retirement', 'date_of_leaving', 'leaving_reason']
        widgets = {
            'date_of_joining': forms.DateInput(attrs={'type': 'date'}),
            'doj_esi': forms.DateInput(attrs={'type': 'date'}),
            'doj_epf': forms.DateInput(attrs={'type': 'date'}),
            'date_of_retirement': forms.DateInput(attrs={'type': 'date'}),
            'date_of_leaving': forms.DateInput(attrs={'type': 'date'}),
        }


class CxEmployeeNomineeForm(forms.Form):
    """
    Plain Form — aadhar_number is encrypted/non-editable (see
    CxEmployeeKYCForm docstring), so the whole form is kept consistent
    as a plain Form rather than mixing ModelForm + manual field.
    """
    nominee_name  = forms.CharField(max_length=255)
    aadhar_number = forms.CharField(max_length=12)
    relation      = forms.ChoiceField(choices=NOMINEE_RELATION_CHOICES)
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    address       = forms.CharField(widget=forms.Textarea, required=False)
    percentage    = forms.DecimalField(max_digits=5, decimal_places=2,
                                        help_text='Share of nomination, e.g. 50.00 for 50%')

    def clean_aadhar_number(self):
        value = self.cleaned_data['aadhar_number']
        if len(value) != 12 or not value.isdigit():
            raise forms.ValidationError('Aadhaar must be exactly 12 digits.')
        return value


# ── Views ────────────────────────────────────────────────────────────────────
# HR-role sub-users and Owner get full access; other roles get list/read
# only, per ROLE_PERMISSIONS['employees'] in Cxapp/app/sub_user.py.

def _can_manage_employees(request):
    if getattr(request, 'cx_sub_user', None) is None:
        return True  # owner always can
    return request.cx_sub_user.get_role_permissions().get('employees', False)


def cxapp_employee_list(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_employee_list)(request)


def _employee_list(request):
    employees = CxEmployee.objects.filter(
        company=request.cx_owner_profile, is_deleted=False
    ).select_related('designation').order_by('name')
    return render(request, 'Cxapp/employee/employee_list.html', {
        'employees': employees,
        'can_manage': _can_manage_employees(request),
    })


def cxapp_employee_create(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_employee_create)(request)


def _employee_create(request):
    if not _can_manage_employees(request):
        messages.error(request, 'You do not have permission to add employees.')
        return redirect('cxapp_employee_list')

    owner_profile = request.cx_owner_profile

    if request.method == 'POST':
        form = CxEmployeeForm(request.POST, request.FILES, company=owner_profile.company)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.company = owner_profile
            employee.created_by = request.user.username
            employee.updated_by = request.user.username
            employee.save()
            messages.success(request, f"Employee '{employee.name}' created. Continue with remaining details.")
            return redirect('cxapp_employee_detail', employee_id=employee.employee_id)
    else:
        form = CxEmployeeForm(company=owner_profile.company)

    return render(request, 'Cxapp/employee/employee_form.html', {'form': form, 'is_new': True})


def cxapp_employee_detail(request, employee_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_employee_detail)(request, employee_id)


def _employee_detail(request, employee_id):
    """
    Single-page hub showing linked records (address/contact/statutory/
    employment always shown; KYC/banking/nominees gated to owner+HR).
    """
    employee = get_object_or_404(CxEmployee, employee_id=employee_id, company=request.cx_owner_profile)
    is_sensitive_allowed = _can_manage_employees(request)

    context = {
        'employee': employee,
        'address': getattr(employee, 'address', None),
        'contact': getattr(employee, 'contact', None),
        'statutory': getattr(employee, 'statutory', None),
        'employment': getattr(employee, 'employment', None),
        'kyc': getattr(employee, 'kyc', None) if is_sensitive_allowed else None,
        'banking': getattr(employee, 'banking', None) if is_sensitive_allowed else None,
        'nominees': employee.nominees.all() if is_sensitive_allowed else [],
        'gates': employee.statutory_gates(),
        'deduction_eligibility': employee.statutory.deduction_eligibility() if hasattr(employee, 'statutory') else None,
        'can_manage': is_sensitive_allowed,
        'has_login': hasattr(employee, 'auth'),
    }
    return render(request, 'Cxapp/employee/employee_detail.html', context)


def cxapp_employee_set_password(request, employee_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_employee_set_password)(request, employee_id)


def _employee_set_password(request, employee_id):
    """
    Owner + HR only — sets/resets the employee's login password
    (PAN + password login, see Cxapp/app/employee_portal.py). Password
    is generated here and shown once; it is never stored or displayed
    again after this response.
    """
    if not _can_manage_employees(request):
        messages.error(request, 'You do not have permission to manage employee logins.')
        return redirect('cxapp_employee_detail', employee_id=employee_id)

    from Cxapp.app.employee_portal import CxEmployeeAuth
    import secrets, string

    employee = get_object_or_404(CxEmployee, employee_id=employee_id, company=request.cx_owner_profile)

    if request.method == 'POST':
        alphabet = string.ascii_uppercase + string.ascii_lowercase + string.digits
        raw_password = ''.join(secrets.choice(alphabet) for _ in range(10))

        auth, _ = CxEmployeeAuth.objects.get_or_create(employee=employee)
        auth.set_password(raw_password)
        auth.is_active = True
        auth.save()

        return render(request, 'Cxapp/employee/employee_password_generated.html', {
            'employee': employee,
            'raw_password': raw_password,
        })

    return render(request, 'Cxapp/employee/employee_password_confirm.html', {'employee': employee})


def _section_edit(request, employee_id, form_cls, model_cls, template, related_name):
    """
    Shared edit handler for the 1:1 side-tables (address/contact/etc.).
    Handles both ModelForm subclasses (address/contact/statutory/
    employment) and plain Form subclasses (kyc/banking, since their
    encrypted fields are non-editable and ModelForm rejects them).
    """
    from Cxapp.views import cx_login_required

    is_model_form = issubclass(form_cls, forms.ModelForm)

    @cx_login_required
    def _view(request, employee_id):
        if not _can_manage_employees(request):
            messages.error(request, 'You do not have permission to edit employee details.')
            return redirect('cxapp_employee_detail', employee_id=employee_id)

        employee = get_object_or_404(CxEmployee, employee_id=employee_id, company=request.cx_owner_profile)
        instance = getattr(employee, related_name, None)

        if request.method == 'POST':
            if is_model_form:
                form = form_cls(request.POST, instance=instance)
            else:
                form = form_cls(request.POST)

            if form.is_valid():
                if is_model_form:
                    obj = form.save(commit=False)
                else:
                    obj = instance or model_cls(employee=employee)
                    for field_name, value in form.cleaned_data.items():
                        setattr(obj, field_name, value)
                obj.employee = employee
                obj.save()
                messages.success(request, 'Saved.')
                return redirect('cxapp_employee_detail', employee_id=employee.employee_id)
        else:
            if is_model_form:
                form = form_cls(instance=instance)
            elif instance is not None:
                # Encrypted fields decrypt transparently via the descriptor,
                # so initial= can safely read plaintext off the instance.
                initial = {f: getattr(instance, f) for f in form_cls.base_fields}
                form = form_cls(initial=initial)
            else:
                form = form_cls()

        return render(request, template, {'form': form, 'employee': employee})

    return _view(request, employee_id)


def cxapp_employee_address_edit(request, employee_id):
    return _section_edit(request, employee_id, CxEmployeeAddressForm, CxEmployeeAddress,
                          'Cxapp/employee/employee_address_form.html', 'address')


def cxapp_employee_contact_edit(request, employee_id):
    return _section_edit(request, employee_id, CxEmployeeContactForm, CxEmployeeContact,
                          'Cxapp/employee/employee_contact_form.html', 'contact')


def cxapp_employee_statutory_edit(request, employee_id):
    return _section_edit(request, employee_id, CxEmployeeStatutoryForm, CxEmployeeStatutory,
                          'Cxapp/employee/employee_statutory_form.html', 'statutory')


def cxapp_employee_kyc_edit(request, employee_id):
    return _section_edit(request, employee_id, CxEmployeeKYCForm, CxEmployeeKYC,
                          'Cxapp/employee/employee_kyc_form.html', 'kyc')


def cxapp_employee_banking_edit(request, employee_id):
    return _section_edit(request, employee_id, CxEmployeeBankingForm, CxEmployeeBanking,
                          'Cxapp/employee/employee_banking_form.html', 'banking')


def cxapp_employee_employment_edit(request, employee_id):
    return _section_edit(request, employee_id, CxEmployeeEmploymentForm, CxEmployeeEmployment,
                          'Cxapp/employee/employee_employment_form.html', 'employment')


def cxapp_employee_nominee_add(request, employee_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_nominee_add)(request, employee_id)


def _nominee_add(request, employee_id):
    if not _can_manage_employees(request):
        messages.error(request, 'You do not have permission to edit nominees.')
        return redirect('cxapp_employee_detail', employee_id=employee_id)

    employee = get_object_or_404(CxEmployee, employee_id=employee_id, company=request.cx_owner_profile)

    if request.method == 'POST':
        form = CxEmployeeNomineeForm(request.POST)
        if form.is_valid():
            existing_total = CxEmployeeNominee.total_percentage(employee)
            new_pct = form.cleaned_data['percentage']
            if existing_total + new_pct > 100:
                form.add_error('percentage', f'Total nomination cannot exceed 100%. '
                                              f'Currently allocated: {existing_total}%.')
            else:
                nominee = CxEmployeeNominee(employee=employee, **form.cleaned_data)
                nominee.save()
                messages.success(request, f"Nominee '{nominee.nominee_name}' added.")
                return redirect('cxapp_employee_detail', employee_id=employee.employee_id)
    else:
        form = CxEmployeeNomineeForm()

    return render(request, 'Cxapp/employee/employee_nominee_form.html', {
        'form': form, 'employee': employee,
        'allocated_percentage': CxEmployeeNominee.total_percentage(employee),
    })


def cxapp_employee_nominee_delete(request, nominee_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_nominee_delete)(request, nominee_id)


def _nominee_delete(request, nominee_id):
    if not _can_manage_employees(request):
        messages.error(request, 'You do not have permission to edit nominees.')
        return redirect('cxapp_dashboard')

    nominee = get_object_or_404(CxEmployeeNominee, id=nominee_id,
                                 employee__company=request.cx_owner_profile)
    employee_id = nominee.employee_id
    if request.method == 'POST':
        nominee.delete()
        messages.success(request, 'Nominee removed.')
    return redirect('cxapp_employee_detail', employee_id=employee_id)
