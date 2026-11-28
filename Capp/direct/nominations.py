"""D5b-2 - nomination and declaration registers for a DIRECT company.

EPF nomination (Form 2), ESI family declaration (Form 1A / 1B), gratuity nominee (Form F) and
Leave With Wages (Form 15). Company-wide records with entry screens (add, edit, delete) plus a PDF
download of the register. Everything is scoped to request.owned_company; the employee choice is
limited to that company's own staff. Records only: none of these change salary.

Gates (fail-closed, from get_company_gates): the EPF nomination needs the EPFO number, the ESI
family declaration the ESIC number, Leave With Wages the Shop Act number. The gratuity nominee
register has no registration gate. Aapp's plan-feature gating is not applied in Capp.
Permissions: view employees.view, change employees.edit, PDF challan.download.
"""
import re
from datetime import date
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.db.models import Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from Aapp.app.employee import employee
from Aapp.app.epf_esi import EpfNomination, EsiFamilyMember
from Aapp.app.factory_act import LeaveWithWagesRegister
from Aapp.app.gratuity import gratuity_nominee
from Aapp.app.services import nominations as nom
from Aapp.app.services.statutory_files import StatutoryFileError
from Aapp.app.statutory_gates import get_company_gates
from Capp.audit import log_action
from Capp.direct.guards import direct_perm

DATE = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')
ZERO, HUNDRED = Decimal('0'), Decimal('100')


# ── forms ─────────────────────────────────────────────────────────────────────
class _Base(forms.ModelForm):
    """Common clean-up. Subclasses set ALL_STAFF to include relieved employees."""
    ALL_STAFF = False
    SHARE_FILTER = None            # extra filter for "other nominees" when checking the 100% cap

    def __init__(self, *a, company=None, **k):
        super().__init__(*a, **k)
        self.company = company
        for f in self.fields.values():
            f.widget.attrs.setdefault('class', 'form-control')
        base = employee.objects.filter(CompanyID=company)
        if not self.ALL_STAFF:
            keep = Q(is_working=True)
            if self.instance.pk:
                keep |= Q(employeeid=self.instance.employee_id)
            base = base.filter(keep)
        self.fields['employee'].queryset = base.order_by('name')

    # field level checks, applied only to the fields a form actually has
    def clean(self):
        d = super().clean()
        pats = {'aadhar_number': (r'\d{12}', 'Aadhaar must be 12 digits.'),
                'pan_number': (r'[A-Z]{5}\d{4}[A-Z]', 'PAN must look like ABCDE1234F.'),
                'bank_ifsc': (r'[A-Z]{4}0[A-Z0-9]{6}', 'IFSC must look like SBIN0001234.'),
                'bank_account': (r'\d{9,18}', 'Account number must be 9 to 18 digits.')}
        for name, (pat, msg) in pats.items():
            v = (d.get(name) or '').strip()
            if name in ('pan_number', 'bank_ifsc'):
                v = v.upper()
            if name in self.fields:
                d[name] = v
                if v and not re.fullmatch(pat, v):
                    self.add_error(name, msg)
        today = date.today()
        for name in ('date_of_birth', 'nomination_date'):
            if d.get(name) and d[name] > today:
                self.add_error(name, 'Date cannot be in the future.')
        if d.get('is_minor') and 'guardian_name' in self.fields and not (d.get('guardian_name') or '').strip():
            self.add_error('guardian_name', 'Guardian name is required for a minor nominee.')
        if 'share_percent' in self.fields:
            self._check_share(d)
        return d

    def _check_share(self, d):
        share, emp = d.get('share_percent'), d.get('employee')
        if share is None:
            return
        if not ZERO < share <= HUNDRED:
            self.add_error('share_percent', 'Share must be above 0 and at most 100.')
            return
        if emp is None:
            return
        others = self._meta.model.objects.filter(company=self.company, employee=emp)
        if self.SHARE_FILTER:
            others = others.filter(**self.SHARE_FILTER)
        if self.instance.pk:
            others = others.exclude(pk=self.instance.pk)
        used = others.aggregate(t=Sum('share_percent'))['t'] or ZERO
        if used + share > HUNDRED:
            self.add_error('share_percent',
                           f'Other nominees already hold {used}%. This share can be at most {HUNDRED - used}%.')


