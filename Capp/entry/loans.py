"""
Capp/entry/loans.py — loans and advances entry (track AI-3, package E3).

Writes the existing Aapp `Loan` / `Advance` models; the schedule and the monthly
deduction stay inside those models (golden-tested against Aapp's own form).
Plan gate: `loans` needs silver or above (revolution.app.plan_gate), same as Aapp.
Lock rule D7 applies to the deduction START month.
"""
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from Aapp.app.employee import employee
from Aapp.app.loan_schedule_pdf import loan_advance_schedule_pdf
from Aapp.app.loans_advances import MONTH_CHOICES, Advance, Loan
from Capp.access import capp_perm, has_perm
from Capp.audit import log_action
from Capp.entry.gates import entry_lock_reason
from Capp.masters import _style
from revolution.app.plan_gate import has_feature

KINDS = {
    'loans': {'model': Loan, 'label': 'Loan', 'plural': 'Loans', 'note_field': 'purpose', 'pk': 'loan_id'},
    'advances': {'model': Advance, 'label': 'Advance', 'plural': 'Advances', 'note_field': 'reason', 'pk': 'advance_id'},
}


def _kind(kind):
    if kind not in KINDS:
        raise Http404('Unknown kind.')
    return KINDS[kind]


def _plan_ok(request):
    if has_feature(request.owned_company, 'loans'):
        return True
    messages.warning(request, f"Loans and advances need the Silver plan or above "
                              f"(you are on {request.owned_company.get_plan_display()}).")
    return False


class LoanAdvanceForm(forms.ModelForm):
    class Meta:
        fields = ['employee', 'principal_amount', 'interest_rate_annual', None, 'deduction_mode',
                  'number_of_instalments', 'fixed_deduction_amount', 'deduction_start_month',
                  'deduction_start_year', 'remarks']

    def __init__(self, *a, company=None, mode='ASSOCIATE', **k):
        super().__init__(*a, **k)
        self.company, self.mode = company, mode
        self.fields['employee'].queryset = employee.objects.filter(
            CompanyID=company, is_working=True).order_by('employeecode')   # always company-scoped
        self.fields['employee'].label_from_instance = lambda e: f'{e.employeecode} — {e.name}'
        self.fields['deduction_start_month'].widget = forms.Select(choices=MONTH_CHOICES)
        self.fields['number_of_instalments'].help_text = 'Needed for "Fixed Number of Instalments".'
        self.fields['fixed_deduction_amount'].help_text = 'Needed for "Fixed Deduction Amount".'
        if self.instance.pk:
            self.fields['employee'].disabled = True
            self.fields['principal_amount'].disabled = True          # the schedule is built on it
        _style(self)

    def clean_principal_amount(self):
        v = self.cleaned_data['principal_amount']
        if v is not None and v <= 0:
            raise forms.ValidationError('Must be above zero.')
        return v

    def clean_interest_rate_annual(self):
        v = self.cleaned_data.get('interest_rate_annual') or Decimal('0')
        if not (0 <= v <= 60):
            raise forms.ValidationError('Between 0 and 60.')
        return v

    def clean_number_of_instalments(self):
        v = self.cleaned_data.get('number_of_instalments')
        if v is not None and not (1 <= v <= 120):
            raise forms.ValidationError('Between 1 and 120.')
        return v

    def clean_deduction_start_year(self):
        v = self.cleaned_data['deduction_start_year']
        if not (2000 <= v <= 2100):
            raise forms.ValidationError('Enter a valid year.')
        return v

    def clean(self):
        d = super().clean()
        mode, fixed, p = d.get('deduction_mode'), d.get('fixed_deduction_amount'), d.get('principal_amount')
        if mode == 'fixed_amount' and fixed is not None:
            if fixed <= 0:
                self.add_error('fixed_deduction_amount', 'Must be above zero.')
            elif p and fixed > p:
                self.add_error('fixed_deduction_amount', 'Cannot exceed the principal.')
        m, y = d.get('deduction_start_month'), d.get('deduction_start_year')
        if m and y:
            lock = entry_lock_reason(self.company, self.mode, int(m), int(y))
            if lock:
                self.add_error('deduction_start_month',
                               lock.replace('Entry is closed', 'This start month is closed'))
        return d


