"""D5b-3b - Payment of Bonus Act records for a DIRECT company.

Bonus records (Form A and C data, one per employee per salary month) with a Form C monthly register
PDF, and the Form B set-on / set-off register (one row per year) with PDF. The Form D annual return
is generated in Capp/direct/returns.py from finalized payroll plus the bonus actually PAID here.

Rules: a paid record is locked (no edit, no delete); the percentage is capped at the statutory 20%;
a year is either set-on or set-off, never both. There is no registration number for the Bonus Act
in company statutory setup, so there is no registration gate. Aapp's `bonus_act` plan feature is not
applied in Capp. Permissions: entry payroll.process, PDFs challan.download.
"""
import calendar
from datetime import date
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from Aapp.app.bonus import bonus_record, bonus_set_on_set_off
from Aapp.app.employee import employee
from Aapp.app.services import bonus_returns as br
from Aapp.app.services.statutory_files import StatutoryFileError
from Capp.audit import log_action
from Capp.direct.guards import direct_perm

DATE = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')
ZERO, CENT = Decimal('0'), Decimal('0.01')
FIRST_YEAR = 2023


def _years():
    return list(range(date.today().year, FIRST_YEAR - 1, -1))


def _css(form):
    for f in form.fields.values():
        f.widget.attrs.setdefault('class', 'form-control')


def _check_year(form, d):
    y = d.get('year', d.get('salary_year'))
    name = 'year' if 'year' in form.fields else 'salary_year'
    if y is not None and not FIRST_YEAR <= y <= date.today().year + 1:
        form.add_error(name, 'Enter a valid year.')


# ── forms ─────────────────────────────────────────────────────────────────────
class BonusRecordForm(forms.ModelForm):
    class Meta:
        model = bonus_record
        fields = ['employee', 'salary_month', 'salary_year', 'bonus_percentage', 'basic_bonus',
                  'performance_bonus', 'festival_bonus', 'other_bonus', 'reason']

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        keep = Q(is_working=True)
        if self.instance.pk:
            keep |= Q(employeeid=self.instance.employee_id)
        self.fields['employee'].queryset = employee.objects.filter(CompanyID=company).filter(keep).order_by('name')
        self.fields['salary_year'].initial = date.today().year
        _css(self)

    def clean(self):
        d = super().clean()
        amounts = ('basic_bonus', 'performance_bonus', 'festival_bonus', 'other_bonus')
        for n in amounts:
            if d.get(n) is not None and d[n] < 0:
                self.add_error(n, 'Cannot be negative.')
        pct = d.get('bonus_percentage')
        if pct is not None and not ZERO <= pct <= 20:
            self.add_error('bonus_percentage', 'Bonus percentage must be between 0 and 20 (statutory maximum).')
        _check_year(self, d)
        if not self.errors and not sum(d[n] for n in amounts):
            raise forms.ValidationError('Enter at least one bonus amount.')
        return d


class PayForm(forms.Form):
    payment_date = forms.DateField(widget=DATE, label='Payment date')

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _css(self)

    def clean_payment_date(self):
        v = self.cleaned_data['payment_date']
        if v > date.today():
            raise forms.ValidationError('Date cannot be in the future.')
        return v


class SetOnSetOffForm(forms.ModelForm):
    class Meta:
        model = bonus_set_on_set_off
        fields = ['year', 'allocable_surplus', 'total_wages_for_bonus', 'min_bonus_amount',
                  'max_bonus_amount', 'bonus_paid', 'set_on_amount', 'set_off_amount', 'cumulative_set_on']

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        self.company = company
        for n in ('min_bonus_amount', 'max_bonus_amount'):
            self.fields[n].required = False
        self.fields['min_bonus_amount'].help_text = 'Leave blank to use 8.33% of wages.'
        self.fields['max_bonus_amount'].help_text = 'Leave blank to use 20% of wages.'
        _css(self)

    def clean(self):
        d = super().clean()
        money = ('allocable_surplus', 'total_wages_for_bonus', 'bonus_paid', 'set_on_amount',
                 'set_off_amount', 'cumulative_set_on', 'min_bonus_amount', 'max_bonus_amount')
        for n in money:
            if d.get(n) is not None and d[n] < 0:
                self.add_error(n, 'Cannot be negative.')
        _check_year(self, d)
        year = d.get('year')
        if year is not None and bonus_set_on_set_off.objects.filter(company=self.company, year=year) \
                .exclude(pk=self.instance.pk).exists():
            self.add_error('year', f'A set-on / set-off record for {year} already exists. Edit it instead.')
        if self.errors:
            return d
        if d['set_on_amount'] > 0 and d['set_off_amount'] > 0:
            raise forms.ValidationError('A year has either a set-on or a set-off amount, not both.')
        wages = d['total_wages_for_bonus']
        if d.get('min_bonus_amount') is None:
            d['min_bonus_amount'] = (wages * Decimal('8.33') / 100).quantize(CENT)
        if d.get('max_bonus_amount') is None:
            d['max_bonus_amount'] = (wages * Decimal('20') / 100).quantize(CENT)
        if d['min_bonus_amount'] > d['max_bonus_amount']:
            raise forms.ValidationError('Minimum bonus cannot exceed maximum bonus.')
        return d