class EpfNominationForm(_Base):
    SHARE_FILTER = {'is_active': True}

    class Meta:
        model = EpfNomination
        fields = ['employee', 'nominee_name', 'relationship', 'date_of_birth', 'address', 'share_percent',
                  'aadhar_number', 'bank_account', 'bank_ifsc', 'bank_name', 'is_minor',
                  'guardian_name', 'guardian_relationship', 'guardian_address',
                  'is_eps_nominee', 'nomination_date']
        widgets = {'date_of_birth': DATE, 'nomination_date': DATE}


class GratuityNomineeForm(_Base):
    class Meta:
        model = gratuity_nominee
        fields = ['employee', 'nominee_name', 'relationship', 'gender', 'share_percent', 'date_of_birth',
                  'address', 'aadhar_number', 'pan_number', 'bank_account', 'bank_ifsc', 'bank_name',
                  'is_minor', 'guardian_name', 'guardian_relationship']
        widgets = {'date_of_birth': DATE}


class EsiFamilyForm(_Base):
    class Meta:
        model = EsiFamilyMember
        fields = ['employee', 'member_name', 'relationship', 'date_of_birth', 'gender', 'aadhar_number',
                  'is_dependent', 'is_residing_with']
        widgets = {'date_of_birth': DATE}


class LeaveWagesForm(_Base):
    ALL_STAFF = True

    class Meta:
        model = LeaveWithWagesRegister
        fields = ['employee', 'year', 'opening_balance', 'leave_earned', 'leave_availed',
                  'leave_lapsed', 'leave_encashed', 'encashment_amount']

    def clean(self):
        d = super().clean()
        for name in ('opening_balance', 'leave_earned', 'leave_availed', 'leave_lapsed',
                     'leave_encashed', 'encashment_amount'):
            if d.get(name) is not None and d[name] < 0:
                self.add_error(name, 'Cannot be negative.')
        year = d.get('year')
        if year is not None and not 2000 <= year <= date.today().year + 1:
            self.add_error('year', 'Enter a valid year.')
        if self.errors:
            return d
        if d['leave_availed'] + d['leave_lapsed'] + d['leave_encashed'] > d['opening_balance'] + d['leave_earned']:
            raise forms.ValidationError('Leave availed, lapsed and encashed cannot exceed opening balance plus earned.')
        if d['encashment_amount'] > 0 and d['leave_encashed'] == 0:
            self.add_error('encashment_amount', 'Enter the encashed days before an encashment amount.')
        return d


class RemoveForm(forms.Form):
    date_removed = forms.DateField(widget=DATE, label='Date removed')
    reason_for_removal = forms.CharField(max_length=255, label='Reason')

    def __init__(self, *a, member=None, **k):
        super().__init__(*a, **k)
        self.member = member
        for f in self.fields.values():
            f.widget.attrs.setdefault('class', 'form-control')

    def clean_date_removed(self):
        v = self.cleaned_data['date_removed']
        if v > date.today():
            raise forms.ValidationError('Date cannot be in the future.')
        if self.member and self.member.date_added and v < self.member.date_added:
            raise forms.ValidationError('Date cannot be before the member was added.')
        return v


# ── register config ───────────────────────────────────────────────────────────
def _mask(aadhaar):
    return f'XXXXXXXX{aadhaar[-4:]}' if aadhaar and len(aadhaar) >= 4 else '—'


def _emp(e):
    return f'{e.employeecode} - {e.name}'


def _epf_row(r):
    return [_emp(r.employee), r.nominee_name, r.get_relationship_display(), f'{r.share_percent}%',
            'Yes' if r.is_eps_nominee else 'No', r.nomination_date.strftime('%d-%b-%Y')]


def _grat_row(r):
    return [_emp(r.employee), r.nominee_name, r.get_relationship_display(), f'{r.share_percent}%',
            _mask(r.aadhar_number), 'Yes' if r.is_minor else 'No']


def _esi_row(r):
    status = 'Active' if not r.date_removed else f'Removed {r.date_removed.strftime("%d-%b-%Y")}'
    return [_emp(r.employee), r.member_name, r.get_relationship_display(),
            r.date_of_birth.strftime('%d-%b-%Y') if r.date_of_birth else '—', status]


