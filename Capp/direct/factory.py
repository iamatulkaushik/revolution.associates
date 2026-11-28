"""D5b-3c - Factories Act 1948 records for a DIRECT company.

Factory registration (Form 1 and 2) with certificate PDF; per factory: whitewash register (Form 7),
vessel examination register (Form 8), accident register (Form 26) and the annual return (Form 34),
each with entry screens and a PDF. Leave With Wages (Form 15) is in nominations.py.

Gate (fail-closed): the factory licence number must be on file under Statutory setup
(company_statury.factory). Aapp's get_company_gates() has no 'factory' key, so the check is local to
this module and follows the same rule: number on file = on, blank = off. Everything is scoped to the
company's own factories (a factory of another company is a 404). Registers are legal records: entries
can be added and deleted (audited) but not edited; Form 34 can be edited, and deleted only while Draft.
Aapp's `factory_act` plan feature is not applied. Permissions: statutory.edit, PDFs challan.download.
"""
from datetime import date

from django import forms
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from Aapp.app.employee import employee
from Aapp.app.factory_act import (
    FactoryAccidentRegister, FactoryAnnualReturn, FactoryAnnualReturnForm, FactoryRegistration,
    FactoryRegistrationForm, FactoryVesselExamination, FactoryWhitewashRegister)
from Aapp.app.services import factory_registers as fr
from Aapp.app.services.statutory_files import StatutoryFileError
from Capp.audit import log_action
from Capp.direct.guards import direct_perm
from Sapp.app.company import company_statury

DATE = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')
PERM = 'statutory.edit'
FIRST_YEAR = 2023


def factory_on(company):
    row = company_statury.objects.filter(company=company).first()
    return bool(row and row.factory)


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
class FactoryForm(FactoryRegistrationForm):
    class Meta(FactoryRegistrationForm.Meta):
        widgets = {'license_expiry_date': DATE}
        error_messages = {'factory_license_no': {'unique': 'This licence number is already registered.'}}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _css(self)

    def clean_factory_license_no(self):
        v = self.cleaned_data['factory_license_no'].strip().upper()
        if not v or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/-' for c in v):
            raise forms.ValidationError('Use letters, digits, / and - only.')
        if FactoryRegistration.objects.filter(factory_license_no=v).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This licence number is already registered.')
        return v

    def clean(self):
        d = super().clean()
        _no_negative(self, d, 'total_hp_used', 'max_workers_day', 'max_workers_night')
        if d.get('factory_area_sqm') is not None and d['factory_area_sqm'] <= 0:
            self.add_error('factory_area_sqm', 'Enter the factory area.')
        if not self.errors and d['max_workers_day'] + d['max_workers_night'] <= 0:
            raise forms.ValidationError('Enter the maximum number of workers.')
        return d


class WhitewashForm(forms.ModelForm):
    class Meta:
        model = FactoryWhitewashRegister
        fields = ['area_description', 'type_of_work', 'date_done', 'next_due_date', 'contractor_name']
        widgets = {'date_done': DATE, 'next_due_date': DATE}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _css(self)

    def clean(self):
        d = super().clean()
        _not_future(self, d, 'date_done')
        if d.get('date_done') and d.get('next_due_date') and d['next_due_date'] < d['date_done']:
            self.add_error('next_due_date', 'Next due date cannot be before the date done.')
        return d


class VesselForm(forms.ModelForm):
    class Meta:
        model = FactoryVesselExamination
        fields = ['vessel_description', 'exam_date', 'examiner_name', 'max_permissible_pressure', 'is_fit_for_use']
        widgets = {'exam_date': DATE}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _css(self)
        self.fields['is_fit_for_use'].widget.attrs['class'] = ''

    def clean(self):
        d = super().clean()
        _not_future(self, d, 'exam_date')
        _no_negative(self, d, 'max_permissible_pressure')
        return d


