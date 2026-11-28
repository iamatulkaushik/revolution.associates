"""
Aapp/app/company_operators.py — the associate sees and suspends the company's operators.

Operators are Capp users created by the company owner (Capp.CompanyOperator). The associate
may suspend or re-enable them (owner decision). Only associates (and superusers) with access
to the selected company; sub-users cannot. Re-enabling respects the 5-active-operator cap.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from Sapp.app.company import Company


def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


def _allowed(request, company):
    user = request.user
    if user.is_superuser:
        return True
    profile = getattr(user, 'associate_profile', None)
    return bool(profile and profile.companyid.filter(company_id=company.pk).exists())


def _guard(request):
    company = _company(request)
    if company is None:
        messages.warning(request, 'Please select a company first.')
        return None, redirect('aapp_dashboard')
    if not _allowed(request, company):
        messages.error(request, 'Only the associate of this company can manage its operators.')
        return None, redirect('aapp_dashboard')
    return company, None


@login_required
def list_company_operators_aapp(request):
    company, bounce = _guard(request)
    if bounce:
        return bounce
    from Capp.foundation.views import active_operators, max_operators
    ops = company.operators.select_related('user').order_by('user__username')
    rows = [{
        'cells': [o.user.username, o.user.get_full_name() or None,
                  'Active' if o.is_active else 'Suspended', o.created_at.strftime('%d-%m-%Y'),
                  o.last_login_ip],
        'actions': [{'label': 'Suspend' if o.is_active else 'Enable',
                     'url': reverse('toggle_company_operator_aapp', args=[o.pk]), 'css': 'delete' if o.is_active else ''}],
    } for o in ops]
    return render(request, 'Aapp/operators/list_operators.html', {
        'page_title': f'Company Operators — {company.company_name}',
        'columns': ['Username', 'Name', 'Status', 'Created', 'Last login IP'],
        'rows': rows, 'operators': ops, 'company': company,
        'active': active_operators(company), 'limit': max_operators()})


@login_required
def toggle_company_operator_aapp(request, operator_id):
    company, bounce = _guard(request)
    if bounce:
        return bounce
    from Capp.foundation.views import active_operators, max_operators
    op = get_object_or_404(company.operators, pk=operator_id)
    if request.method == 'POST':
        if not op.is_active and active_operators(company) >= max_operators():
            messages.error(request, f'Maximum {max_operators()} active operators. Suspend another first.')
        else:
            op.is_active = not op.is_active
            op.suspended_reason = '' if op.is_active else f'Suspended by associate {request.user.username}'
            op.save(update_fields=['is_active', 'suspended_reason'])
            messages.success(request, f"Operator {op.user.username} {'enabled' if op.is_active else 'suspended'}.")
    return redirect('list_company_operators_aapp')
