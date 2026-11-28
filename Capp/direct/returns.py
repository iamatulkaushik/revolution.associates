"""D5b-3a - annual returns for a DIRECT company: Minimum Wages Form V and Payment of Wages Form IV and Bonus Form D.

A return is generated for a calendar year from the company's FINALIZED payroll (batches APPROVED or
PAID; draft and processed batches are ignored, unlike Aapp which counts every batch). Fines,
deductions and overtime are limited to those same months. The owner then sets the wage rates / wage
period / payment mode and records the filing (status, date, acknowledgement). A filed return cannot
be recomputed or deleted. Min Wages and Payment of Wages have no registration number in company
statutory setup, so there is no registration gate (same as the D5a wages-act reports).
Permissions: entry payroll.process, PDF challan.download. This hub is where later return families
(bonus, factory, contract labour) register.
"""
from datetime import date

from django import forms
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from Aapp.app.bonus import BonusReturnEditForm, bonus_annual_return
from Aapp.app.services import bonus_returns as br
from Aapp.app.services import wage_returns as wr
from Aapp.app.services.statutory_files import StatutoryFileError
from Aapp.app.wage_compliance import (
    MinimumWagesAnnualReturn, MinimumWagesEditForm, PaymentOfWagesAnnualReturn, PaymentOfWagesEditForm)
from Capp.audit import log_action
from Capp.direct.guards import direct_perm

DATE = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')
FIRST_YEAR = 2023


def _years():
    return list(range(date.today().year, FIRST_YEAR - 1, -1))


class _EditMixin:
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        for f in self.fields.values():
            f.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        d = super().clean()
        filed = d.get('filing_status') == 'filed'
        if filed and not d.get('filed_date'):
            self.add_error('filed_date', 'Enter the date it was filed.')
        if d.get('filed_date') and d['filed_date'] > date.today():
            self.add_error('filed_date', 'Date cannot be in the future.')
        self._filed = filed
        return d


class MinWagesEditForm(_EditMixin, MinimumWagesEditForm):
    class Meta(MinimumWagesEditForm.Meta):
        widgets = {'filed_date': DATE}

    def clean(self):
        d = super().clean()
        d['category_of_work'] = (d.get('category_of_work') or '').strip()
        rates = ('min_wage_rate_unskilled', 'min_wage_rate_semiskilled', 'min_wage_rate_skilled')
        for r in rates:
            if d.get(r) is not None and d[r] < 0:
                self.add_error(r, 'Cannot be negative.')
        if self._filed and not self.errors and any(not d.get(r) for r in rates):
            raise forms.ValidationError('Enter all three minimum wage rates before marking the return as filed.')
        return d


class PowEditForm(_EditMixin, PaymentOfWagesEditForm):
    class Meta(PaymentOfWagesEditForm.Meta):
        widgets = {'filed_date': DATE}


class BonusEditForm(_EditMixin, BonusReturnEditForm):
    class Meta(BonusReturnEditForm.Meta):
        widgets = {'payment_date': DATE, 'filed_date': DATE}

    def clean(self):
        d = super().clean()
        if d.get('allocable_surplus') is not None and d['allocable_surplus'] < 0:
            self.add_error('allocable_surplus', 'Cannot be negative.')
        if self._filed and not d.get('payment_date'):
            self.add_error('payment_date', 'Enter the bonus payment date before marking the return as filed.')
        return d


class GenerateForm(forms.Form):
    year = forms.TypedChoiceField(coerce=int, label='Year')
    category_of_work = forms.CharField(max_length=255, required=False, label='Category of work')

    def __init__(self, *a, needs_category=False, **k):
        super().__init__(*a, **k)
        self.needs_category = needs_category
        self.fields['year'].choices = [(y, y) for y in _years()]
        if needs_category:
            self.fields['category_of_work'].required = True
            self.fields['category_of_work'].help_text = 'Category of scheduled employment, as in Form V.'
        else:
            del self.fields['category_of_work']
        for f in self.fields.values():
            f.widget.attrs.setdefault('class', 'form-control')


def _mw_row(r):
    return [r.year, r.category_of_work, r.total_employees_male, r.total_employees_female,
            r.total_wages_paid, r.get_filing_status_display()]


def _pow_row(r):
    return [r.year, r.total_employed, r.total_wages_paid, r.get_wage_period_display(),
            r.get_payment_mode_display(), r.get_filing_status_display()]


