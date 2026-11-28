"""Capp/foundation/views.py — operator management and audit screen (owner only)."""
from datetime import date

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from Capp.access import capp_perm
from Capp.audit import log_action
from Capp.foundation.models import CappAuditLog, CompanyOperator

def max_operators():
    """Owner decision: at most 5 active operators per company (own limit, apart from employees)."""
    return getattr(settings, 'CAPP_MAX_OPERATORS', 5)


def active_operators(company):
    return CompanyOperator.objects.filter(company=company, is_active=True).count()


NEW_OPERATOR_DEFAULTS = ('can_add_employees', 'can_edit_attendance', 'can_edit_loans')
FLAG_FIELDS = ['can_view_employees', 'can_view_attendance', 'can_view_wages', 'can_view_compliance',
               'can_view_reports', 'can_view_statutory', 'can_download_pdf', 'can_add_employees',
               'can_edit_attendance', 'can_edit_loans', 'can_download_payroll',
               'can_download_challans', 'can_manage_masters', 'can_manage_billing']
DIRECT_ONLY = ('can_manage_masters', 'can_manage_billing')


class OperatorForm(forms.ModelForm):
    username = forms.CharField(max_length=150)
    full_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    password = forms.CharField(widget=forms.PasswordInput, required=False,
                               help_text='Required for a new operator.')

    class Meta:
        model = CompanyOperator
        fields = FLAG_FIELDS

    def __init__(self, *a, mode='ASSOCIATE', **k):
        super().__init__(*a, **k)
        if self.instance.pk:
            u = self.instance.user
            self.fields['username'].initial = u.username
            self.fields['username'].disabled = True
            self.fields['full_name'].initial = u.get_full_name()
            self.fields['email'].initial = u.email
            self.fields['password'].help_text = 'Leave blank to keep the current password.'
        if not self.instance.pk:                  # a new operator starts able to do data entry
            for f in NEW_OPERATOR_DEFAULTS:
                self.fields[f].initial = True
        if mode != 'DIRECT':                      # masters/billing are DIRECT-only rights
            for f in DIRECT_ONLY:
                self.fields[f].disabled = True
                self.fields[f].help_text = 'Available to direct companies only.'
        order = ['username', 'full_name', 'email', 'password'] + FLAG_FIELDS
        self.order_fields(order)

    def clean_username(self):
        v = self.cleaned_data['username'].strip()
        if not self.instance.pk and User.objects.filter(username__iexact=v).exists():
            raise forms.ValidationError('This username is taken.')
        return v

    def clean_password(self):
        pw = self.cleaned_data.get('password', '')
        if not self.instance.pk and not pw:
            raise forms.ValidationError('Password is required.')
        if pw:
            validate_password(pw)
        return pw

    def clean(self):
        d = super().clean()
        if self.fields['can_manage_masters'].disabled:
            d['can_manage_masters'] = d['can_manage_billing'] = False
        return d


@capp_perm('operators.manage')
def capp_operator_list(request):
    ops = CompanyOperator.objects.filter(company=request.owned_company).select_related('user')
    return render(request, 'Capp/foundation/operator_list.html', {
        'page_title': 'Operators', 'operators': ops,
        'active': active_operators(request.owned_company), 'limit': max_operators()})


@capp_perm('operators.manage')
def capp_operator_edit(request, pk=None):
    company = request.owned_company
    inst = get_object_or_404(CompanyOperator, pk=pk, company=company) if pk else None
    form = OperatorForm(request.POST or None, instance=inst, mode=request.capp_mode)
    if request.method == 'POST' and form.is_valid() and inst is None \
            and active_operators(company) >= max_operators():
        form.add_error(None, f'You already have {max_operators()} active operators (the maximum). '
                             'Suspend one before adding another.')
    elif request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        op = form.save(commit=False)
        if inst is None:
            user = User.objects.create_user(d['username'], d['email'], d['password'])
            op.user, op.company, op.created_by = user, company, request.user
        else:
            user = inst.user
            if d['password']:
                user.set_password(d['password'])
            user.email = d['email']
        user.first_name = d['full_name'][:150]
        user.save()
        op.save()
        log_action(request, 'operator_create' if inst is None else 'operator_update', op,
                   user.username)
        messages.success(request, 'Operator saved.')
        return redirect('capp_operator_list')
    return render(request, 'Capp/masters/form.html', {
        'form': form, 'page_title': 'Edit Operator' if pk else 'Add Operator',
        'cancel_url': 'capp_operator_list'})


@capp_perm('operators.manage')
def capp_operator_toggle(request, pk):
    op = get_object_or_404(CompanyOperator, pk=pk, company=request.owned_company)
    if request.method == 'POST' and not op.is_active and \
            active_operators(request.owned_company) >= max_operators():
        messages.error(request, f'Maximum {max_operators()} active operators. Suspend another first.')
    elif request.method == 'POST':
        op.is_active = not op.is_active
        op.suspended_reason = '' if op.is_active else 'Suspended by owner'
        op.save(update_fields=['is_active', 'suspended_reason'])
        log_action(request, 'operator_enable' if op.is_active else 'operator_suspend', op,
                   op.user.username)
        messages.success(request, f"Operator {'enabled' if op.is_active else 'suspended'}.")
    return redirect('capp_operator_list')


@capp_perm('operators.manage')
def capp_audit_list(request):
    qs = CappAuditLog.objects.filter(company=request.owned_company)
    g = request.GET
    if g.get('user'):
        qs = qs.filter(username__icontains=g['user'])
    if g.get('action'):
        qs = qs.filter(action__icontains=g['action'])
    for key, lookup in (('from', 'at__date__gte'), ('to', 'at__date__lte')):
        try:
            qs = qs.filter(**{lookup: date.fromisoformat(g[key])}) if g.get(key) else qs
        except ValueError:
            messages.error(request, f'Bad "{key}" date. Use YYYY-MM-DD.')
    page = Paginator(qs, 50).get_page(g.get('page'))
    return render(request, 'Capp/foundation/audit_list.html', {
        'page_title': 'Audit Log', 'page': page, 'q': g})
