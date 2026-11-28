"""D5b-1 - fines (Form I), deductions (Form II) and overtime (Form IV) registers for a DIRECT company.

Entry screens plus the PDF download. These registers are records only: they do not change any
salary figure (Aapp's salary calculation does not read them). Aapp parity: fines need the Shop
Act number on file; deductions and overtime have no registration gate. Everything is scoped to
request.owned_company; the employee / attendance choices are limited to the company's own rows.
"""
import calendar
from datetime import date
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from Aapp.app.attandance import MinimumWagesOvertimeRegister, attendance
from Aapp.app.employee import employee
from Aapp.app.salary_processing import MONTH_CHOICES, YEAR_CHOICES
from Aapp.app.services import registers as rg
from Aapp.app.services.statutory_files import StatutoryFileError
from Aapp.app.statutory_gates import get_company_gates
from Aapp.app.wages import wages_deduction, wages_fine
from Capp.audit import log_action
from Capp.direct.guards import direct_perm

DATE = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')


def _positive(form, name):
    v = form.cleaned_data.get(name)
    if v is not None and v <= 0:
        form.add_error(name, 'Enter an amount above zero.')


class _Base(forms.ModelForm):
    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        for f in self.fields.values():
            f.widget.attrs.setdefault('class', 'form-control')
        if 'employee' in self.fields:
            self.fields['employee'].queryset = employee.objects.filter(
                CompanyID=company, is_working=True).order_by('name')
        if 'salary_year' in self.fields:
            self.fields['salary_year'].choices = [(y, y) for y in YEAR_CHOICES]


class FineForm(_Base):
    class Meta:
        model = wages_fine
        fields = ['employee', 'fine_date', 'fine_amount', 'fine_reason', 'salary_month', 'salary_year']
        widgets = {'fine_date': DATE}

    def clean(self):
        d = super().clean()
        _positive(self, 'fine_amount')
        return d


class DeductionForm(_Base):
    class Meta:
        model = wages_deduction
        fields = ['employee', 'deduction_type', 'deduction_amount', 'reason', 'salary_month', 'salary_year']

    def clean(self):
        d = super().clean()
        _positive(self, 'deduction_amount')
        return d


class OvertimeForm(_Base):
    ot_rate = forms.DecimalField(required=False, max_digits=10, decimal_places=2,
                                 help_text='Leave blank for double the ordinary rate.')
    ot_wages_paid = forms.DecimalField(required=False, max_digits=10, decimal_places=2,
                                       help_text='Leave blank for hours x OT rate.')

    class Meta:
        model = MinimumWagesOvertimeRegister
        fields = ['attendance', 'ot_date', 'overtime_hours', 'ordinary_rate', 'ot_rate',
                  'ot_wages_paid', 'ot_reason']
        widgets = {'ot_date': DATE}

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, company=company, **k)
        self.fields['attendance'].queryset = attendance.objects.filter(
            companyid=company).order_by('-salary_year', '-salary_month', 'emp_code')
        self.fields['attendance'].label = 'Employee and month (from attendance)'

    def clean(self):
        d = super().clean()
        _positive(self, 'overtime_hours')
        _positive(self, 'ordinary_rate')
        if self.errors:
            return d
        if not d.get('ot_rate'):
            d['ot_rate'] = d['ordinary_rate'] * 2
        if not d.get('ot_wages_paid'):
            d['ot_wages_paid'] = (d['overtime_hours'] * d['ot_rate']).quantize(Decimal('0.01'))
        return d


def _fine_row(r):
    return [r.employee.name, r.fine_date.strftime('%d-%b-%Y'), r.fine_reason, r.fine_amount]


def _ded_row(r):
    return [r.employee.name, r.get_deduction_type_display(), r.reason, r.deduction_amount]


def _ot_row(r):
    return [r.attendance.emp_code, r.ot_date.strftime('%d-%b-%Y'), r.overtime_hours, r.ot_wages_paid]


REGISTERS = {
    'fines': {
        'title': 'Fines register (Form I)', 'form': FineForm, 'model': wages_fine, 'pk': 'fine_id',
        'columns': ['Employee', 'Date', 'Reason', 'Amount'], 'row': _fine_row,
        'scope': lambda c: {'company': c}, 'month_f': 'salary_month', 'year_f': 'salary_year',
        'select': ['employee'], 'build': rg.build_fines_register_pdf, 'needs_shop_act': True,
        'save': lambda obj, c, u: (setattr(obj, 'company', c), setattr(obj, 'created_by', u)),
    },
    'deductions': {
        'title': 'Deductions register (Form II)', 'form': DeductionForm, 'model': wages_deduction,
        'pk': 'deduction_id', 'columns': ['Employee', 'Type', 'Reason', 'Amount'], 'row': _ded_row,
        'scope': lambda c: {'company': c}, 'month_f': 'salary_month', 'year_f': 'salary_year',
        'select': ['employee'], 'build': rg.build_deductions_register_pdf, 'needs_shop_act': False,
        'save': lambda obj, c, u: (setattr(obj, 'company', c), setattr(obj, 'created_by', u)),
    },
    'overtime': {
        'title': 'Overtime register (Form IV)', 'form': OvertimeForm, 'model': MinimumWagesOvertimeRegister,
        'pk': 'ot_register_id', 'columns': ['Code', 'Date', 'Hours', 'OT wages'], 'row': _ot_row,
        'scope': lambda c: {'attendance__companyid': c}, 'month_f': 'attendance__salary_month',
        'year_f': 'attendance__salary_year', 'select': ['attendance'],
        'build': rg.build_ot_register_pdf, 'needs_shop_act': False,
        'save': lambda obj, c, u: None,
    },
}


