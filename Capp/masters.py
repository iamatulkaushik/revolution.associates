"""
Capp/masters.py
===============
Owner-managed masters (Capp only): company details + bank, branch,
department, designation.

Every query is scoped to request.owned_company. Writes need the
`can_manage_masters` flag on CompanyOwnerProfile.
"""
import re
from decimal import Decimal
from functools import wraps

from django import forms
from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from Aapp.app.branch_department import branch, department
from Aapp.app.designation import designation
from Capp.views import owner_required
from Sapp.app.company import Company

IFSC_RE = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')


def masters_required(view_func):
    @wraps(view_func)
    @owner_required
    def _wrapped(request, *args, **kwargs):
        if not request.owner_profile.can_manage_masters:
            messages.error(request, 'You do not have permission to manage masters.')
            return redirect('capp_dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped


def _style(form):
    for f in form.fields.values():
        w = f.widget
        if not isinstance(w, (forms.CheckboxInput, forms.ClearableFileInput)):
            w.attrs.setdefault('class', 'form-control')
    return form


# ── Forms ─────────────────────────────────────────────────────────────────────

class CompanyDetailsForm(forms.ModelForm):
    """Identity fields (name, PAN, dates, state, district, plan) stay locked."""
    class Meta:
        model = Company
        fields = ['tagline1', 'address1', 'address2', 'address3', 'pin',
                  'phone', 'phone2', 'mobile', 'mobile2', 'email1', 'email2',
                  'website', 'tan', 'cin', 'bank_id', 'account', 'ifsc',
                  'branch_address', 'company_logo']

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)

    def _digits(self, name, length):
        v = (self.cleaned_data.get(name) or '').strip()
        if v and not (v.isdigit() and len(v) == length):
            raise forms.ValidationError(f'Enter {length} digits.')
        return v

    def clean_pin(self):     return self._digits('pin', 6)
    def clean_mobile(self):  return self._digits('mobile', 10)
    def clean_mobile2(self): return self._digits('mobile2', 10)
    def clean_phone(self):   return self._digits('phone', 10)
    def clean_phone2(self):  return self._digits('phone2', 10)

    def clean_account(self):
        v = (self.cleaned_data.get('account') or '').strip()
        if v and not (v.isdigit() and 9 <= len(v) <= 18):
            raise forms.ValidationError('Account number: 9 to 18 digits.')
        return v

    def clean_ifsc(self):
        v = (self.cleaned_data.get('ifsc') or '').strip().upper()
        if v and not IFSC_RE.match(v):
            raise forms.ValidationError('Invalid IFSC (e.g. CNRB0001234).')
        return v


class BranchForm(forms.ModelForm):
    class Meta:
        model = branch
        fields = ['branch_name', 'branch_code', 'branch_address', 'branch_email',
                  'contact_person', 'contact_mobile']

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        self.company = company
        _style(self)

    def clean_contact_mobile(self):
        v = (self.cleaned_data.get('contact_mobile') or '').strip()
        if v and not (v.isdigit() and len(v) == 10):
            raise forms.ValidationError('Enter 10 digits.')
        return v

    def clean_branch_name(self):
        v = self.cleaned_data['branch_name'].strip()
        qs = branch.objects.filter(companyid=self.company, branch_name__iexact=v)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('This branch already exists.')
        return v


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = department
        fields = ['department_name', 'branch']

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        self.company = company
        self.fields['branch'].queryset = branch.objects.filter(companyid=company)
        _style(self)

    def clean(self):
        data = super().clean()
        name, br = data.get('department_name'), data.get('branch')
        if name and br:
            qs = department.objects.filter(companyid=self.company, branch=br,
                                           department_name__iexact=name.strip())
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('department_name', 'This department exists in the branch.')
        return data


class DesignationForm(forms.ModelForm):
    REQUIRED = {'designationname', 'basicpay'}

    class Meta:
        model = designation
        exclude = ['company', 'created_by', 'updated_by', 'created_at',
                   'updated_at', 'is_deleted']

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        self.company = company
        for name, f in self.fields.items():
            if isinstance(f, forms.DecimalField) and name not in self.REQUIRED:
                f.required = False
                f.initial = Decimal('0')
        _style(self)

    def clean(self):
        data = super().clean()
        for name, f in self.fields.items():
            if isinstance(f, forms.DecimalField) and data.get(name) is None and name not in self.errors:
                data[name] = Decimal('0')
        nm = (data.get('designationname') or '').strip()
        if nm:
            qs = designation.objects.filter(company=self.company, designationname__iexact=nm,
                                            is_deleted=False)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('designationname', 'This designation already exists.')
        return data


# ── Company details ───────────────────────────────────────────────────────────

@masters_required
def capp_company_details(request):
    company = request.owned_company
    form = CompanyDetailsForm(request.POST or None, request.FILES or None, instance=company)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.updated_at = timezone.now()
        obj.updated_by = request.user.username
        obj.save()
        messages.success(request, 'Company details saved.')
        return redirect('capp_company_details')
    return render(request, 'Capp/masters/form.html', {
        'form': form, 'page_title': 'Company Details & Bank', 'multipart': True,
        'cancel_url': 'capp_dashboard',
        'locked': [('Company', company.company_name), ('PAN', company.pan),
                   ('Plan', company.get_plan_display())],
    })


# ── Generic CRUD plumbing ─────────────────────────────────────────────────────