class AccidentForm(forms.ModelForm):
    class Meta:
        model = FactoryAccidentRegister
        fields = ['employee', 'accident_date', 'nature_of_accident', 'injury_description', 'is_fatal',
                  'days_lost', 'reported_to_dish', 'dish_reference_no']
        widgets = {'accident_date': DATE}

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        self.fields['employee'].queryset = employee.objects.filter(CompanyID=company).order_by('name')
        _css(self)
        for n in ('is_fatal', 'reported_to_dish'):
            self.fields[n].widget.attrs['class'] = ''

    def clean(self):
        d = super().clean()
        _not_future(self, d, 'accident_date')
        _no_negative(self, d, 'days_lost')
        if d.get('reported_to_dish') and not (d.get('dish_reference_no') or '').strip():
            self.add_error('dish_reference_no', 'Enter the DISH reference number for a reported accident.')
        return d


class Form34Form(FactoryAnnualReturnForm):
    def __init__(self, *a, factory=None, **k):
        super().__init__(*a, **k)
        self.factory = factory
        _css(self)

    def clean(self):
        d = super().clean()
        _no_negative(self, d, 'total_workers_male', 'total_workers_female', 'total_man_days',
                     'total_overtime_hours', 'total_accidents', 'total_wages_paid')
        y = d.get('year')
        if y is not None:
            if not FIRST_YEAR <= y <= date.today().year:
                self.add_error('year', 'Enter a valid year.')
            elif FactoryAnnualReturn.objects.filter(factory=self.factory, year=y).exclude(pk=self.instance.pk).exists():
                self.add_error('year', f'A Form 34 for {y} already exists for this factory. Edit it instead.')
        if d.get('filing_status') == 'Acknowledged' and not (d.get('acknowledgement_no') or '').strip():
            self.add_error('acknowledgement_no', 'Enter the acknowledgement number.')
        return d


CHILD = {
    'whitewash': {
        'title': 'Whitewash register (Form 7)', 'model': FactoryWhitewashRegister, 'pk': 'whitewash_id',
        'form': WhitewashForm, 'build': fr.build_whitewash_register_pdf,
        'columns': ['Area', 'Type of work', 'Date done', 'Next due', 'Contractor'],
        'row': lambda r: [r.area_description[:60], r.type_of_work, r.date_done, r.next_due_date,
                          r.contractor_name or '—'], 'order': ('-date_done',)},
    'vessels': {
        'title': 'Vessel examination register (Form 8)', 'model': FactoryVesselExamination, 'pk': 'vessel_id',
        'form': VesselForm, 'build': fr.build_vessel_register_pdf,
        'columns': ['Vessel', 'Exam date', 'Examiner', 'Max pressure', 'Status'],
        'row': lambda r: [r.vessel_description[:60], r.exam_date, r.examiner_name, r.max_permissible_pressure,
                          'Fit' if r.is_fit_for_use else 'Not fit'], 'order': ('-exam_date',)},
    'accidents': {
        'title': 'Accident register (Form 26)', 'model': FactoryAccidentRegister, 'pk': 'accident_id',
        'form': AccidentForm, 'build': fr.build_accident_register_pdf, 'company_arg': True,
        'columns': ['Employee', 'Date', 'Nature', 'Fatal', 'Days lost', 'DISH ref'],
        'row': lambda r: [r.employee.name if r.employee else '—', r.accident_date, r.nature_of_accident,
                          'Yes' if r.is_fatal else 'No', r.days_lost, r.dish_reference_no or '—'],
        'order': ('-accident_date',)},
}


def _off_redirect(request, company):
    if factory_on(company):
        return None
    messages.error(request, 'The factory licence number is not on file, so the Factories Act registers '
                            'are off. Add it under Statutory setup.')
    return redirect('capp_dir_factories')


def _factory(company, fid):
    return get_object_or_404(FactoryRegistration, factory_id=fid, company=company)


def _child_cfg(key):
    if key not in CHILD:
        raise Http404('Unknown register.')
    return CHILD[key]


def _pdf(request, pdf_fname, back, label, obj=None):
    pdf, fname = pdf_fname
    log_action(request, 'report.download', obj, label)
    r = HttpResponse(pdf, content_type='application/pdf')
    r['Content-Disposition'] = f'attachment; filename="{fname}"'
    return r


