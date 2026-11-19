"""Capp/bank_views.py — bank format screens + bank file download."""
from datetime import date

from django import forms
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404

from Capp.bank_export import apply_month, build_rows, group_by_bank, render_file, seed_canara
from Capp.billing_models import BankFormat, BankFormatColumn
from Capp.masters import masters_required, _style
from Capp.views import access_required


class BankFormatForm(forms.ModelForm):
    class Meta:
        model = BankFormat
        fields = ['bank_name', 'ifsc_prefix', 'file_type', 'delimiter', 'has_header',
                  'add_total_row', 'sample_file', 'is_active']

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        self.company = company
        _style(self)

    def clean_ifsc_prefix(self):
        v = self.cleaned_data['ifsc_prefix'].strip().upper()
        if not (len(v) == 4 and v.isalpha()):
            raise forms.ValidationError('4 letters, e.g. CNRB.')
        qs = BankFormat.objects.filter(company=self.company, ifsc_prefix=v)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A format for this bank already exists.')
        return v


ColumnFormSet = forms.inlineformset_factory(
    BankFormat, BankFormatColumn,
    fields=['position', 'header', 'source', 'fixed_value', 'width'],
    extra=3, can_delete=True)


@masters_required
def capp_bankformat_list(request):
    company = request.owned_company
    if request.method == 'POST' and 'seed_canara' in request.POST:
        seed_canara(company)
        messages.success(request, 'Canara format added.')
        return redirect('capp_bankformat_list')
    rows = [{'pk': f.pk, 'cells': [f.bank_name, f.ifsc_prefix, f.file_type,
                                   f.columns.count(), 'Yes' if f.is_active else 'No']}
            for f in BankFormat.objects.filter(company=company).order_by('bank_name')]
    return render(request, 'Capp/masters/bank_formats.html', {
        'page_title': 'Bank Formats', 'rows': rows,
        'columns': ['Bank', 'IFSC prefix', 'File', 'Columns', 'Active']})


@masters_required
def capp_bankformat_edit(request, pk=None):
    company = request.owned_company
    inst = get_object_or_404(BankFormat, pk=pk, company=company) if pk else None
    form = BankFormatForm(request.POST or None, request.FILES or None, instance=inst, company=company)
    fs = ColumnFormSet(request.POST or None, instance=inst or BankFormat(company=company))
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.company = company
        fs = ColumnFormSet(request.POST, instance=obj)
        if fs.is_valid():
            obj.save()
            fs.instance = obj
            fs.save()
            messages.success(request, 'Bank format saved.')
            return redirect('capp_bankformat_list')
    return render(request, 'Capp/masters/bank_format_form.html', {
        'form': form, 'formset': fs, 'page_title': 'Edit Bank Format' if pk else 'Add Bank Format'})


@masters_required
def capp_bankformat_delete(request, pk):
    obj = get_object_or_404(BankFormat, pk=pk, company=request.owned_company)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Bank format deleted.')
        return redirect('capp_bankformat_list')
    return render(request, 'Capp/masters/confirm_delete.html', {
        'label': f'Bank format "{obj.bank_name}"', 'cancel_url': 'capp_bankformat_list'})


@access_required('wages')
def capp_bank_file(request):
    from Aapp.app.salary_processing import salary_slip
    company = request.owned_company
    month = int(request.GET.get('month', date.today().month))
    year = int(request.GET.get('year', date.today().year))
    if request.method == 'POST' and 'close_month' in request.POST:
        n = apply_month(company, year, month)
        messages.success(request, f'{n} deduction(s) updated for {month:02d}/{year}.')
        return redirect(f"{request.path}?month={month}&year={year}")
    slips = salary_slip.objects.filter(
        company_id=company, processing_id__month=month, processing_id__year=year,
        net_pay__gt=0).select_related('employee_id', 'employee_id__departmentID')
    groups = group_by_bank(build_rows(slips, company, year, month))
    formats = {f.ifsc_prefix: f for f in BankFormat.objects.filter(company=company, is_active=True)}

    want = request.GET.get('bank')
    if want and want in groups:
        ctx = {'pay_date': date.today().strftime('%d/%m/%Y'),
               'debit_account': company.account or '',
               'narration': f'Salary {month:02d}/{year}'}
        data, fname, ctype = render_file(formats.get(want), groups[want], ctx)
        resp = HttpResponse(data, content_type=ctype)
        resp['Content-Disposition'] = f'attachment; filename="{want}_{year}_{month:02d}_{fname}"'
        return resp

    summary = [{'prefix': p, 'count': len(r), 'total': sum(int(x['net_pay']) for x in r),
                'format': formats[p].bank_name if p in formats else 'No format (CSV)'}
               for p, r in groups.items()]
    return render(request, 'Capp/masters/bank_file.html', {
        'page_title': 'Bank Payment Files', 'summary': summary, 'month': month, 'year': year,
        'months': list(range(1, 13)),
        'grand_total': sum(s['total'] for s in summary)})