# ── bonus records ─────────────────────────────────────────────────────────────
def _period(request):
    today = date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except ValueError:
        year, month = today.year, today.month
    return (year if FIRST_YEAR <= year <= today.year + 1 else today.year,
            month if 1 <= month <= 12 else today.month)


@direct_perm('payroll.process')
def capp_dir_bonus(request):
    company = request.owned_company
    year, month = _period(request)
    qs = (bonus_record.objects.filter(company=company, salary_year=year)
          .select_related('employee').order_by('salary_month', 'employee__name'))
    rows = list(qs)
    return render(request, 'Capp/direct/bonus_list.html', {
        'rows': rows, 'year': year, 'month': month, 'years': _years(),
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'total': sum((r.total_bonus for r in rows), ZERO),
        'register_url': reverse('capp_dir_bonus_register', args=[year, month])})


@direct_perm('payroll.process')
def capp_dir_bonus_add(request):
    form = BonusRecordForm(request.POST or None, company=request.owned_company)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.company, obj.created_by = request.owned_company, request.user
        obj.save()
        log_action(request, 'bonus.add', obj, f'{obj.salary_month}/{obj.salary_year}')
        messages.success(request, 'Bonus record saved.')
        return redirect(f'{reverse("capp_dir_bonus")}?year={obj.salary_year}')
    return render(request, 'Capp/direct/register_form.html', {
        'form': form, 'title': 'Add bonus record', 'back': reverse('capp_dir_bonus')})


def _unpaid_or_redirect(request, rec, what):
    if rec.is_paid:
        messages.error(request, f'A paid bonus record cannot be {what}.')
        return redirect(f'{reverse("capp_dir_bonus")}?year={rec.salary_year}')
    return None


@direct_perm('payroll.process')
def capp_dir_bonus_edit(request, pk):
    company = request.owned_company
    rec = get_object_or_404(bonus_record, bonus_id=pk, company=company)
    locked = _unpaid_or_redirect(request, rec, 'edited')
    if locked:
        return locked
    form = BonusRecordForm(request.POST or None, instance=rec, company=company)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.updated_by = request.user
        obj.save()
        log_action(request, 'bonus.edit', obj, f'{obj.salary_month}/{obj.salary_year}')
        messages.success(request, 'Bonus record updated.')
        return redirect(f'{reverse("capp_dir_bonus")}?year={obj.salary_year}')
    return render(request, 'Capp/direct/register_form.html', {
        'form': form, 'title': f'Edit bonus: {rec.employee.name} {rec.salary_month}/{rec.salary_year}',
        'back': reverse('capp_dir_bonus')})


@direct_perm('payroll.process')
def capp_dir_bonus_pay(request, pk):
    rec = get_object_or_404(bonus_record, bonus_id=pk, company=request.owned_company)
    if rec.is_paid:
        messages.error(request, 'This bonus is already marked as paid.')
        return redirect(f'{reverse("capp_dir_bonus")}?year={rec.salary_year}')
    form = PayForm(request.POST or None, initial={'payment_date': date.today()})
    if request.method == 'POST' and form.is_valid():
        rec.is_paid, rec.payment_date, rec.updated_by = True, form.cleaned_data['payment_date'], request.user
        rec.save()
        log_action(request, 'bonus.pay', rec, f'{rec.salary_month}/{rec.salary_year}')
        messages.success(request, f'Bonus marked as paid for {rec.employee.name}. It is now locked.')
        return redirect(f'{reverse("capp_dir_bonus")}?year={rec.salary_year}')
    return render(request, 'Capp/direct/register_form.html', {
        'form': form, 'back': reverse('capp_dir_bonus'),
        'title': f'Mark paid: {rec.employee.name} {rec.salary_month}/{rec.salary_year} (Rs {rec.total_bonus})'})