def _cfg(key):
    if key not in REGISTERS:
        raise Http404('Unknown register.')
    return REGISTERS[key]


def _month_year(request):
    today = date.today()
    try:
        month, year = int(request.GET.get('month', today.month)), int(request.GET.get('year', today.year))
    except ValueError:
        month, year = today.month, today.year
    return (month if 1 <= month <= 12 else today.month), year


def _shop_act_blocked(request, cfg, company):
    if cfg['needs_shop_act'] and not get_company_gates(company)['shop_act']:
        messages.error(request, 'Shop and Establishment Act number is not on file, so this register '
                                'is off. Add it under Statutory setup.')
        return True
    return False


@direct_perm('payroll.process')
def capp_dir_registers(request):
    return render(request, 'Capp/direct/register_hub.html', {
        'items': [(k, v['title'], reverse('capp_dir_reg_list', args=[k])) for k, v in REGISTERS.items()]})


@direct_perm('payroll.process')
def capp_dir_reg_list(request, key):
    cfg, company = _cfg(key), request.owned_company
    month, year = _month_year(request)
    qs = cfg['model'].objects.filter(**cfg['scope'](company), **{
        cfg['month_f']: month, cfg['year_f']: year}).select_related(*cfg['select'])
    rows = [{'cells': cfg['row'](r), 'pk': getattr(r, cfg['pk'])} for r in qs]
    return render(request, 'Capp/direct/register_list.html', {
        'key': key, 'title': cfg['title'], 'columns': cfg['columns'], 'rows': rows,
        'month': month, 'year': year, 'month_name': calendar.month_name[month],
        'months': MONTH_CHOICES, 'years': YEAR_CHOICES,
        'off': _shop_act_off(cfg, company),
    })


def _shop_act_off(cfg, company):
    return cfg['needs_shop_act'] and not get_company_gates(company)['shop_act']


@direct_perm('payroll.process')
def capp_dir_reg_add(request, key):
    cfg, company = _cfg(key), request.owned_company
    month, year = _month_year(request)
    back = f"{reverse('capp_dir_reg_list', args=[key])}?month={month}&year={year}"
    if _shop_act_blocked(request, cfg, company):
        return redirect(back)
    initial = {'salary_month': month, 'salary_year': year}
    form = cfg['form'](request.POST or None, company=company, initial=initial)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        cfg['save'](obj, company, request.user)
        if key == 'overtime':
            obj.ot_rate = form.cleaned_data['ot_rate']
            obj.ot_wages_paid = form.cleaned_data['ot_wages_paid']
        obj.save()
        log_action(request, f'register.{key}.add', obj, cfg['title'])
        messages.success(request, 'Entry saved.')
        return redirect(back)
    return render(request, 'Capp/direct/register_form.html', {
        'form': form, 'title': f'Add entry: {cfg["title"]}', 'back': back})


@direct_perm('payroll.process')
@require_POST
def capp_dir_reg_delete(request, key, pk):
    cfg, company = _cfg(key), request.owned_company
    obj = get_object_or_404(cfg['model'], **{cfg['pk']: pk}, **cfg['scope'](company))
    log_action(request, f'register.{key}.delete', obj, cfg['title'])
    obj.delete()
    messages.success(request, 'Entry deleted.')
    return redirect('capp_dir_reg_list', key=key)


@direct_perm('challan.download')
def capp_dir_reg_download(request, key, year, month):
    cfg, company = _cfg(key), request.owned_company
    if not 1 <= month <= 12:
        raise Http404('Invalid month.')
    back = f"{reverse('capp_dir_reg_list', args=[key])}?month={month}&year={year}"
    if _shop_act_blocked(request, cfg, company):
        return redirect(back)
    try:
        pdf, fname = cfg['build'](company, month, year)
    except StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect(back)
    log_action(request, 'report.download', None, f'{cfg["title"]} {month}/{year}')
    r = HttpResponse(pdf, content_type='application/pdf')
    r['Content-Disposition'] = f'attachment; filename="{fname}"'
    return r