def _form_class(kind):
    cfg = _kind(kind)
    fields = [cfg['note_field'] if f is None else f for f in LoanAdvanceForm.Meta.fields]
    meta = type('Meta', (), {'model': cfg['model'], 'fields': fields})
    return type(f"{cfg['label']}Form", (LoanAdvanceForm,), {'Meta': meta})


def _get(request, kind, pk):
    cfg = _kind(kind)
    return get_object_or_404(cfg['model'], **{cfg['pk']: pk, 'company': request.owned_company})


@capp_perm('loans.view')
def capp_ent_loan_list(request, kind):
    cfg = _kind(kind)
    if not _plan_ok(request):
        return redirect('capp_dashboard')
    rows = cfg['model'].objects.filter(company=request.owned_company).select_related('employee') \
        .order_by('-created_at')
    return render(request, 'Capp/entry/loans_list.html', {
        'page_title': cfg['plural'], 'kind': kind, 'cfg': cfg,
        'rows': [{'obj': o, 'pk': getattr(o, cfg['pk'])} for o in rows],
        'can_edit': has_perm(request, 'loans.edit')})


@capp_perm('loans.edit')
def capp_ent_loan_edit(request, kind, pk=None):
    cfg = _kind(kind)
    if not _plan_ok(request):
        return redirect('capp_dashboard')
    company = request.owned_company
    inst = _get(request, kind, pk) if pk else None
    if inst is not None:
        lock = entry_lock_reason(company, request.capp_mode, int(inst.deduction_start_month),
                                 int(inst.deduction_start_year))
        if lock and request.method == 'POST':
            messages.error(request, lock)
            return redirect('capp_ent_loan_list', kind=kind)
    form = _form_class(kind)(request.POST or None, instance=inst, company=company, mode=request.capp_mode)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        created = obj.pk is None
        if created:
            obj.company, obj.created_by = company, request.user.username
        obj.save()
        log_action(request, 'create' if created else 'update', obj,
                   f'{cfg["label"]} {obj.employee.employeecode} {obj.principal_amount}')
        messages.success(request, f'{cfg["label"]} saved.')
        return redirect('capp_ent_loan_list', kind=kind)
    return render(request, 'Capp/masters/form.html', {
        'form': form, 'page_title': f'{"Edit" if pk else "Add"} {cfg["label"]}',
        'cancel_url': 'capp_ent_loan_list', 'cancel_href': reverse('capp_ent_loan_list', kwargs={'kind': kind})})


@capp_perm('loans.view')
def capp_ent_loan_schedule(request, kind, pk):
    cfg = _kind(kind)
    if not _plan_ok(request):
        return redirect('capp_dashboard')
    obj = _get(request, kind, pk)
    return render(request, 'Capp/entry/loan_schedule.html', {
        'page_title': f'{cfg["label"]} schedule', 'obj': obj, 'kind': kind, 'cfg': cfg, 'pk': pk,
        'schedule': obj.amortization_schedule()})


@capp_perm('loans.view')
def capp_ent_loan_pdf(request, kind, pk):
    if not _plan_ok(request):
        return redirect('capp_dashboard')
    obj = _get(request, kind, pk)
    return HttpResponse(loan_advance_schedule_pdf(obj), content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="{kind}_schedule_{pk}.pdf"'})


@capp_perm('loans.edit')
def capp_ent_loan_stop(request, kind, pk):
    """Stop = status cancelled (never delete: the history stays)."""
    cfg = _kind(kind)
    obj = _get(request, kind, pk)
    if request.method == 'POST' and obj.status == 'active':
        obj.status = 'cancelled'
        obj.save(update_fields=['status', 'updated_at'])
        log_action(request, 'stop', obj, f'{cfg["label"]} {obj.employee.employeecode}')
        messages.success(request, f'{cfg["label"]} stopped.')
    return redirect('capp_ent_loan_list', kind=kind)
