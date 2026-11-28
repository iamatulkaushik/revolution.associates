"""D5b-3d - Contract Labour (Regulation and Abolition) Act 1970 records for a DIRECT company.

The company as principal employer: registration (Forms I and II), register of contractors (Form IV),
contract workers deployed under each contractor (Form XII), contractor payments with a payment
register PDF, employment cards (Form XIII), service certificates (Form XIV) and the half-yearly
return Form 20(CL), with a PDF for each.

Gate (fail-closed): the Labour licence number is on file under Statutory setup (get_company_gates
'labour') or an active registration with a certificate number has been recorded here. The
registration screen itself is always open, since it is how the certificate is recorded. Everything is
scoped to the company's own contractors and employees (another company's record is a 404, and every
employee choice is limited to this company on POST as well as GET). Aapp's `contract_labour` plan
feature is not applied.

Records: payments, cards and certificates can be added and deleted (audited) but not edited; a
worker's deployment can be ended; a contractor with any records cannot be deleted. The Form 20(CL)
is pre-filled from FINALIZED payroll (APPROVED or PAID) of the contractor's workers; a filed return
cannot be recomputed or deleted. Permissions: statutory.edit for records, payroll.process for returns,
challan.download for PDFs.
"""
import re
from datetime import date, timedelta
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from Aapp.app.contract_labour import (
    ContractEmploymentCard, ContractLabourHalfYearlyReturn, ContractLabourRegistration,
    ContractServiceCertificate)
from Aapp.app.contractor import (
    PAYMENT_SCHEDULE_CHOICES, contractor, contractor_payment, contractor_worker)
from Aapp.app.employee import employee
from Aapp.app.services import contract_labour_registers as cl
from Aapp.app.services.statutory_files import StatutoryFileError
from Aapp.app.statutory_gates import get_company_gates
from Capp.audit import log_action
from Capp.direct.guards import direct_perm

