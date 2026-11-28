"""D6 - relieving an employee and the Full and Final settlement, for a DIRECT company.

Relieve (employees.relieve): an employee is marked left with a leaving date (today or earlier, not before
joining) and a reason, so payroll stops including them. A relieved employee can be reinstated while no
settlement exists. Settlement (employees.relieve to create/edit/delete, payroll.finalize to finalize and
mark paid, payroll.download for PDFs): one settlement per employee, for a relieved employee only; the
last working day is the leaving date. The figures come from Aapp's FnFSettlement.compute() through
services/fnf.py (leave encashment, notice pay, gratuity with the statutory ceiling, loan and advance
balance, pending asset recoveries); the owner adds pending salary, other deductions and any asset
recovery raised outside the asset module. Flow: Draft (editable, recomputable, deletable) -> Finalized
(locked) -> Paid (pending asset recoveries become recovered and active loans and advances are completed).
The settlement statement is available from Draft; the experience and character certificates from
Finalized; the last pay certificate only once Paid. Everything is scoped to the company's own employees.
"""
from datetime import date

from django import forms
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from Aapp.app.employee import employee
from Aapp.app.fnf_settlement import FnFSettlement
from Aapp.app.services import fnf as svc
from Aapp.app.services.statutory_files import StatutoryFileError
from Capp.audit import log_action
from Capp.direct.guards import direct_perm

HOME = 'capp_dir_fnf'
RELIEVE = 'employees.relieve'


def _css(form):
    for f in form.fields.values():
        f.widget.attrs.setdefault('class', 'form-control')


