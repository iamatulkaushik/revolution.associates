"""Capp/import_views.py — Excel employee import: upload -> preview -> confirm."""
import base64
import io

from django import forms
from django.contrib import messages
from django.shortcuts import redirect, render

from Aapp.app.branch_department import branch
from Capp import importer
from Capp.billing_models import BillingClient
from Capp.masters import masters_required, _style

MAX_BYTES = 2 * 1024 * 1024
SESSION_KEY = 'capp_employee_import'


class ImportForm(forms.Form):
    file = forms.FileField(label='Excel file (.xls or .xlsx)')
    branch = forms.ModelChoiceField(queryset=branch.objects.none(), label='Branch',
                                    help_text='New employees and departments go here.')
    gender = forms.ChoiceField(choices=[(g, g) for g in importer.GENDERS], initial='Male',
                               label='Default gender',
                               help_text='Sheets usually have no gender column. Fix later per employee.')
    client = forms.ModelChoiceField(queryset=BillingClient.objects.none(), required=False,
                                    label='Map to billing client (optional)')

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        self.fields['branch'].queryset = branch.objects.filter(companyid=company)
        self.fields['client'].queryset = BillingClient.objects.filter(company=company, is_active=True)
        _style(self)

    def clean_file(self):
        f = self.cleaned_data['file']
        if not f.name.lower().endswith(('.xls', '.xlsx')):
            raise forms.ValidationError('Upload an .xls or .xlsx file.')
        if f.size > MAX_BYTES:
            raise forms.ValidationError('File is larger than 2 MB.')
        return f


def _summary(rows):
    return {'total': len(rows),
            'ok': sum(1 for r in rows if not r['issues']),
            'create': sum(1 for r in rows if not r['issues'] and r['action'] == 'create'),
            'update': sum(1 for r in rows if not r['issues'] and r['action'] == 'update'),
            'bad': sum(1 for r in rows if r['issues'])}


@masters_required
def capp_import_employees(request):
    company = request.owned_company
    form = ImportForm(request.POST or None, request.FILES or None, company=company)

    if request.method == 'POST' and 'confirm' in request.POST:
        saved = request.session.get(SESSION_KEY)
        if not saved:
            messages.error(request, 'Import expired. Upload the file again.')
            return redirect('capp_import_employees')
        raw = base64.b64decode(saved['b64'])
        rows, _ = importer.parse(importer.read_sheets(io.BytesIO(raw), saved['name']), company)
        br = branch.objects.filter(pk=saved['branch'], companyid=company).first()
        client = BillingClient.objects.filter(pk=saved['client'], company=company).first() \
            if saved['client'] else None
        if not br:
            messages.error(request, 'Branch not found.')
            return redirect('capp_import_employees')
        res = importer.apply(rows, company, br, request.user, saved['gender'], client)
        request.session.pop(SESSION_KEY, None)
        messages.success(request, f"Imported: {res['created']} new, {res['updated']} updated, "
                                  f"{res['skipped']} skipped.")
        return redirect('capp_import_employees')

    if request.method == 'POST' and form.is_valid():
        f = form.cleaned_data['file']
        raw = f.read()
        try:
            rows, notes = importer.parse(importer.read_sheets(io.BytesIO(raw), f.name), company)
        except Exception as e:                       # unreadable workbook
            form.add_error('file', f'Could not read the workbook: {e}')
        else:
            request.session[SESSION_KEY] = {
                'name': f.name, 'b64': base64.b64encode(raw).decode(),
                'branch': form.cleaned_data['branch'].pk, 'gender': form.cleaned_data['gender'],
                'client': form.cleaned_data['client'].pk if form.cleaned_data['client'] else None}
            return render(request, 'Capp/masters/import_preview.html', {
                'page_title': 'Import Preview', 'rows': rows, 'notes': notes,
                'summary': _summary(rows)})
    return render(request, 'Capp/masters/form.html', {
        'form': form, 'page_title': 'Import Employees from Excel', 'multipart': True,
        'cancel_url': 'capp_dashboard',
        'locked': [('Reads', 'DATA sheet; IFSC from bank sheets'), ('Matches by', 'ID No.')]})
