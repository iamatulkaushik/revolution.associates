"""
Capp/entry/employees.py — add, edit and reactivate employees (track AI-3, package E1).

Writes the existing Aapp `employee` model (no copy). Permissions: employees.add for
add and reactivate (reactivating counts as adding, so the plan limit applies),
employees.edit for edit. Relieving an employee is DIRECT-only and belongs to AI-2.
"""
import re

from django import forms
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from Aapp.app.branch_department import branch, department
from Aapp.app.designation import designation
from Aapp.app.employee import employee
from Capp.access import capp_perm
from Capp.audit import log_action
from Capp.masters import _style
from revolution.app.plan_limits import PlanLimitExceeded, check_can_add
from Sapp.app.state_district import District, State

IFSC_RE = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')
PAN_RE = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]$')

SECTIONS = [
    ('Identity', ['employeecode', 'name', 'fathername', 'mothername', 'gender', 'dateofbirth',
                  'maritalstatus']),
    ('Contact', ['mobile', 'phone', 'email']),
    ('Current address', ['temporaryaddress', 'temp_state', 'temp_district', 'temp_pincode']),
    ('Permanent address', ['same_as_permanent', 'permanentaddress', 'perm_state', 'perm_district',
                           'perm_pincode']),
    ('Identity documents', ['aadhar_number', 'aadhar_name', 'pan_number', 'pan_name']),
    ('Bank', ['bank_name', 'bank_account', 'bank_ifsc']),
    ('Employment', ['dateofjoining', 'employment_type', 'contract_start_date', 'contract_end_date',
                    'designationID', 'departmentID', 'branchID']),
    ('Statutory numbers', ['uan_number', 'epf_memberID', 'esic_number']),
]
FIELDS = [f for _, fs in SECTIONS for f in fs]
DATE_FIELDS = ('dateofbirth', 'dateofjoining', 'contract_start_date', 'contract_end_date')


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = employee
        fields = FIELDS
        widgets = {f: forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d') for f in DATE_FIELDS}

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        self.company = company
        for f in DATE_FIELDS:
            self.fields[f].input_formats = ['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y']
        for f in ('email', 'temp_pincode', 'temp_state', 'temp_district', 'fathername'):
            self.fields[f].required = False          # the owner's sheets rarely carry these
        self.fields['branchID'].queryset = branch.objects.filter(companyid=company)
        self.fields['departmentID'].queryset = department.objects.filter(companyid=company)
        self.fields['designationID'].queryset = designation.objects.filter(
            company=company, is_deleted=False, is_active=True)
        for f, label in (('branchID', 'Branch'), ('departmentID', 'Department'),
                         ('designationID', 'Designation')):
            self.fields[f].label = label
        self.fields['temp_district'].queryset = District.objects.select_related('state').order_by('name')
        self.fields['perm_district'].queryset = District.objects.select_related('state').order_by('name')
        if self.instance.pk:
            self.fields['employeecode'].disabled = True      # the code is the payroll key
        _style(self)

    def _digits(self, name, lengths):
        v = (self.cleaned_data.get(name) or '').strip()
        if v and not (v.isdigit() and len(v) in lengths):
            raise forms.ValidationError('Enter ' + ' or '.join(str(n) for n in lengths) + ' digits.')
        return v

    def clean_employeecode(self):
        v = (self.cleaned_data.get('employeecode') or '').strip()
        if not v:
            raise forms.ValidationError('Required.')
        return v

    def clean_mobile(self):
        v = self._digits('mobile', (10,))
        if not v:
            raise forms.ValidationError('Required.')
        return v

    def clean_aadhar_number(self):
        v = self._digits('aadhar_number', (12,))
        if not v:
            raise forms.ValidationError('Required.')
        return v

    def clean_bank_account(self):
        v = (self.cleaned_data.get('bank_account') or '').strip()
        if not (v.isdigit() and 9 <= len(v) <= 18):
            raise forms.ValidationError('Account number: 9 to 18 digits.')
        return v

    def clean_bank_ifsc(self):
        v = (self.cleaned_data.get('bank_ifsc') or '').strip().upper()
        if not IFSC_RE.match(v):
            raise forms.ValidationError('Invalid IFSC (e.g. CNRB0001234).')
        return v

    def clean_pan_number(self):
        v = (self.cleaned_data.get('pan_number') or '').strip().upper()
        if v and not PAN_RE.match(v):
            raise forms.ValidationError('Invalid PAN (e.g. ABCDE1234F).')
        return v or None                              # unique + null: blank must be NULL

    def clean_esic_number(self):
        return self._digits('esic_number', (10, 17))

    def clean_name(self):
        return self.cleaned_data['name'].strip().upper()

    def clean(self):
        d = super().clean()
        dob, doj = d.get('dateofbirth'), d.get('dateofjoining')
        if dob and doj and doj < dob:
            self.add_error('dateofjoining', 'Joining date cannot be before date of birth.')
        br, dp = d.get('branchID'), d.get('departmentID')
        if br and dp and dp.branch_id != br.pk:
            self.add_error('departmentID', 'This department belongs to another branch.')
        if d.get('employment_type') == 'Contract':
            s, e = d.get('contract_start_date'), d.get('contract_end_date')
            if not (s and e):
                self.add_error('contract_end_date', 'Contract start and end dates are required.')
            elif e < s:
                self.add_error('contract_end_date', 'End date is before the start date.')
        return d


def _render_form(request, form, title):
    return render(request, 'Capp/entry/employee_form.html', {
        'form': form, 'page_title': title,
        'sections': [(label, [form[f] for f in fs]) for label, fs in SECTIONS]})


@capp_perm('employees.add')
def capp_ent_emp_add(request):
    company = request.owned_company
    form = EmployeeForm(request.POST or None, company=company)
    if request.method == 'POST' and form.is_valid():
        try:
            check_can_add(company)
        except PlanLimitExceeded as e:
            form.add_error(None, str(e))
        else:
            emp = form.save(commit=False)
            emp.CompanyID = company
            emp.is_working = True
            emp.save()
            log_action(request, 'create', emp, f'{emp.employeecode} {emp.name}')
            messages.success(request, f'Employee {emp.employeecode} added.')
            return redirect('capp_employee_detail', pk=emp.employeeid)
    return _render_form(request, form, 'Add Employee')


@capp_perm('employees.edit')
def capp_ent_emp_edit(request, pk):
    company = request.owned_company
    emp = get_object_or_404(employee, employeeid=pk, CompanyID=company)
    form = EmployeeForm(request.POST or None, instance=emp, company=company)
    if request.method == 'POST' and form.is_valid():
        form.save()
        log_action(request, 'update', emp, f'{emp.employeecode} {emp.name}')
        messages.success(request, f'Employee {emp.employeecode} saved.')
        return redirect('capp_employee_detail', pk=emp.employeeid)
    return _render_form(request, form, f'Edit Employee {emp.employeecode}')


@capp_perm('employees.add')
def capp_ent_emp_relieved(request):
    """Relieved employees with a Reactivate button (counts toward the plan limit)."""
    rows = employee.objects.filter(CompanyID=request.owned_company, is_working=False) \
        .order_by('employeecode')
    return render(request, 'Capp/entry/employees_relieved.html', {
        'page_title': 'Relieved Employees', 'employees': rows})


@capp_perm('employees.add')
def capp_ent_emp_reactivate(request, pk):
    company = request.owned_company
    emp = get_object_or_404(employee, employeeid=pk, CompanyID=company)
    if request.method == 'POST' and not emp.is_working:
        try:
            check_can_add(company)
        except PlanLimitExceeded as e:
            messages.error(request, str(e))
        else:
            emp.is_working = True
            emp.dateofleaving = None
            emp.leaving_reason = ''
            emp.save()
            log_action(request, 'reactivate', emp, f'{emp.employeecode} {emp.name}')
            messages.success(request, f'Employee {emp.employeecode} reactivated.')
    return redirect('capp_ent_emp_relieved')


@capp_perm('employees.view')
def capp_ent_districts(request):
    """JSON: districts of a state, for the dependent dropdowns on the employee form."""
    try:
        state_id = int(request.GET.get('state', ''))
    except ValueError:
        return JsonResponse({'districts': []})
    qs = District.objects.filter(state_id=state_id).order_by('name').values('Districtid', 'name')
    return JsonResponse({'districts': [{'id': d['Districtid'], 'name': d['name']} for d in qs]})