@direct_perm('payroll.process')
@require_POST
def capp_dir_bonus_delete(request, pk):
    rec = get_object_or_404(bonus_record, bonus_id=pk, company=request.owned_company)
    locked = _unpaid_or_redirect(request, rec, 'deleted')
    if locked:
        return locked
    log_action(request, 'bonus.delete', rec, f'{rec.salary_month}/{rec.salary_year}')
    year = rec.salary_year
    rec.delete()
    messages.success(request, 'Bonus record deleted.')
    return redirect(f'{reverse("capp_dir_bonus")}?year={year}')


@direct_perm('challan.download')
def capp_dir_bonus_register(request, year, month):
    if not 1 <= month <= 12:
        raise Http404('Invalid month.')
    try:
        pdf, fname = br.build_bonus_register_pdf(request.owned_company, month, year)
    except StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect(f'{reverse("capp_dir_bonus")}?year={year}&month={month}')
    log_action(request, 'report.download', None, f'Bonus register (Form C) {month}/{year}')
    r = HttpResponse(pdf, content_type='application/pdf')
    r['Content-Disposition'] = f'attachment; filename="{fname}"'
    return r


# ── set-on / set-off (Form B) ───────────────────────────────────────────────────
@direct_perm('payroll.process')
def capp_dir_bonus_so(request):
    return render(request, 'Capp/direct/bonus_so_list.html', {
        'rows': bonus_set_on_set_off.objects.filter(company=request.owned_company).order_by('-year')})


@direct_perm('payroll.process')
def capp_dir_bonus_so_add(request):
    company = request.owned_company
    form = SetOnSetOffForm(request.POST or None, company=company)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.company, obj.created_by = company, request.user
        obj.save()
        log_action(request, 'bonus.setonoff.add', obj, str(obj.year))
        messages.success(request, 'Set-on / set-off record saved.')
        return redirect('capp_dir_bonus_so')
    return render(request, 'Capp/direct/register_form.html', {
        'form': form, 'title': 'Add set-on / set-off (Form B)', 'back': reverse('capp_dir_bonus_so')})


@direct_perm('payroll.process')
def capp_dir_bonus_so_edit(request, pk):
    company = request.owned_company
    rec = get_object_or_404(bonus_set_on_set_off, record_id=pk, company=company)
    form = SetOnSetOffForm(request.POST or None, instance=rec, company=company)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        log_action(request, 'bonus.setonoff.edit', obj, str(obj.year))
        messages.success(request, 'Record updated.')
        return redirect('capp_dir_bonus_so')
    return render(request, 'Capp/direct/register_form.html', {
        'form': form, 'title': f'Edit set-on / set-off: {rec.year}', 'back': reverse('capp_dir_bonus_so')})


@direct_perm('payroll.process')
@require_POST
def capp_dir_bonus_so_delete(request, pk):
    rec = get_object_or_404(bonus_set_on_set_off, record_id=pk, company=request.owned_company)
    log_action(request, 'bonus.setonoff.delete', rec, str(rec.year))
    rec.delete()
    messages.success(request, 'Record deleted.')
    return redirect('capp_dir_bonus_so')


@direct_perm('challan.download')
def capp_dir_bonus_so_pdf(request, pk):
    company = request.owned_company
    rec = get_object_or_404(bonus_set_on_set_off, record_id=pk, company=company)
    try:
        pdf, fname = br.build_set_on_set_off_pdf(company, rec)
    except StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect('capp_dir_bonus_so')
    log_action(request, 'report.download', rec, f'Bonus set-on/set-off (Form B) {rec.year}')
    r = HttpResponse(pdf, content_type='application/pdf')
    r['Content-Disposition'] = f'attachment; filename="{fname}"'
    return r