def _mw_summary(r):
    return [('Male employees', r.total_employees_male), ('Female employees', r.total_employees_female),
            ('Total wages paid', r.total_wages_paid), ('Total OT hours', r.total_ot_hours),
            ('Total OT wages', r.total_ot_wages), ('Total fines imposed', r.total_fines_imposed),
            ('Total deductions', r.total_deductions)]


def _pow_summary(r):
    return [('Total employed', r.total_employed), ('Total wages paid', r.total_wages_paid),
            ('Total fines imposed', r.total_fines_imposed), ('Total fines realised', r.total_fines_realised),
            ('Total deductions', r.total_deductions)]


def _bonus_row(r):
    return [r.year, r.total_employees, r.total_wages, f'{r.bonus_percentage}%',
            r.total_bonus_paid, r.get_filing_status_display()]


def _bonus_summary(r):
    return [('Total employees', r.total_employees), ('Total wages', r.total_wages),
            ('Total bonus paid', r.total_bonus_paid), ('Bonus percentage', f'{r.bonus_percentage}%')]


def _bonus_notes(r):
    if r.total_bonus_paid and not 8.33 <= float(r.bonus_percentage) <= 20:
        return [f'Bonus is {r.bonus_percentage}% of wages, outside the statutory 8.33% to 20% band. '
                'Check the bonus records before filing.']
    return []


RETURNS = {
    'minimum-wages': {
        'title': 'Minimum Wages annual return (Form V)', 'model': MinimumWagesAnnualReturn,
        'edit': MinWagesEditForm, 'compute': wr.compute_minwages_totals,
        'build': wr.build_minwages_return_pdf, 'needs_category': True, 'due': '1 February',
        'columns': ['Year', 'Category of work', 'Male', 'Female', 'Total wages paid', 'Status'],
        'row': _mw_row, 'summary': _mw_summary,
    },
    'payment-of-wages': {
        'title': 'Payment of Wages annual return (Form IV)', 'model': PaymentOfWagesAnnualReturn,
        'edit': PowEditForm, 'compute': wr.compute_pow_totals,
        'build': wr.build_pow_return_pdf, 'needs_category': False, 'due': '15 February',
        'columns': ['Year', 'Employees', 'Total wages paid', 'Wage period', 'Payment mode', 'Status'],
        'row': _pow_row, 'summary': _pow_summary,
    },
    'bonus': {
        'title': 'Bonus annual return (Form D)', 'model': bonus_annual_return,
        'edit': BonusEditForm,
        'compute': lambda c, y, s: br.compute_bonus_return_totals(c, y, s, paid_only=True),
        'build': br.build_bonus_return_pdf, 'needs_category': False, 'due': '1 February',
        'columns': ['Year', 'Employees', 'Total wages', 'Bonus %', 'Bonus paid', 'Status'],
        'row': _bonus_row, 'summary': _bonus_summary, 'notes': _bonus_notes,
        'wages_key': 'total_wages',
    },
}

# Other Annual-returns hub links (url name, label); later families add theirs here.
EXTRA = [('capp_dir_bonus', 'Bonus records (Form A and C)'),
         ('capp_dir_bonus_so', 'Bonus set-on / set-off (Form B)'),
         ('capp_dir_factories', 'Factory registers and Form 34'),
         ('capp_dir_cl', 'Contract labour (Forms I, II, XIII, XIV, 20-CL)')]


def _cfg(key):
    if key not in RETURNS:
        raise Http404('Unknown return.')
    return RETURNS[key]


def _list_url(key):
    return reverse('capp_dir_ret_list', args=[key])


def _get(cfg, company, pk):
    return get_object_or_404(cfg['model'], return_id=pk, company=company)


def _locked(request, rec, key, what):
    if rec.filing_status == 'filed':
        messages.error(request, f'A filed return cannot be {what}.')
        return redirect(_list_url(key))
    return None


@direct_perm('payroll.process')
def capp_dir_returns(request):
    return render(request, 'Capp/direct/returns_hub.html', {
        'items': [(k, v['title'], v['due'], reverse('capp_dir_ret_list', args=[k])) for k, v in RETURNS.items()],
        'extra': [(label, reverse(name)) for name, label in EXTRA]})