DATE = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')
PERM = 'statutory.edit'
FIRST_YEAR = 2023
PAN_RE = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]$')
GSTIN_RE = re.compile(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$')
HALF_END = {'jan_jun': (6, 30), 'jul_dec': (12, 31)}


def cl_on(company):
    if get_company_gates(company)['labour']:
        return True
    return ContractLabourRegistration.objects.filter(
        company=company, is_active=True).exclude(registration_cert_no='').exists()


def half_end(year, half):
    m, d = HALF_END[half]
    return date(year, m, d)


def _css(form):
    for f in form.fields.values():
        f.widget.attrs.setdefault('class', 'form-control')


def _not_future(form, d, *names):
    for n in names:
        if d.get(n) and d[n] > date.today():
            form.add_error(n, 'Date cannot be in the future.')


def _no_negative(form, d, *names):
    for n in names:
        if d.get(n) is not None and d[n] < 0:
            form.add_error(n, 'Cannot be negative.')


# ── forms ─────────────────────────────────────────────────────────────────────
class RegistrationForm(forms.ModelForm):
    class Meta:
        model = ContractLabourRegistration
        fields = ['registration_cert_no', 'registration_date', 'registration_authority',
                  'establishment_name', 'nature_of_work', 'max_contract_workers', 'is_active']
        widgets = {'registration_date': DATE}

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        self.company = company
        _css(self)
        self.fields['is_active'].widget.attrs['class'] = ''
        self.fields['registration_cert_no'].required = True
        self.fields['registration_date'].required = True

    def clean_registration_cert_no(self):
        v = self.cleaned_data['registration_cert_no'].strip().upper()
        if ContractLabourRegistration.objects.filter(
                company=self.company, registration_cert_no=v).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This certificate number is already recorded.')
        return v

    def clean(self):
        d = super().clean()
        _not_future(self, d, 'registration_date')
        if d.get('max_contract_workers') is not None and d['max_contract_workers'] <= 0:
            self.add_error('max_contract_workers', 'Enter the maximum number of contract workers.')
        return d


class ContractorForm(forms.ModelForm):
    payment_schedule = forms.ChoiceField(choices=PAYMENT_SCHEDULE_CHOICES)

    class Meta:
        model = contractor
        fields = ['contractor_name', 'contractor_license_no', 'contractor_address', 'contractor_mobile',
                  'contractor_email', 'contractor_pan', 'contractor_gstin', 'work_description',
                  'contract_start_date', 'contract_end_date', 'contract_amount', 'payment_schedule',
                  'max_contract_workers', 'worksite_address', 'status']
        widgets = {'contract_start_date': DATE, 'contract_end_date': DATE,
                   'contractor_address': forms.Textarea(attrs={'rows': 2}),
                   'worksite_address': forms.Textarea(attrs={'rows': 2}),
                   'work_description': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        self.company = company
        _css(self)
        self.fields['contractor_license_no'].required = True
        self.fields['contractor_address'].required = True

    def clean_contractor_license_no(self):
        v = self.cleaned_data['contractor_license_no'].strip().upper()
        if contractor.objects.filter(company=self.company, contractor_license_no=v).exclude(
                pk=self.instance.pk).exists():
            raise forms.ValidationError('Another contractor has this licence number.')
        return v

    def clean_contractor_pan(self):
        v = self.cleaned_data['contractor_pan'].strip().upper()
        if v and not PAN_RE.match(v):
            raise forms.ValidationError('Enter a valid PAN, for example ABCDE1234F.')
        return v

    def clean_contractor_gstin(self):
        v = self.cleaned_data['contractor_gstin'].strip().upper()
        if v and not GSTIN_RE.match(v):
            raise forms.ValidationError('Enter a valid 15-character GSTIN.')
        return v

    def clean_contractor_mobile(self):
        v = self.cleaned_data['contractor_mobile'].strip()
        if v and not re.match(r'^[6-9][0-9]{9}$', v):
            raise forms.ValidationError('Enter a 10-digit mobile number.')
        return v

    def clean(self):
        d = super().clean()
        s, e = d.get('contract_start_date'), d.get('contract_end_date')
        if s and e and e < s:
            self.add_error('contract_end_date', 'Contract end cannot be before the start.')
        _no_negative(self, d, 'contract_amount')
        n = d.get('max_contract_workers')
        if n is not None and n <= 0:
            self.add_error('max_contract_workers', 'Enter the maximum number of workers.')
        reg = ContractLabourRegistration.objects.filter(company=self.company, is_active=True).order_by(
            '-max_contract_workers').first()
        if n and reg and reg.max_contract_workers and n > reg.max_contract_workers:
            self.add_error('max_contract_workers',
                           f'More than the {reg.max_contract_workers} workers your registration allows.')
        return d


class _ScopedForm(forms.ModelForm):
    """Forms of one contractor of one company; employee choices come from that company only."""
    deployed_only = False

    def __init__(self, *a, company=None, con=None, **k):
        super().__init__(*a, **k)
        self.company, self.con = company, con
        if 'employee' in self.fields:
            qs = employee.objects.filter(CompanyID=company)
            if self.deployed_only:
                qs = qs.filter(contractor_deployments__contractor=con).distinct()
            else:
                qs = qs.filter(is_working=True)
            self.fields['employee'].queryset = qs.order_by('name')
        _css(self)


class WorkerForm(_ScopedForm):
    class Meta:
        model = contractor_worker
        fields = ['employee', 'deployment_start', 'deployment_end', 'work_description']
        widgets = {'deployment_start': DATE, 'deployment_end': DATE}

    def clean(self):
        d = super().clean()
        emp, s, e = d.get('employee'), d.get('deployment_start'), d.get('deployment_end')
        if s and e and e < s:
            self.add_error('deployment_end', 'Deployment end cannot be before the start.')
        if emp and s and not self.errors:
            far = date.max
            clash = contractor_worker.objects.filter(company=self.company, employee=emp).filter(
                deployment_start__lte=e or far).filter(Q(deployment_end__isnull=True) | Q(deployment_end__gte=s))
            if clash.exists():
                raise forms.ValidationError(
                    'This worker is already deployed under a contractor for part of that period.')
        return d


class PaymentForm(_ScopedForm):
    class Meta:
        model = contractor_payment
        fields = ['salary_month', 'salary_year', 'payment_amount', 'payment_date',
                  'payment_reference', 'remarks']
        widgets = {'payment_date': DATE}

    def clean(self):
        d = super().clean()
        m, y = d.get('salary_month'), d.get('salary_year')
        if m is not None and not 1 <= m <= 12:
            self.add_error('salary_month', 'Month must be 1 to 12.')
        if y is not None and not FIRST_YEAR <= y <= date.today().year + 1:
            self.add_error('salary_year', 'Enter a valid year.')
        if d.get('payment_amount') is not None and d['payment_amount'] <= 0:
            self.add_error('payment_amount', 'Enter an amount above zero.')
        _not_future(self, d, 'payment_date')
        return d


class CardForm(_ScopedForm):
    deployed_only = True

    class Meta:
        model = ContractEmploymentCard
        fields = ['employee', 'card_number', 'token_number', 'work_description', 'work_site',
                  'wage_rate', 'issue_date', 'validity_date']
        widgets = {'issue_date': DATE, 'validity_date': DATE,
                   'work_description': forms.Textarea(attrs={'rows': 2})}

    def clean(self):
        d = super().clean()
        _no_negative(self, d, 'wage_rate')
        _not_future(self, d, 'issue_date')
        if d.get('issue_date') and d.get('validity_date') and d['validity_date'] < d['issue_date']:
            self.add_error('validity_date', 'Validity cannot be before the issue date.')
        n = (d.get('card_number') or '').strip()
        if n and ContractEmploymentCard.objects.filter(company=self.company, card_number=n).exists():
            self.add_error('card_number', 'This card number is already used.')
        return d


class CertForm(_ScopedForm):
    deployed_only = True

    class Meta:
        model = ContractServiceCertificate
        fields = ['employee', 'work_description', 'work_site', 'date_of_employment',
                  'date_of_termination', 'reason_for_termination', 'last_wage_paid', 'certificate_date']
        widgets = {'date_of_employment': DATE, 'date_of_termination': DATE, 'certificate_date': DATE,
                   'work_description': forms.Textarea(attrs={'rows': 2})}

    def clean(self):
        d = super().clean()
        _no_negative(self, d, 'last_wage_paid')
        _not_future(self, d, 'certificate_date')
        s, e, c = d.get('date_of_employment'), d.get('date_of_termination'), d.get('certificate_date')
        if s and e and e < s:
            self.add_error('date_of_termination', 'Termination cannot be before the date of employment.')
        if e and c and c < e:
            self.add_error('certificate_date', 'Certificate date cannot be before the termination date.')
        return d


class ReturnForm(_ScopedForm):
    class Meta:
        model = ContractLabourHalfYearlyReturn
        fields = ['year', 'half_year', 'total_workers_employed', 'total_man_days', 'total_wages_paid',
                  'total_overtime_hours', 'total_overtime_wages', 'filing_status', 'filed_date',
                  'acknowledgement_no']
        widgets = {'filed_date': DATE}

    def clean(self):
        d = super().clean()
        _no_negative(self, d, 'total_wages_paid', 'total_overtime_wages')
        y, h = d.get('year'), d.get('half_year')
        if y is not None and h:
            if not FIRST_YEAR <= y <= date.today().year:
                self.add_error('year', 'Enter a valid year.')
            elif half_end(y, h) >= date.today():
                self.add_error('half_year', 'That half year has not closed yet.')
            elif ContractLabourHalfYearlyReturn.objects.filter(
                    contractor=self.con, year=y, half_year=h).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError(
                    'A return for this contractor and half year already exists. Edit it instead.')
            elif d.get('filed_date') and d['filed_date'] < half_end(y, h):
                self.add_error('filed_date', 'Filed date cannot be before the half year closes.')
        _not_future(self, d, 'filed_date')
        if d.get('filing_status') == 'filed' and not d.get('filed_date'):
            self.add_error('filed_date', 'Enter the date it was filed.')
        if d.get('filing_status') != 'filed' and (d.get('filed_date') or d.get('acknowledgement_no')):
            self.add_error('filing_status', 'Set the status to Filed to record a filing date or acknowledgement.')
        return d


CHILD = {
    'workers': {
        'title': 'Contract workers (Form XII)', 'model': contractor_worker, 'pk': 'cw_id', 'form': WorkerForm,
        'columns': ['Name', 'Code', 'Deployed from', 'Deployed to', 'Work'],
        'row': lambda r: [r.employee.name, r.employee.employeecode, r.deployment_start,
                          r.deployment_end or 'Current', (r.work_description or '—')[:40]],
        'order': ('-deployment_start',), 'select': 'employee'},
    'payments': {
        'title': 'Contractor payments', 'model': contractor_payment, 'pk': 'payment_id', 'form': PaymentForm,
        'columns': ['Month/Year', 'Amount', 'Paid on', 'Reference', 'Remarks'],
        'row': lambda r: [f'{r.salary_month}/{r.salary_year}', r.payment_amount, r.payment_date,
                          r.payment_reference or '—', (r.remarks or '—')[:40]],
        'order': ('-payment_date',), 'list_pdf': cl.build_contractor_payment_register_pdf},
    'cards': {
        'title': 'Employment cards (Form XIII)', 'model': ContractEmploymentCard, 'pk': 'card_id',
        'form': CardForm, 'row_pdf': cl.build_employment_card_pdf,
        'columns': ['Worker', 'Card no.', 'Token', 'Wage rate', 'Issued', 'Valid till'],
        'row': lambda r: [r.employee.name, r.card_number or '—', r.token_number or '—', r.wage_rate,
                          r.issue_date, r.validity_date or '—'],
        'order': ('-issue_date',), 'select': 'employee'},
    'certificates': {
        'title': 'Service certificates (Form XIV)', 'model': ContractServiceCertificate, 'pk': 'cert_id',
        'form': CertForm, 'row_pdf': cl.build_service_certificate_pdf,
        'columns': ['Worker', 'Employed', 'Terminated', 'Last wage', 'Certificate date'],
        'row': lambda r: [r.employee.name, r.date_of_employment, r.date_of_termination, r.last_wage_paid,
                          r.certificate_date],
        'order': ('-certificate_date',), 'select': 'employee'},
}


# ── helpers ───────────────────────────────────────────────────────────────────
HOME = 'capp_dir_cl'


def _off_redirect(request, company):
    if cl_on(company):
        return None
    messages.error(request, 'The Labour licence number is not on file and no registration certificate '
                            'is recorded, so contract labour records are off. Add the licence under '
                            'Statutory setup or record the registration certificate here.')
    return redirect(HOME)


def _con(company, cid):
    return get_object_or_404(contractor, contractor_id=cid, company=company)


def _cfg(key):
    if key not in CHILD:
        raise Http404('Unknown register.')
    return CHILD[key]


def _pdf(request, out, label, obj):
    pdf, fname = out
    log_action(request, 'report.download', obj, label)
    r = HttpResponse(pdf, content_type='application/pdf')
    r['Content-Disposition'] = f'attachment; filename="{fname}"'
    return r


def _form_page(request, form, title, back):
    return render(request, 'Capp/direct/register_form.html', {'form': form, 'title': title, 'back': back})


# ── hub, registration ─────────────────────────────────────────────────────────
@direct_perm(PERM)
def capp_dir_cl(request):
    company = request.owned_company
    on = cl_on(company)
    return render(request, 'Capp/direct/cl_home.html', {
        'on': on, 'regs': ContractLabourRegistration.objects.filter(company=company),
        'contractors': contractor.objects.filter(company=company) if on else [], 'today': date.today()})


@direct_perm(PERM)
def capp_dir_cl_reg_add(request):
    company = request.owned_company
    form = RegistrationForm(request.POST or None, company=company,
                            initial={'establishment_name': company.company_name})
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.company, obj.created_by = company, request.user
        obj.save()
        log_action(request, 'contract.registration.add', obj, obj.registration_cert_no)
        messages.success(request, 'Registration recorded.')
        return redirect(HOME)
    return _form_page(request, form, 'Record registration (Form I and II)', reverse(HOME))


@direct_perm(PERM)
def capp_dir_cl_reg_edit(request, pk):
    company = request.owned_company
    obj = get_object_or_404(ContractLabourRegistration, reg_id=pk, company=company)
    form = RegistrationForm(request.POST or None, instance=obj, company=company)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        log_action(request, 'contract.registration.edit', obj, obj.registration_cert_no)
        messages.success(request, 'Registration updated.')
        return redirect(HOME)
    return _form_page(request, form, f'Edit registration {obj.registration_cert_no}', reverse(HOME))


@direct_perm(PERM)
@require_POST
def capp_dir_cl_reg_delete(request, pk):
    obj = get_object_or_404(ContractLabourRegistration, reg_id=pk, company=request.owned_company)
    log_action(request, 'contract.registration.delete', obj, obj.registration_cert_no)
    obj.delete()
    messages.success(request, 'Registration deleted.')
    return redirect(HOME)


@direct_perm('challan.download')
def capp_dir_cl_reg_pdf(request, pk):
    company = request.owned_company
    obj = get_object_or_404(ContractLabourRegistration, reg_id=pk, company=company)
    try:
        out = cl.build_cl_registration_pdf(company, obj)
    except StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect(HOME)
    return _pdf(request, out, f'CL registration {obj.registration_cert_no}', obj)


# ── contractors (Form IV) ─────────────────────────────────────────────────────
@direct_perm(PERM)
def capp_dir_cl_con_add(request):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    form = ContractorForm(request.POST or None, company=company)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.company, obj.created_by = company, request.user
        obj.principal_employer = company.company_name
        obj.save()
        log_action(request, 'contract.contractor.add', obj, obj.contractor_name)
        messages.success(request, 'Contractor added.')
        return redirect(HOME)
    return _form_page(request, form, 'Add contractor (Form IV)', reverse(HOME))


@direct_perm(PERM)
def capp_dir_cl_con_edit(request, cid):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    con = _con(company, cid)
    form = ContractorForm(request.POST or None, instance=con, company=company)
    if request.method == 'POST' and form.is_valid():
        con = form.save(commit=False)
        con.updated_by = request.user
        con.save()
        log_action(request, 'contract.contractor.edit', con, con.contractor_name)
        messages.success(request, 'Contractor updated.')
        return redirect(HOME)
    return _form_page(request, form, f'Edit contractor {con.contractor_name}', reverse(HOME))


@direct_perm(PERM)
@require_POST
def capp_dir_cl_con_delete(request, cid):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    con = _con(company, cid)
    if (con.workers.exists() or con.payments.exists() or con.employment_cards.exists()
            or con.service_certificates.exists() or con.halfyearly_returns.exists()):
        messages.error(request, 'This contractor has workers, payments, cards, certificates or returns, so '
                                'it cannot be deleted. Set its status to Completed or Terminated instead.')
        return redirect(HOME)
    log_action(request, 'contract.contractor.delete', con, con.contractor_name)
    con.delete()
    messages.success(request, 'Contractor deleted.')
    return redirect(HOME)


# ── workers, payments, cards, certificates ────────────────────────────────────
def _list_url(cid, key):
    return reverse('capp_dir_cl_list', args=[cid, key])


@direct_perm(PERM)
def capp_dir_cl_list(request, cid, key):
    cfg, company = _cfg(key), request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    con = _con(company, cid)
    qs = cfg['model'].objects.filter(contractor=con).order_by(*cfg['order'])
    if cfg.get('select'):
        qs = qs.select_related(cfg['select'])
    rows = []
    for r in qs:
        pk = getattr(r, cfg['pk'])
        rows.append({
            'cells': cfg['row'](r),
            'download_url': reverse('capp_dir_cl_pdf', args=[cid, key, pk]) if cfg.get('row_pdf') else '',
            'end_url': (reverse('capp_dir_cl_worker_end', args=[cid, pk])
                        if key == 'workers' and not r.deployment_end else ''),
            'delete_url': reverse('capp_dir_cl_delete', args=[cid, key, pk])})
    return render(request, 'Capp/direct/cl_list.html', {
        'title': f'{cfg["title"]}: {con.contractor_name}', 'columns': cfg['columns'], 'rows': rows,
        'add_url': reverse('capp_dir_cl_add', args=[cid, key]),
        'download_url': reverse('capp_dir_cl_list_pdf', args=[cid, key]) if cfg.get('list_pdf') else '',
        'back': reverse(HOME)})


@direct_perm(PERM)
def capp_dir_cl_add(request, cid, key):
    cfg, company = _cfg(key), request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    con = _con(company, cid)
    form = cfg['form'](request.POST or None, company=company, con=con)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.contractor, obj.company, obj.created_by = con, company, request.user
        obj.save()
        log_action(request, f'contract.{key}.add', obj, con.contractor_name)
        messages.success(request, 'Entry saved.')
        return redirect(_list_url(cid, key))
    return _form_page(request, form, f'Add: {cfg["title"]}', _list_url(cid, key))


@direct_perm(PERM)
@require_POST
def capp_dir_cl_delete(request, cid, key, pk):
    cfg, company = _cfg(key), request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    con = _con(company, cid)
    obj = get_object_or_404(cfg['model'], **{cfg['pk']: pk}, contractor=con)
    if key == 'workers' and (
            ContractEmploymentCard.objects.filter(contractor=con, employee=obj.employee).exists()
            or ContractServiceCertificate.objects.filter(contractor=con, employee=obj.employee).exists()):
        messages.error(request, 'This worker has an employment card or service certificate under this '
                                'contractor, so the deployment cannot be deleted. End it instead.')
        return redirect(_list_url(cid, key))
    log_action(request, f'contract.{key}.delete', obj, con.contractor_name)
    obj.delete()
    messages.success(request, 'Entry deleted.')
    return redirect(_list_url(cid, key))


@direct_perm(PERM)
@require_POST
def capp_dir_cl_worker_end(request, cid, pk):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    con = _con(company, cid)
    w = get_object_or_404(contractor_worker, cw_id=pk, contractor=con)
    if w.deployment_end:
        messages.error(request, 'This deployment has already ended.')
    elif w.deployment_start > date.today():
        messages.error(request, 'This deployment has not started yet. Delete it instead.')
    else:
        w.deployment_end = date.today()
        w.save()
        log_action(request, 'contract.workers.end', w, con.contractor_name)
        messages.success(request, 'Deployment ended today.')
    return redirect(_list_url(cid, 'workers'))


@direct_perm('challan.download')
def capp_dir_cl_pdf(request, cid, key, pk):
    cfg, company = _cfg(key), request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    if not cfg.get('row_pdf'):
        raise Http404('No PDF for this register.')
    con = _con(company, cid)
    obj = get_object_or_404(cfg['model'], **{cfg['pk']: pk}, contractor=con)
    try:
        out = cfg['row_pdf'](company, obj)
    except StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect(_list_url(cid, key))
    return _pdf(request, out, f'{cfg["title"]} {con.contractor_name}', obj)


@direct_perm('challan.download')
def capp_dir_cl_list_pdf(request, cid, key):
    cfg, company = _cfg(key), request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    if not cfg.get('list_pdf'):
        raise Http404('No PDF for this register.')
    con = _con(company, cid)
    try:
        out = cfg['list_pdf'](company, con)
    except StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect(_list_url(cid, key))
    return _pdf(request, out, f'{cfg["title"]} {con.contractor_name}', con)


# ── Form 20(CL) half-yearly return ────────────────────────────────────────────
def _ret_url(cid):
    return reverse('capp_dir_cl_ret', args=[cid])


def _status(r):
    if r.filing_status == 'pending' and date.today() > half_end(r.year, r.half_year) + timedelta(days=30):
        return 'Overdue'
    return r.get_filing_status_display()


@direct_perm('payroll.process')
def capp_dir_cl_ret(request, cid):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    con = _con(company, cid)
    rows = []
    for r in ContractLabourHalfYearlyReturn.objects.filter(contractor=con):
        filed = r.filing_status == 'filed'
        rows.append({
            'cells': [r.year, r.get_half_year_display(), r.total_workers_employed, r.total_man_days,
                      r.total_wages_paid, _status(r), r.filed_date or '—'],
            'edit_url': reverse('capp_dir_cl_ret_edit', args=[cid, r.return_id]),
            'download_url': reverse('capp_dir_cl_ret_pdf', args=[cid, r.return_id]),
            'delete_url': '' if filed else reverse('capp_dir_cl_ret_delete', args=[cid, r.return_id]),
            'recompute_url': '' if filed else reverse('capp_dir_cl_ret_recompute', args=[cid, r.return_id])})
    return render(request, 'Capp/direct/cl_list.html', {
        'title': f'Half-yearly return (Form 20-CL): {con.contractor_name}',
        'columns': ['Year', 'Half year', 'Workers', 'Man-days', 'Wages paid', 'Status', 'Filed on'],
        'rows': rows, 'add_url': reverse('capp_dir_cl_ret_add', args=[cid]), 'back': reverse(HOME),
        'note': 'Adding a return pre-fills the figures from your finalized payroll for the workers deployed '
                'under this contractor. The return is due within 30 days of the half year closing.'})


@direct_perm('payroll.process')
def capp_dir_cl_ret_add(request, cid):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    con = _con(company, cid)
    today = date.today()
    year, half = (today.year, 'jan_jun') if today.month > 6 else (today.year - 1, 'jul_dec')
    if request.method == 'GET':
        try:
            year = int(request.GET.get('year', year))
        except ValueError:
            pass
        half = request.GET.get('half_year', half)
        initial = {'year': year, 'half_year': half}
        if half in cl.HALF_MONTHS:
            initial.update(cl.compute_cl_half_year_totals(company, con, year, half))
        initial['filing_status'] = 'pending'
    else:
        initial = None
    form = ReturnForm(request.POST or None, company=company, con=con, initial=initial)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.contractor, obj.company, obj.created_by = con, company, request.user
        obj.save()
        log_action(request, 'contract.return.add', obj, f'{con.contractor_name} {obj.year} {obj.half_year}')
        messages.success(request, 'Return saved.')
        return redirect(_ret_url(cid))
    return _form_page(request, form, f'Add half-yearly return (Form 20-CL): {con.contractor_name}', _ret_url(cid))


@direct_perm('payroll.process')
def capp_dir_cl_ret_edit(request, cid, pk):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    con = _con(company, cid)
    rec = get_object_or_404(ContractLabourHalfYearlyReturn, return_id=pk, contractor=con)
    form = ReturnForm(request.POST or None, instance=rec, company=company, con=con)
    if request.method == 'POST' and form.is_valid():
        rec = form.save()
        log_action(request, 'contract.return.edit', rec, f'{con.contractor_name} {rec.year} {rec.half_year}')
        messages.success(request, 'Return updated.')
        return redirect(_ret_url(cid))
    return _form_page(request, form, f'Edit Form 20-CL {rec.year}: {con.contractor_name}', _ret_url(cid))


@direct_perm('payroll.process')
@require_POST
def capp_dir_cl_ret_recompute(request, cid, pk):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    con = _con(company, cid)
    rec = get_object_or_404(ContractLabourHalfYearlyReturn, return_id=pk, contractor=con)
    if rec.filing_status == 'filed':
        messages.error(request, 'A filed return cannot be recomputed.')
        return redirect(_ret_url(cid))
    for k, v in cl.compute_cl_half_year_totals(company, con, rec.year, rec.half_year).items():
        setattr(rec, k, v)
    rec.save()
    log_action(request, 'contract.return.recompute', rec, f'{con.contractor_name} {rec.year} {rec.half_year}')
    messages.success(request, 'Figures recomputed from finalized payroll.')
    return redirect(_ret_url(cid))


@direct_perm('payroll.process')
@require_POST
def capp_dir_cl_ret_delete(request, cid, pk):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    con = _con(company, cid)
    rec = get_object_or_404(ContractLabourHalfYearlyReturn, return_id=pk, contractor=con)
    if rec.filing_status == 'filed':
        messages.error(request, 'A filed return cannot be deleted.')
        return redirect(_ret_url(cid))
    log_action(request, 'contract.return.delete', rec, f'{con.contractor_name} {rec.year} {rec.half_year}')
    rec.delete()
    messages.success(request, 'Return deleted.')
    return redirect(_ret_url(cid))


@direct_perm('challan.download')
def capp_dir_cl_ret_pdf(request, cid, pk):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    con = _con(company, cid)
    rec = get_object_or_404(ContractLabourHalfYearlyReturn, return_id=pk, contractor=con)
    try:
        out = cl.build_cl_return_pdf(company, rec)
    except StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect(_ret_url(cid))
    return _pdf(request, out, f'Form 20-CL {con.contractor_name} {rec.year} {rec.half_year}', rec)