class RelieveForm(forms.Form):
    employee = forms.ModelChoiceField(queryset=employee.objects.none())
    dateofleaving = forms.DateField(label='Date of leaving (last working day)',
                                    widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    leaving_reason = forms.CharField(max_length=255, label='Reason for leaving')

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        self.fields['employee'].queryset = employee.objects.filter(CompanyID=company, is_working=True).order_by('name')
        _css(self)

    def clean(self):
        d = super().clean()
        emp, when = d.get('employee'), d.get('dateofleaving')
        if when and when > date.today():
            self.add_error('dateofleaving', 'The leaving date cannot be in the future.')
        elif emp and when and emp.dateofjoining and when < emp.dateofjoining:
            self.add_error('dateofleaving', 'The leaving date cannot be before the date of joining.')
        return d


class SettlementForm(forms.ModelForm):
    class Meta:
        model = FnFSettlement
        fields = ['employee', 'notice_period_days_required', 'notice_period_days_served',
                  'pending_salary', 'other_deductions', 'asset_recovery_amount', 'remarks']
        labels = {'asset_recovery_amount': 'Asset recovery raised outside the asset module',
                  'pending_salary': 'Unpaid salary up to the last working day'}
        help_texts = {'asset_recovery_amount': 'Pending recoveries in the asset module are added automatically.'}

    def __init__(self, *a, company=None, fixed=False, **k):
        super().__init__(*a, **k)
        if fixed:
            del self.fields['employee']
        else:
            self.fields['employee'].queryset = employee.objects.filter(
                CompanyID=company, is_working=False, dateofleaving__isnull=False,
                fnf_settlements__isnull=True).order_by('name')
        _css(self)

    def clean(self):
        d = super().clean()
        for n in ('pending_salary', 'other_deductions', 'asset_recovery_amount'):
            if d.get(n) is not None and d[n] < 0:
                self.add_error(n, 'Cannot be negative.')
        for n in ('notice_period_days_required', 'notice_period_days_served'):
            if d.get(n) is not None and d[n] > 365:
                self.add_error(n, 'Enter the number of days (365 at most).')
        return d


def _settlement(company, pk):
    return get_object_or_404(FnFSettlement.objects.select_related('employee'), settlement_id=pk, company=company)


def _form_page(request, form, title, back):
    return render(request, 'Capp/direct/register_form.html', {'form': form, 'title': title, 'back': back})


def _view_url(pk):
    return reverse('capp_dir_fnf_view', args=[pk])


def _draft_only(request, s):
    if s.status != 'draft':
        messages.error(request, 'Only a draft settlement can be changed.')
        return redirect(_view_url(s.settlement_id))
    return None


# ── hub and relieving ─────────────────────────────────────────────────────────
@direct_perm(RELIEVE)
def capp_dir_fnf(request):
    company = request.owned_company
    waiting = employee.objects.filter(CompanyID=company, is_working=False, dateofleaving__isnull=False,
                                      fnf_settlements__isnull=True).order_by('-dateofleaving')
    return render(request, 'Capp/direct/fnf_home.html', {
        'settlements': FnFSettlement.objects.filter(company=company).select_related('employee'),
        'waiting': waiting})


@direct_perm(RELIEVE)
def capp_dir_relieve(request):
    company = request.owned_company
    form = RelieveForm(request.POST or None, company=company)
    if request.method == 'POST' and form.is_valid():
        emp = svc.relieve_employee(form.cleaned_data['employee'], form.cleaned_data['dateofleaving'],
                                   form.cleaned_data['leaving_reason'])
        log_action(request, 'employee.relieve', emp, f'{emp.employeecode} {emp.dateofleaving}')
        messages.success(request, f'{emp.name} relieved. You can now start the final settlement.')
        return redirect(HOME)
    return _form_page(request, form, 'Relieve an employee', reverse(HOME))


@direct_perm(RELIEVE)
@require_POST
def capp_dir_reinstate(request, eid):
    company = request.owned_company
    emp = get_object_or_404(employee, employeeid=eid, CompanyID=company, is_working=False)
    if FnFSettlement.objects.filter(employee=emp).exists():
        messages.error(request, 'A settlement exists for this employee, so they cannot be reinstated.')
        return redirect(HOME)
    emp.is_working, emp.dateofleaving, emp.leaving_reason = True, None, ''
    emp.save()
    log_action(request, 'employee.reinstate', emp, emp.employeecode)
    messages.success(request, f'{emp.name} reinstated.')
    return redirect(HOME)


# ── settlement ────────────────────────────────────────────────────────────────
@direct_perm(RELIEVE)
def capp_dir_fnf_add(request):
    company = request.owned_company
    initial = {}
    if request.GET.get('employee', '').isdigit():
        initial['employee'] = int(request.GET['employee'])
    form = SettlementForm(request.POST or None, company=company, initial=initial)
    if request.method == 'POST' and form.is_valid():
        s = form.save(commit=False)
        s.company, s.created_by = company, request.user.username
        s.last_working_day = s.employee.dateofleaving
        svc.compute_settlement(s, form.cleaned_data['asset_recovery_amount'])
        s.save()
        log_action(request, 'fnf.add', s, s.employee.employeecode)
        messages.success(request, 'Settlement calculated. Review it before finalizing.')
        return redirect(_view_url(s.settlement_id))
    return _form_page(request, form, 'Start final settlement', reverse(HOME))


@direct_perm(RELIEVE)
def capp_dir_fnf_edit(request, pk):
    company = request.owned_company
    s = _settlement(company, pk)
    locked = _draft_only(request, s)
    if locked:
        return locked
    form = SettlementForm(request.POST or None, instance=s, company=company, fixed=True,
                          initial={'asset_recovery_amount': svc.manual_asset_part(s)})
    if request.method == 'POST' and form.is_valid():
        s = form.save(commit=False)
        svc.compute_settlement(s, form.cleaned_data['asset_recovery_amount'])
        s.save()
        log_action(request, 'fnf.edit', s, s.employee.employeecode)
        messages.success(request, 'Settlement updated and recalculated.')
        return redirect(_view_url(pk))
    return _form_page(request, form, f'Edit settlement: {s.employee.name}', _view_url(pk))


@direct_perm(RELIEVE)
@require_POST
def capp_dir_fnf_recompute(request, pk):
    s = _settlement(request.owned_company, pk)
    locked = _draft_only(request, s)
    if locked:
        return locked
    svc.compute_settlement(s, svc.manual_asset_part(s))
    s.save()
    log_action(request, 'fnf.recompute', s, s.employee.employeecode)
    messages.success(request, 'Figures recalculated from the latest records.')
    return redirect(_view_url(pk))


@direct_perm(RELIEVE)
@require_POST
def capp_dir_fnf_delete(request, pk):
    s = _settlement(request.owned_company, pk)
    locked = _draft_only(request, s)
    if locked:
        return locked
    log_action(request, 'fnf.delete', s, s.employee.employeecode)
    s.delete()
    messages.success(request, 'Draft settlement deleted.')
    return redirect(HOME)


@direct_perm('payroll.finalize')
@require_POST
def capp_dir_fnf_finalize(request, pk):
    s = _settlement(request.owned_company, pk)
    locked = _draft_only(request, s)
    if locked:
        return locked
    svc.finalize_settlement(s)
    log_action(request, 'fnf.finalize', s, s.employee.employeecode)
    messages.success(request, 'Settlement finalized.')
    return redirect(_view_url(pk))


@direct_perm('payroll.finalize')
@require_POST
def capp_dir_fnf_paid(request, pk):
    s = _settlement(request.owned_company, pk)
    if s.status != 'finalized':
        messages.error(request, 'Only a finalized settlement can be marked paid.')
        return redirect(_view_url(pk))
    svc.mark_paid(s)
    log_action(request, 'fnf.paid', s, s.employee.employeecode)
    messages.success(request, 'Marked paid. Pending asset recoveries are now recovered and loans cleared.')
    return redirect(_view_url(pk))


@direct_perm(RELIEVE)
def capp_dir_fnf_view(request, pk):
    s = _settlement(request.owned_company, pk)
    certs = [('experience', 'Experience certificate', s.status in ('finalized', 'paid')),
             ('character', 'Character certificate', s.status in ('finalized', 'paid')),
             ('last_pay', 'Last pay certificate', s.status == 'paid')]
    return render(request, 'Capp/direct/fnf_detail.html', {'s': s, 'certs': certs})


def _pdf(request, out, label, obj):
    pdf, fname = out
    log_action(request, 'report.download', obj, label)
    r = HttpResponse(pdf, content_type='application/pdf')
    r['Content-Disposition'] = f'attachment; filename="{fname}"'
    return r


@direct_perm('payroll.download')
def capp_dir_fnf_pdf(request, pk):
    s = _settlement(request.owned_company, pk)
    try:
        out = svc.build_fnf_statement_pdf(s)
    except StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect(_view_url(pk))
    return _pdf(request, out, f'FnF statement {s.employee.employeecode}', s)


@direct_perm('payroll.download')
def capp_dir_fnf_cert(request, pk, cert_type):
    if cert_type not in svc.CERT_TYPES:
        raise Http404('Unknown certificate type')
    s = _settlement(request.owned_company, pk)
    ready = s.status == 'paid' if cert_type == 'last_pay' else s.status in ('finalized', 'paid')
    if not ready:
        messages.error(request, 'This certificate is not available yet. The last pay certificate needs a '
                                'paid settlement; the others need it finalized.')
        return redirect(_view_url(pk))
    try:
        out = svc.build_fnf_certificate_pdf(s, cert_type)
    except StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect(_view_url(pk))
    return _pdf(request, out, f'{cert_type} certificate {s.employee.employeecode}', s)
