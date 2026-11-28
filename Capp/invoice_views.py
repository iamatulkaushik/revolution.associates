"""Capp/invoice_views.py — generate, view, issue, cancel, pay, download."""
from datetime import date
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from Capp.billing_models import BillingClient, Invoice
from Capp.billing_views import MonthField
from Capp.invoice_export import invoice_pdf, invoice_xlsx
from Capp.invoicing import InvoiceError, generate_invoice
from Capp.audit import log_action
from Capp.masters import billing_required, _style


class GenerateForm(forms.Form):
    client = forms.ModelChoiceField(queryset=BillingClient.objects.none())
    kind = forms.ChoiceField(choices=Invoice.KIND_CHOICES, label='Bill type')
    month = MonthField(label='Month')
    extra_label = forms.CharField(required=False, label='Extra charge title',
                                  help_text='e.g. Conveyance')
    extra_charges = forms.DecimalField(required=False, min_value=0, decimal_places=2,
                                       max_digits=12, label='Extra charge amount')

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        self.fields['client'].queryset = BillingClient.objects.filter(company=company, is_active=True)
        self.fields['month'].initial = date.today().replace(day=1)
        _style(self)


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['received_amount', 'tds_amount', 'received_on', 'payment_ref']
        widgets = {'received_on': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        _style(self)

    def clean(self):
        d = super().clean()
        got = (d.get('received_amount') or 0) + (d.get('tds_amount') or 0)
        if got > self.instance.total:
            raise forms.ValidationError('Received plus TDS cannot exceed the invoice total.')
        return d


def _inv(request, pk):
    return get_object_or_404(Invoice, pk=pk, company=request.owned_company)


@billing_required
def capp_invoice_list(request):
    qs = Invoice.objects.filter(company=request.owned_company).select_related('client')
    if request.GET.get('status'):
        qs = qs.filter(status=request.GET['status'])
    total = sum(i.total for i in qs if i.status != 'CANCELLED')
    due = sum(i.outstanding for i in qs if i.status == 'ISSUED')
    return render(request, 'Capp/masters/invoice_list.html', {
        'page_title': 'Invoices', 'invoices': qs, 'total': total, 'due': due})


@billing_required
def capp_invoice_generate(request):
    company = request.owned_company
    form = GenerateForm(request.POST or None, company=company)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        try:
            inv = generate_invoice(company, d['client'], d['kind'], d['month'].year, d['month'].month,
                                   user=request.user.username, extra_label=d['extra_label'],
                                   extra_charges=d['extra_charges'] or Decimal('0'))
        except InvoiceError as e:
            form.add_error(None, str(e))
        else:
            log_action(request, 'invoice_generate', inv, f'{inv.number} {inv.get_kind_display()}')
            messages.success(request, f'Draft {inv.number} created.')
            return redirect('capp_invoice_detail', pk=inv.pk)
    return render(request, 'Capp/masters/form.html', {
        'form': form, 'page_title': 'Generate Invoice', 'cancel_url': 'capp_invoice_list'})


@billing_required
def capp_invoice_detail(request, pk):
    inv = _inv(request, pk)
    pay_form = PaymentForm(instance=inv)
    return render(request, 'Capp/masters/invoice_detail.html', {
        'page_title': inv.number, 'inv': inv, 'lines': inv.lines.all(), 'pay_form': pay_form})


@billing_required
def capp_invoice_action(request, pk, action):
    inv = _inv(request, pk)
    if request.method != 'POST':
        return redirect('capp_invoice_detail', pk=pk)
    if action == 'issue' and inv.status == 'DRAFT':
        inv.status = 'ISSUED'
        inv.save(update_fields=['status'])
        log_action(request, 'invoice_issue', inv, inv.number)
        messages.success(request, f'{inv.number} issued.')
    elif action == 'cancel' and inv.status in ('DRAFT', 'ISSUED') and not inv.received_amount:
        inv.status = 'CANCELLED'
        inv.save(update_fields=['status'])
        log_action(request, 'invoice_cancel', inv, inv.number)
        messages.success(request, f'{inv.number} cancelled.')
    elif action == 'delete' and inv.status == 'DRAFT':
        log_action(request, 'invoice_delete', inv, inv.number)
        inv.delete()
        messages.success(request, 'Draft deleted.')
        return redirect('capp_invoice_list')
    elif action == 'payment' and inv.status == 'ISSUED':
        form = PaymentForm(request.POST, instance=inv)
        if form.is_valid():
            form.save()
            log_action(request, 'invoice_payment', inv, f'{inv.number} received {inv.received_amount} tds {inv.tds_amount}')
            messages.success(request, 'Payment recorded.')
        else:
            messages.error(request, ' '.join(e for es in form.errors.values() for e in es))
    else:
        messages.error(request, 'That action is not allowed for this invoice.')
    return redirect('capp_invoice_detail', pk=pk)


@billing_required
def capp_invoice_download(request, pk, fmt):
    inv = _inv(request, pk)
    name = inv.number.replace('/', '-')
    if fmt == 'pdf':
        if not request.owner_profile.can_download_pdf:
            messages.error(request, 'PDF download not permitted.')
            return redirect('capp_invoice_detail', pk=pk)
        data, ctype = invoice_pdf(inv), 'application/pdf'
    else:
        data = invoice_xlsx(inv)
        ctype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    resp = HttpResponse(data, content_type=ctype)
    resp['Content-Disposition'] = f'attachment; filename="{name}.{fmt}"'
    return resp