def _leave_row(r):
    bal = r.opening_balance + r.leave_earned - r.leave_availed - r.leave_lapsed - r.leave_encashed
    return [_emp(r.employee), r.year, r.opening_balance, r.leave_earned, r.leave_availed,
            r.leave_lapsed, r.leave_encashed, r.encashment_amount, bal]


def _stamp(obj, company, user):
    obj.company = company
    obj.created_by = user


NOMS = {
    'epf-nominations': {
        'title': 'EPF nomination (Form 2)', 'form': EpfNominationForm, 'model': EpfNomination,
        'pk': 'nomination_id', 'scope': lambda c: {'company': c}, 'gate': 'epf', 'gate_label': 'EPFO number',
        'columns': ['Employee', 'Nominee', 'Relationship', 'Share', 'EPS nominee', 'Date'],
        'row': _epf_row, 'build': nom.build_epf_nomination_register_pdf, 'save': _stamp,
        'order': ('employee__name', 'nominee_name'), 'share_filter': {'is_active': True},
    },
    'esi-family': {
        'title': 'ESI family declaration (Form 1A)', 'form': EsiFamilyForm, 'model': EsiFamilyMember,
        'pk': 'member_id', 'scope': lambda c: {'company': c}, 'gate': 'esi', 'gate_label': 'ESIC number',
        'columns': ['Employee', 'Member', 'Relationship', 'Date of birth', 'Status'],
        'row': _esi_row, 'build': nom.build_esi_family_register_pdf, 'save': _stamp,
        'order': ('employee__name', 'relationship'), 'removable': True,
    },
    'gratuity-nominees': {
        'title': 'Gratuity nominee (Form F)', 'form': GratuityNomineeForm, 'model': gratuity_nominee,
        'pk': 'nominee_id', 'scope': lambda c: {'company': c}, 'gate': None, 'gate_label': '',
        'columns': ['Employee', 'Nominee', 'Relationship', 'Share', 'Aadhaar', 'Minor'],
        'row': _grat_row, 'build': nom.build_gratuity_nominee_register_pdf, 'save': _stamp,
        'order': ('employee__name', 'nominee_name'), 'share_filter': {},
    },
    'leave-wages': {
        'title': 'Leave with wages (Form 15)', 'form': LeaveWagesForm, 'model': LeaveWithWagesRegister,
        'pk': 'leave_register_id', 'scope': lambda c: {'employee__CompanyID': c}, 'gate': 'shop_act',
        'gate_label': 'Shop and Establishment Act number',
        'columns': ['Employee', 'Year', 'Opening', 'Earned', 'Availed', 'Lapsed', 'Encashed',
                    'Encashment (Rs)', 'Balance'],
        'row': _leave_row, 'build': nom.build_leave_wages_register_pdf, 'save': lambda o, c, u: None,
        'order': ('-year', 'employee__name'),
    },
}


def _cfg(key):
    if key not in NOMS:
        raise Http404('Unknown register.')
    return NOMS[key]


def _off(cfg, company):
    """Message when the company's registration for this register is missing, else ''."""
    g = cfg['gate']
    if g and not get_company_gates(company)[g]:
        return (f'The {cfg["gate_label"]} is not on file, so this register is off. '
                'Add it under Statutory setup.')
    return ''


def _back(key):
    return reverse('capp_dir_nom_list', args=[key])


def _blocked(request, cfg, company, key):
    msg = _off(cfg, company)
    if msg:
        messages.error(request, msg)
        return redirect(_back(key))
    return None


def _share_warnings(cfg, rows_qs):
    f = cfg.get('share_filter')
    if f is None:
        return []
    totals = {}
    for r in rows_qs.filter(**f):
        t = totals.setdefault(r.employee_id, [r.employee.name, ZERO])
        t[1] += r.share_percent
    return [f'{n}: nominee shares total {t}%, not 100%.' for n, t in sorted(totals.values()) if t != HUNDRED]


# ── views ─────────────────────────────────────────────────────────────────────
@direct_perm('employees.view')
def capp_dir_nominations(request):
    company = request.owned_company
    items = [(k, v['title'], reverse('capp_dir_nom_list', args=[k]), not _off(v, company))
             for k, v in NOMS.items()]
    return render(request, 'Capp/direct/nom_hub.html', {'items': items})