@direct_perm('payroll.process')
def capp_dir_ret_list(request, key):
    cfg, company = _cfg(key), request.owned_company
    rows = [{'cells': cfg['row'](r), 'pk': r.return_id, 'filed': r.filing_status == 'filed',
             'due': f'{cfg["due"]} {r.year + 1}'}
            for r in cfg['model'].objects.filter(company=company).order_by('-year')]
    return render(request, 'Capp/direct/returns_list.html', {
        'key': key, 'title': cfg['title'], 'columns': cfg['columns'], 'rows': rows, 'due': cfg['due']})


@direct_perm('payroll.process')
def capp_dir_ret_generate(request, key):
    cfg, company = _cfg(key), request.owned_company
    form = GenerateForm(request.POST or None, needs_category=cfg['needs_category'])
    if request.method == 'POST' and form.is_valid():
        year = form.cleaned_data['year']
        if cfg['model'].objects.filter(company=company, year=year).exists():
            messages.error(request, f'A return for {year} already exists. Edit it instead.')
            return redirect(_list_url(key))
        totals = cfg['compute'](company, year, wr.FINAL)
        if not totals[cfg.get('wages_key', 'total_wages_paid')]:
            messages.error(request, f'No finalized payroll found for {year}. Finalize the monthly '
                                    'payroll batches first.')
            return redirect(_list_url(key))
        extra = {'category_of_work': form.cleaned_data['category_of_work'].strip()} if cfg['needs_category'] else {}
        rec = cfg['model'].objects.create(company=company, year=year, created_by=request.user, **extra, **totals)
        log_action(request, f'return.{key}.generate', rec, f'{cfg["title"]} {year}')
        messages.success(request, f'Return for {year} generated from finalized payroll. '
                                  'Set the details and record the filing.')
        return redirect('capp_dir_ret_edit', key=key, pk=rec.return_id)
    return render(request, 'Capp/direct/register_form.html', {
        'form': form, 'title': f'Generate: {cfg["title"]}', 'back': _list_url(key)})


@direct_perm('payroll.process')
def capp_dir_ret_edit(request, key, pk):
    cfg, company = _cfg(key), request.owned_company
    rec = _get(cfg, company, pk)
    form = cfg['edit'](request.POST or None, instance=rec)
    if request.method == 'POST' and form.is_valid():
        rec = form.save()
        log_action(request, f'return.{key}.edit', rec, f'{cfg["title"]} {rec.year}')
        messages.success(request, 'Return updated.')
        return redirect(_list_url(key))
    return render(request, 'Capp/direct/returns_edit.html', {
        'form': form, 'title': f'{cfg["title"]}: {rec.year}', 'back': _list_url(key),
        'summary': cfg['summary'](rec), 'filed': rec.filing_status == 'filed',
        'notes': cfg['notes'](rec) if 'notes' in cfg else []})


@direct_perm('payroll.process')
@require_POST
def capp_dir_ret_recompute(request, key, pk):
    cfg, company = _cfg(key), request.owned_company
    rec = _get(cfg, company, pk)
    locked = _locked(request, rec, key, 'recomputed')
    if locked:
        return locked
    totals = cfg['compute'](company, rec.year, wr.FINAL)
    if not totals[cfg.get('wages_key', 'total_wages_paid')]:
        messages.error(request, f'No finalized payroll found for {rec.year}; totals left unchanged.')
        return redirect(_list_url(key))
    for name, value in totals.items():
        setattr(rec, name, value)
    rec.save()
    log_action(request, f'return.{key}.recompute', rec, f'{cfg["title"]} {rec.year}')
    messages.success(request, 'Totals refreshed from finalized payroll.')
    return redirect('capp_dir_ret_edit', key=key, pk=rec.return_id)


@direct_perm('payroll.process')
@require_POST
def capp_dir_ret_delete(request, key, pk):
    cfg, company = _cfg(key), request.owned_company
    rec = _get(cfg, company, pk)
    locked = _locked(request, rec, key, 'deleted')
    if locked:
        return locked
    log_action(request, f'return.{key}.delete', rec, f'{cfg["title"]} {rec.year}')
    rec.delete()
    messages.success(request, 'Return deleted.')
    return redirect(_list_url(key))


@direct_perm('challan.download')
def capp_dir_ret_download(request, key, pk):
    cfg, company = _cfg(key), request.owned_company
    rec = _get(cfg, company, pk)
    try:
        pdf, fname = cfg['build'](company, rec)
    except StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect(_list_url(key))
    log_action(request, 'report.download', rec, f'{cfg["title"]} {rec.year}')
    r = HttpResponse(pdf, content_type='application/pdf')
    r['Content-Disposition'] = f'attachment; filename="{fname}"'
    return r
