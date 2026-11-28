"""D1 - statutory registration setup for a DIRECT company (edits company_statury).

Registration numbers decide deductions and challans through get_company_gates():
number on file = scheme switched on, blank = off. This screen only edits that
row; it never computes anything itself.
"""
import re
from datetime import date

from django import forms
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from Aapp.app.statutory_gates import get_company_gates, lwf_allowed
from Capp.audit import log_action
from Capp.direct.guards import direct_perm
from Sapp.app.company import company_statury

GSTIN_RE = re.compile(r'^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$')
LICENCE_RE = re.compile(r'^[A-Za-z0-9/\-]{1,15}$')

LABELS = {
    'epfo': 'EPF', 'esic': 'ESIC', 'shop_act': 'Shop Act',
    'labour': 'Labour Welfare (LWF)', 'pt_number': 'Professional Tax',
}

# (title, help text, fields) - drives the page layout.
GROUPS = [
    ('EPF (Provident Fund)',
     'Switches on EPF deduction and the ECR file. Leave blank if not registered.',
     ['epfo', 'epfo_date']),
    ('ESIC',
     'Switches on ESI deduction and the ESI challan. Leave blank if not registered.',
     ['esic', 'esic_date']),
    ('Shop & Establishment Act',
     'Needed for overtime, wages registers and leave balances. LWF also needs it.',
     ['shop_act', 'shop_act_date']),
    ('Labour Welfare Fund (LWF)',
     'Switches on LWF deduction and challan. Needs the Shop Act number as well.',
     ['labour', 'labour_from', 'labour_to']),
    ('Professional Tax',
     'Switches on PT deduction. State-wise slabs are applied automatically by work location.',
     ['pt_number', 'pt_date']),
    ('GST and other licences',
     'Kept on file. They do not change payroll.',
     ['gst', 'gst_date', 'psara', 'psara_from', 'psara_to',
      'factory', 'factory_from', 'factory_to']),
]

FIELDS = [f for _, _, fs in GROUPS for f in fs]


class StatutoryForm(forms.ModelForm):
    class Meta:
        model = company_statury
        fields = FIELDS
        widgets = {f: forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')
                   for f in FIELDS if f.endswith(('_date', '_from', '_to'))}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        for f in self.fields.values():
            f.widget.attrs.setdefault('class', 'form-control')

    def _text(self, name, upper=False):
        v = (self.cleaned_data.get(name) or '').strip()
        return v.upper() if upper else v

    def clean_epfo(self):
        v = self._text('epfo', upper=True)
        if v and not (len(v) == 15 and v.isalnum()):
            raise forms.ValidationError('EPF code must be exactly 15 letters or digits.')
        return v or None

    def clean_esic(self):
        v = self._text('esic')
        if v and not (v.isdigit() and len(v) == 17):
            raise forms.ValidationError('ESIC code must be exactly 17 digits.')
        return v or None

    def clean_gst(self):
        v = self._text('gst', upper=True)
        if v and not GSTIN_RE.match(v):
            raise forms.ValidationError('Enter a valid 15-character GSTIN, e.g. 06ABCDE1234F1Z5.')
        return v or None

    def _licence(self, name):
        v = self._text(name)
        if v and not LICENCE_RE.match(v):
            raise forms.ValidationError('Up to 15 letters, digits, "/" or "-".')
        return v or None

    def clean_shop_act(self):  return self._licence('shop_act')
    def clean_labour(self):    return self._licence('labour')
    def clean_pt_number(self): return self._licence('pt_number')
    def clean_psara(self):     return self._licence('psara')
    def clean_factory(self):   return self._licence('factory')

    def clean(self):
        data = super().clean()
        today = date.today()
        for name in FIELDS:
            if name.endswith('_date') and data.get(name) and data[name] > today:
                self.add_error(name, 'Registration date cannot be in the future.')
        for start, end in (('labour_from', 'labour_to'), ('psara_from', 'psara_to'),
                           ('factory_from', 'factory_to')):
            if data.get(start) and data.get(end) and data[end] < data[start]:
                self.add_error(end, 'End date cannot be before the start date.')
        return data


def _gate_rows(company):
    g = get_company_gates(company)
    return [
        ('EPF deduction and ECR', g['epf']),
        ('ESI deduction and challan', g['esi']),
        ('Shop Act (overtime, registers)', g['shop_act']),
        ('Labour Welfare deduction and challan', lwf_allowed(g)),
        ('Professional Tax deduction', g['pt']),
        ('Income tax (needs company TAN, set under Company details)', g['income_tax']),
    ]


def _change_detail(form, before):
    parts = [f'{n}: {before.get(n) or "-"} -> {form.cleaned_data.get(n) or "-"}'
             for n in form.changed_data]
    return '; '.join(parts)


def _warn_removed(request, form, before):
    for name, label in LABELS.items():
        if before.get(name) and not form.cleaned_data.get(name):
            messages.warning(request, f'{label} number removed. Its deduction and files stop '
                                      'from the next payroll run. Processed months are unchanged.')
    if form.cleaned_data.get('labour') and not form.cleaned_data.get('shop_act'):
        messages.warning(request, 'LWF stays off until the Shop Act number is also entered.')


@direct_perm('statutory.edit')
def capp_dir_statutory(request):
    company = request.owned_company
    # Same lookup as get_company_gates(), so this screen edits the row the gates read.
    row = company_statury.objects.filter(company=company).first()
    before = {f: getattr(row, f, None) for f in FIELDS}
    form = StatutoryForm(request.POST or None, instance=row)

    if request.method == 'POST' and form.is_valid():
        if not form.has_changed():
            messages.info(request, 'No changes to save.')
            return redirect('capp_dir_statutory')
        obj = form.save(commit=False)
        if not obj.pk:
            obj.created_by = request.user.username
        obj.company = company
        obj.updated_by = request.user.username
        obj.updated_at = timezone.now()
        obj.save()
        log_action(request, 'statutory.update', obj, _change_detail(form, before))
        _warn_removed(request, form, before)
        messages.success(request, 'Statutory details saved.')
        return redirect('capp_dir_statutory')

    return render(request, 'Capp/direct/statutory.html', {
        'form': form,
        'groups': [(t, h, [form[f] for f in fs]) for t, h, fs in GROUPS],
        'gates': _gate_rows(company),
    })