# ── factory registration ──────────────────────────────────────────────────────
@direct_perm(PERM)
def capp_dir_factories(request):
    company = request.owned_company
    on = factory_on(company)
    factories = FactoryRegistration.objects.filter(company=company) if on else []
    return render(request, 'Capp/direct/fac_home.html', {
        'on': on, 'factories': factories, 'today': date.today()})


@direct_perm(PERM)
def capp_dir_factory_add(request):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    form = FactoryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.company = company
        obj.save()
        log_action(request, 'factory.add', obj, obj.factory_license_no)
        messages.success(request, 'Factory registered.')
        return redirect('capp_dir_factories')
    return render(request, 'Capp/direct/register_form.html', {
        'form': form, 'title': 'Register factory (Form 1 and 2)', 'back': reverse('capp_dir_factories')})


@direct_perm(PERM)
def capp_dir_factory_edit(request, fid):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    obj = _factory(company, fid)
    form = FactoryForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        log_action(request, 'factory.edit', obj, obj.factory_license_no)
        messages.success(request, 'Factory updated.')
        return redirect('capp_dir_factories')
    return render(request, 'Capp/direct/register_form.html', {
        'form': form, 'title': f'Edit factory {obj.factory_license_no}', 'back': reverse('capp_dir_factories')})


@direct_perm('challan.download')
def capp_dir_factory_cert(request, fid):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    f = _factory(company, fid)
    try:
        out = fr.build_factory_certificate_pdf(company, f)
    except StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect('capp_dir_factories')
    return _pdf(request, out, None, f'Factory certificate {f.factory_license_no}', f)


# ── whitewash / vessels / accidents ───────────────────────────────────────────
def _child_list_url(fid, key):
    return reverse('capp_dir_fac_list', args=[fid, key])


@direct_perm(PERM)
def capp_dir_fac_list(request, fid, key):
    cfg, company = _child_cfg(key), request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    f = _factory(company, fid)
    qs = cfg['model'].objects.filter(factory=f).order_by(*cfg['order'])
    if cfg.get('company_arg'):
        qs = qs.select_related('employee')
    rows = [{'cells': cfg['row'](r), 'delete_url': reverse('capp_dir_fac_delete', args=[fid, key, getattr(r, cfg['pk'])])}
            for r in qs]
    return render(request, 'Capp/direct/fac_list.html', {
        'title': f'{cfg["title"]}: {f.factory_license_no}', 'columns': cfg['columns'], 'rows': rows,
        'add_url': reverse('capp_dir_fac_add', args=[fid, key]),
        'download_url': reverse('capp_dir_fac_download', args=[fid, key]),
        'back': reverse('capp_dir_factories')})


@direct_perm(PERM)
def capp_dir_fac_add(request, fid, key):
    cfg, company = _child_cfg(key), request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    f = _factory(company, fid)
    kw = {'company': company} if cfg.get('company_arg') else {}
    form = cfg['form'](request.POST or None, **kw)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.factory = f
        obj.save()
        log_action(request, f'factory.{key}.add', obj, f.factory_license_no)
        messages.success(request, 'Entry saved.')
        return redirect(_child_list_url(fid, key))
    return render(request, 'Capp/direct/register_form.html', {
        'form': form, 'title': f'Add: {cfg["title"]}', 'back': _child_list_url(fid, key)})


@direct_perm(PERM)
@require_POST
def capp_dir_fac_delete(request, fid, key, pk):
    cfg, company = _child_cfg(key), request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    f = _factory(company, fid)
    obj = get_object_or_404(cfg['model'], **{cfg['pk']: pk}, factory=f)
    log_action(request, f'factory.{key}.delete', obj, f.factory_license_no)
    obj.delete()
    messages.success(request, 'Entry deleted.')
    return redirect(_child_list_url(fid, key))


@direct_perm('challan.download')
def capp_dir_fac_download(request, fid, key):
    cfg, company = _child_cfg(key), request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    f = _factory(company, fid)
    try:
        out = cfg['build'](company, f)
    except StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect(_child_list_url(fid, key))
    return _pdf(request, out, None, f'{cfg["title"]} {f.factory_license_no}', f)