def _list(request, *, title, qs, columns, row, add_url, edit_name, delete_name, pk):
    rows = [{'pk': getattr(o, pk), 'cells': row(o)} for o in qs]
    return render(request, 'Capp/masters/list.html', {
        'page_title': title, 'columns': columns, 'rows': rows, 'add_url': add_url,
        'edit_name': edit_name, 'delete_name': delete_name,
    })


def _edit(request, *, form_cls, instance, title, list_name, save):
    company = request.owned_company
    form = form_cls(request.POST or None, instance=instance, company=company) \
        if form_cls is not CompanyDetailsForm else form_cls(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        save(form.save(commit=False))
        form.save_m2m()
        messages.success(request, f'{title} saved.')
        return redirect(list_name)
    return render(request, 'Capp/masters/form.html', {
        'form': form, 'page_title': title, 'cancel_url': list_name})


def _delete(request, *, obj, label, list_name, remover=None):
    if request.method == 'POST':
        try:
            remover(obj) if remover else obj.delete()
            messages.success(request, f'{label} deleted.')
        except ProtectedError:
            messages.error(request, f'{label} is in use by employees and cannot be deleted.')
        return redirect(list_name)
    return render(request, 'Capp/masters/confirm_delete.html', {
        'label': label, 'cancel_url': list_name})


# ── Branch ────────────────────────────────────────────────────────────────────

@masters_required
def capp_branch_list(request):
    qs = branch.objects.filter(companyid=request.owned_company).order_by('branch_name')
    return _list(request, title='Branches', qs=qs, pk='branchid',
                 columns=['Name', 'Code', 'Contact', 'Mobile'],
                 row=lambda b: [b.branch_name, b.branch_code, b.contact_person, b.contact_mobile],
                 add_url='capp_branch_add', edit_name='capp_branch_edit',
                 delete_name='capp_branch_delete')


@masters_required
def capp_branch_edit(request, pk=None):
    company = request.owned_company
    inst = get_object_or_404(branch, branchid=pk, companyid=company) if pk else None

    def save(o):
        if not o.pk:
            o.companyid, o.created_by = company, request.user
        o.updated_by = request.user
        o.save()
    return _edit(request, form_cls=BranchForm, instance=inst,
                 title='Edit Branch' if pk else 'Add Branch',
                 list_name='capp_branch_list', save=save)


@masters_required
def capp_branch_delete(request, pk):
    obj = get_object_or_404(branch, branchid=pk, companyid=request.owned_company)
    return _delete(request, obj=obj, label=f'Branch "{obj.branch_name}"',
                   list_name='capp_branch_list')


# ── Department ────────────────────────────────────────────────────────────────

@masters_required
def capp_department_list(request):
    qs = department.objects.filter(companyid=request.owned_company) \
        .select_related('branch').order_by('branch__branch_name', 'department_name')
    return _list(request, title='Departments', qs=qs, pk='departmentid',
                 columns=['Department', 'Branch'],
                 row=lambda d: [d.department_name, d.branch.branch_name],
                 add_url='capp_department_add', edit_name='capp_department_edit',
                 delete_name='capp_department_delete')


@masters_required
def capp_department_edit(request, pk=None):
    company = request.owned_company
    inst = get_object_or_404(department, departmentid=pk, companyid=company) if pk else None

    def save(o):
        if not o.pk:
            o.companyid, o.created_by = company, request.user
        o.updated_by = request.user
        o.save()
    return _edit(request, form_cls=DepartmentForm, instance=inst,
                 title='Edit Department' if pk else 'Add Department',
                 list_name='capp_department_list', save=save)


@masters_required
def capp_department_delete(request, pk):
    obj = get_object_or_404(department, departmentid=pk, companyid=request.owned_company)
    return _delete(request, obj=obj, label=f'Department "{obj.department_name}"',
                   list_name='capp_department_list')


# ── Designation ───────────────────────────────────────────────────────────────

@masters_required
def capp_designation_list(request):
    qs = designation.objects.filter(company=request.owned_company, is_deleted=False) \
        .order_by('designationname')
    return _list(request, title='Designations', qs=qs, pk='designationid',
                 columns=['Designation', 'Daily wage?', 'Basic', 'HRA', 'DA', 'Active'],
                 row=lambda d: [d.designationname, 'Yes' if d.is_dailywage else 'No',
                                d.basicpay, d.hra, d.da, 'Yes' if d.is_active else 'No'],
                 add_url='capp_designation_add', edit_name='capp_designation_edit',
                 delete_name='capp_designation_delete')


@masters_required
def capp_designation_edit(request, pk=None):
    company = request.owned_company
    inst = get_object_or_404(designation, designationid=pk, company=company,
                             is_deleted=False) if pk else None

    def save(o):
        if not o.pk:
            o.company, o.created_by = company, request.user.username
        o.updated_by = request.user.username
        o.save()
    return _edit(request, form_cls=DesignationForm, instance=inst,
                 title='Edit Designation' if pk else 'Add Designation',
                 list_name='capp_designation_list', save=save)


@masters_required
def capp_designation_delete(request, pk):
    obj = get_object_or_404(designation, designationid=pk, company=request.owned_company,
                            is_deleted=False)

    def soft(o):
        if o.employee_set.exists():
            raise ProtectedError('in use', set())
        o.is_deleted, o.is_active = True, False
        o.updated_by = request.user.username
        o.save()
    return _delete(request, obj=obj, label=f'Designation "{obj.designationname}"',
                   list_name='capp_designation_list', remover=soft)