@direct_perm('employees.view')
def capp_dir_nom_list(request, key):
    cfg, company = _cfg(key), request.owned_company
    off = _off(cfg, company)
    rows, warnings = [], []
    if not off:
        qs = (cfg['model'].objects.filter(**cfg['scope'](company))
              .select_related('employee').order_by(*cfg['order']))
        rows = [{'cells': cfg['row'](r), 'pk': getattr(r, cfg['pk']),
                 'removable': bool(cfg.get('removable')) and not r.date_removed} for r in qs]
        warnings = _share_warnings(cfg, qs)
    return render(request, 'Capp/direct/nom_list.html', {
        'key': key, 'title': cfg['title'], 'columns': cfg['columns'], 'rows': rows,
        'off': off, 'warnings': warnings, 'removable': bool(cfg.get('removable'))})


@direct_perm('employees.edit')
def capp_dir_nom_add(request, key):
    cfg, company = _cfg(key), request.owned_company
    blocked = _blocked(request, cfg, company, key)
    if blocked:
        return blocked
    form = cfg['form'](request.POST or None, company=company)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        cfg['save'](obj, company, request.user)
        obj.save()
        log_action(request, f'nomination.{key}.add', obj, cfg['title'])
        messages.success(request, 'Entry saved.')
        return redirect(_back(key))
    return render(request, 'Capp/direct/register_form.html', {
        'form': form, 'title': f'Add: {cfg["title"]}', 'back': _back(key)})


@direct_perm('employees.edit')
def capp_dir_nom_edit(request, key, pk):
    cfg, company = _cfg(key), request.owned_company
    blocked = _blocked(request, cfg, company, key)
    if blocked:
        return blocked
    obj = get_object_or_404(cfg['model'], **{cfg['pk']: pk}, **cfg['scope'](company))
    form = cfg['form'](request.POST or None, instance=obj, company=company)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        log_action(request, f'nomination.{key}.edit', obj, cfg['title'])
        messages.success(request, 'Entry updated.')
        return redirect(_back(key))
    return render(request, 'Capp/direct/register_form.html', {
        'form': form, 'title': f'Edit: {cfg["title"]}', 'back': _back(key)})


@direct_perm('employees.edit')
@require_POST
def capp_dir_nom_delete(request, key, pk):
    cfg, company = _cfg(key), request.owned_company
    blocked = _blocked(request, cfg, company, key)
    if blocked:
        return blocked
    obj = get_object_or_404(cfg['model'], **{cfg['pk']: pk}, **cfg['scope'](company))
    log_action(request, f'nomination.{key}.delete', obj, cfg['title'])
    obj.delete()
    messages.success(request, 'Entry deleted.')
    return redirect(_back(key))


@direct_perm('employees.edit')
def capp_dir_nom_remove(request, key, pk):
    """ESI Form 1B: mark a family member as removed (kept in the register, shown as Removed)."""
    cfg, company = _cfg(key), request.owned_company
    if not cfg.get('removable'):
        raise Http404('Not available for this register.')
    blocked = _blocked(request, cfg, company, key)
    if blocked:
        return blocked
    member = get_object_or_404(cfg['model'], **{cfg['pk']: pk}, **cfg['scope'](company))
    if member.date_removed:
        messages.error(request, 'This family member is already marked as removed.')
        return redirect(_back(key))
    form = RemoveForm(request.POST or None, member=member, initial={'date_removed': date.today()})
    if request.method == 'POST' and form.is_valid():
        member.date_removed = form.cleaned_data['date_removed']
        member.reason_for_removal = form.cleaned_data['reason_for_removal']
        member.save()
        log_action(request, f'nomination.{key}.remove', member, cfg['title'])
        messages.success(request, 'Family member marked as removed (Form 1B).')
        return redirect(_back(key))
    return render(request, 'Capp/direct/register_form.html', {
        'form': form, 'title': f'Remove {member.member_name} (Form 1B)', 'back': _back(key)})


@direct_perm('challan.download')
def capp_dir_nom_download(request, key):
    cfg, company = _cfg(key), request.owned_company
    blocked = _blocked(request, cfg, company, key)
    if blocked:
        return blocked
    try:
        pdf, fname = cfg['build'](company)
    except StatutoryFileError as e:
        messages.error(request, str(e))
        return redirect(_back(key))
    log_action(request, 'report.download', None, cfg['title'])
    r = HttpResponse(pdf, content_type='application/pdf')
    r['Content-Disposition'] = f'attachment; filename="{fname}"'
    return r
