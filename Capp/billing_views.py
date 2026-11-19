"""Capp/billing_views.py — employee deductions + billing clients (owner-managed)."""
import re
from datetime import date
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from Aapp.app.employee import employee
from Capp.billing_models import BillingClient, ClientEmployee, EmployeeDeduction
from Capp.masters import masters_required, _list, _edit, _delete, _style

GSTIN_RE = re.compile(r'^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]$')


class MonthField(forms.DateField):
    widget = forms.DateInput(format='%Y-%m', attrs={'type': 'month'})

    def __init__(self, **kw):
        super().__init__(input_formats=['%Y-%m', '%Y-%m-%d'], **kw)

    def clean(self, value):
        v = super().clean(value)
        return v.replace(day=1) if v else v


class DeductionForm(forms.ModelForm):
    employee = forms.ModelChoiceField(queryset=employee.objects.none())
    start_month = MonthField(label='Start month')

    class Meta:
        model = EmployeeDeduction
        fields = ['employee', 'title', 'kind', 'total_amount', 'emi_amount',
                  'start_month', 'is_paused', 'is_closed', 'remarks']

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        self.company = company
        self.fields['employee'].queryset = employee.objects.filter(
            CompanyID=company, is_working=True).order_by('name')
        self.fields['employee'].label_from_instance = lambda e: f'{e.employeecode} — {e.name}'
        self.fields['emi_amount'].help_text = 'Loan/advance: amount cut every month.'
        if self.instance.pk:                       # edit: money and identity are fixed
            for f in ('employee', 'kind', 'total_amount', 'start_month'):
                self.fields[f].disabled = True
        else:
            del self.fields['is_paused'], self.fields['is_closed']
        _style(self)

    def clean(self):
        d = super().clean()
        kind, total, emi = d.get('kind'), d.get('total_amount'), d.get('emi_amount')
        if total is not None and total <= 0:
            self.add_error('total_amount', 'Must be above zero.')
        if kind == 'RECURRING':
            if not emi or emi <= 0:
                self.add_error('emi_amount', 'EMI is required for loan/advance.')
            elif total and emi > total:
                self.add_error('emi_amount', 'EMI cannot exceed the total.')
        elif kind == 'ONCE':
            d['emi_amount'] = None
        return d


class BillingClientForm(forms.ModelForm):
    employees = forms.ModelMultipleChoiceField(
        queryset=employee.objects.none(), required=False,
        help_text='Employees deployed here. An employee already mapped to another client is moved.')

    class Meta:
        model = BillingClient
        fields = ['name', 'gstin', 'address', 'service_charge_pct', 'gst_pct', 'esi_base', 'is_active']

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        self.company = company
        self.fields['employees'].queryset = employee.objects.filter(
            CompanyID=company, is_working=True).order_by('name')
        self.fields['employees'].label_from_instance = lambda e: f'{e.employeecode} — {e.name}'
        if self.instance.pk:
            self.fields['employees'].initial = list(
                self.instance.deployed.values_list('employee_id', flat=True))
        self.fields['esi_base'].help_text = 'ESI is calculated on Basic or on Gross (never on overtime).'
        _style(self)

    def clean_gstin(self):
        v = (self.cleaned_data.get('gstin') or '').strip().upper()
        if v and not GSTIN_RE.match(v):
            raise forms.ValidationError('Invalid GSTIN.')
        return v

    def _pct(self, name):
        v = self.cleaned_data.get(name)
        if v is not None and not (0 <= v <= 100):
            raise forms.ValidationError('Between 0 and 100.')
        return v

    def clean_service_charge_pct(self): return self._pct('service_charge_pct')
    def clean_gst_pct(self):            return self._pct('gst_pct')

    def clean_name(self):
        v = self.cleaned_data['name'].strip()
        qs = BillingClient.objects.filter(company=self.company, name__iexact=v)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('This client already exists.')
        return v


# ── Deductions ────────────────────────────────────────────────────────────────

@masters_required
def capp_deduction_list(request):
    qs = EmployeeDeduction.objects.filter(company=request.owned_company) \
        .select_related('employee').order_by('is_closed', '-start_month', 'employee__name')

    def status(d):
        return 'Closed' if d.is_closed else 'Paused' if d.is_paused else 'Active'
    return _list(request, title='Deductions', qs=qs, pk='pk',
                 columns=['Employee', 'Title', 'Type', 'Total', 'EMI', 'Balance', 'From', 'Status'],
                 row=lambda d: [f'{d.employee.employeecode} {d.employee.name}', d.title,
                                'Loan/Advance' if d.kind == 'RECURRING' else 'One-time',
                                d.total_amount, d.emi_amount, d.balance,
                                d.start_month.strftime('%b %Y'), status(d)],
                 add_url='capp_deduction_add', edit_name='capp_deduction_edit',
                 delete_name='capp_deduction_delete')


@masters_required
def capp_deduction_edit(request, pk=None):
    company = request.owned_company
    inst = get_object_or_404(EmployeeDeduction, pk=pk, company=company) if pk else None

    def save(o):
        if not o.pk:
            o.company, o.balance = company, o.total_amount
        o.save()
    return _edit(request, form_cls=DeductionForm, instance=inst,
                 title='Edit Deduction' if pk else 'Add Deduction',
                 list_name='capp_deduction_list', save=save)


@masters_required
def capp_deduction_delete(request, pk):
    obj = get_object_or_404(EmployeeDeduction, pk=pk, company=request.owned_company)
    if obj.last_applied:
        messages.error(request, 'Already deducted in payroll. Close it instead of deleting.')
        return redirect('capp_deduction_list')
    return _delete(request, obj=obj, label=f'Deduction "{obj.title}"',
                   list_name='capp_deduction_list')


# ── Billing clients ───────────────────────────────────────────────────────────

@masters_required
def capp_client_list(request):
    qs = BillingClient.objects.filter(company=request.owned_company).order_by('name')
    return _list(request, title='Billing Clients', qs=qs, pk='pk',
                 columns=['Client', 'GSTIN', 'Service %', 'GST %', 'ESI on', 'Active'],
                 row=lambda c: [c.name, c.gstin, c.service_charge_pct, c.gst_pct,
                                c.get_esi_base_display(), 'Yes' if c.is_active else 'No'],
                 add_url='capp_client_add', edit_name='capp_client_edit',
                 delete_name='capp_client_delete')


@masters_required
def capp_client_edit(request, pk=None):
    company = request.owned_company
    inst = get_object_or_404(BillingClient, pk=pk, company=company) if pk else None

    def save(o):
        o.company = company
        o.save()
        picked = request.POST.getlist('employees')
        ClientEmployee.objects.filter(company=company, client=o).exclude(
            employee_id__in=picked).delete()
        for eid in picked:
            emp = employee.objects.filter(pk=eid, CompanyID=company).first()
            if emp:
                ClientEmployee.objects.update_or_create(
                    employee=emp, defaults={'company': company, 'client': o})
    return _edit(request, form_cls=BillingClientForm, instance=inst,
                 title='Edit Client' if pk else 'Add Client',
                 list_name='capp_client_list', save=save)


@masters_required
def capp_client_delete(request, pk):
    obj = get_object_or_404(BillingClient, pk=pk, company=request.owned_company)
    return _delete(request, obj=obj, label=f'Client "{obj.name}"', list_name='capp_client_list')