# ── Form 34 annual return ─────────────────────────────────────────────────────
def _ar_url(fid):
    return reverse('capp_dir_fac_ar', args=[fid])


@direct_perm(PERM)
def capp_dir_fac_ar(request, fid):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    f = _factory(company, fid)
    rows = [{'cells': [r.year, r.total_workers_male, r.total_workers_female, r.total_man_days,
                       r.total_accidents, r.total_wages_paid, r.get_filing_status_display()],
             'edit_url': reverse('capp_dir_fac_ar_edit', args=[fid, r.return_id]),
             'download_url': reverse('capp_dir_fac_ar_download', args=[fid, r.return_id]),
             'delete_url': reverse('capp_dir_fac_ar_delete', args=[fid, r.return_id]) if r.filing_status == 'Draft' else ''}
            for r in FactoryAnnualReturn.objects.filter(factory=f)]
    return render(request, 'Capp/direct/fac_list.html', {
        'title': f'Annual return (Form 34): {f.factory_license_no}',
        'columns': ['Year', 'Male', 'Female', 'Man-days', 'Accidents', 'Wages paid', 'Status'], 'rows': rows,
        'add_url': reverse('capp_dir_fac_ar_add', args=[fid]), 'back': reverse('capp_dir_factories'),
        'note': 'Adding a return pre-fills the figures from your finalized payroll. Payroll is not split by '
                'factory, so check the figures if you have more than one factory.'})


@direct_perm(PERM)
def capp_dir_fac_ar_add(request, fid):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    f = _factory(company, fid)
    initial = {'year': date.today().year - 1}
    try:
        initial['year'] = int(request.GET.get('year', initial['year']))
    except ValueError:
        pass
    if request.method == 'GET':
        initial.update(fr.compute_form34_defaults(company, f, initial['year']))
    form = Form34Form(request.POST or None, factory=f, initial=initial)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.factory = f
        obj.save()
        log_action(request, 'factory.annual-return.add', obj, f'{f.factory_license_no} {obj.year}')
        messages.success(request, 'Annual return saved.')
        return redirect(_ar_url(fid))
    return render(request, 'Capp/direct/register_form.html', {
        'form': form, 'title': f'Add annual return (Form 34): {f.factory_license_no}', 'back': _ar_url(fid)})


@direct_perm(PERM)
def capp_dir_fac_ar_edit(request, fid, pk):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    f = _factory(company, fid)
    rec = get_object_or_404(FactoryAnnualReturn, return_id=pk, factory=f)
    form = Form34Form(request.POST or None, instance=rec, factory=f)
    if request.method == 'POST' and form.is_valid():
        rec = form.save()
        log_action(request, 'factory.annual-return.edit', rec, f'{f.factory_license_no} {rec.year}')
        messages.success(request, 'Annual return updated.')
        return redirect(_ar_url(fid))
    return render(request, 'Capp/direct/register_form.html', {
        'form': form, 'title': f'Edit Form 34 {rec.year}: {f.factory_license_no}', 'back': _ar_url(fid)})


@direct_perm(PERM)
@require_POST
def capp_dir_fac_ar_delete(request, fid, pk):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    f = _factory(company, fid)
    rec = get_object_or_404(FactoryAnnualReturn, return_id=pk, factory=f)
    if rec.filing_status != 'Draft':
        messages.error(request, 'A filed return cannot be deleted.')
        return redirect(_ar_url(fid))
    log_action(request, 'factory.annual-return.delete', rec, f'{f.factory_license_no} {rec.year}')
    rec.delete()
    messages.success(request, 'Annual return deleted.')
    return redirect(_ar_url(fid))


@direct_perm('challan.download')
def capp_dir_fac_ar_download(request, fid, pk):
    company = request.owned_company
    off = _off_redirect(request, company)
    if off:
        return off
    f = _factory(company, fid)
    rec = get_object_or_404(FactoryAnnualReturn, return_id=pk, factory=f)
    try:
        out = fr.build_factory_annual_return_pdf(company, rec)
    except StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect(_ar_url(fid))
    return _pdf(request, out, None, f'Form 34 {f.factory_license_no} {rec.year}', rec)
