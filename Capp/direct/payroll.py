"""D2 - payroll batch lifecycle for a DIRECT company.

DRAFT -> PROCESSED -> APPROVED -> PAID. The calculation and the batch writes live in
Aapp/app/services/payroll_batch.py (shared with Aapp). This module adds the Capp rules:
 * once APPROVED a batch can no longer be reprocessed, reopened or deleted here
   (only a Sapp superadmin can change it back, with a reason);
 * PAID is set here only (Aapp never sets it);
 * every state change is audited.
Every query is scoped to request.owned_company.
"""
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from Aapp.app.salary_processing import (
    MONTH_CHOICES, YEAR_CHOICES, salary_processing, salary_slip)
from Aapp.app.services import payroll_batch as svc
from Capp.audit import log_action
from Capp.direct.checklist import build_checklist
from Capp.direct.guards import direct_perm

MONTHS = dict(MONTH_CHOICES)
ERR_KEY = 'capp_dir_payroll_errors'

# status -> who may do what
CAN_PROCESS = {'DRAFT', 'PROCESSED'}
CAN_REOPEN = {'PROCESSED'}
CAN_FINALIZE = {'PROCESSED'}
CAN_PAY = {'APPROVED'}
CAN_DELETE = {'DRAFT', 'PROCESSED'}


def _label(batch):
    return f'{MONTHS.get(batch.month, batch.month)} {batch.year}'


def _batch(request, pk, lock=False):
    qs = salary_processing.objects.filter(company_id=request.owned_company)
    if lock:
        qs = qs.select_for_update()
    return get_object_or_404(qs, pk=pk)


def _blocked(request, batch, why):
    messages.warning(request, why)
    return redirect('capp_dir_payroll_detail', pk=batch.pk)


@direct_perm('payroll.process')
def capp_dir_payroll(request):
    company = request.owned_company
    today = timezone.localdate()
    if request.method == 'POST':
        try:
            month, year = int(request.POST.get('month')), int(request.POST.get('year'))
        except (TypeError, ValueError):
            month = year = 0
        if month not in MONTHS or year not in YEAR_CHOICES:
            messages.error(request, 'Choose a valid month and year.')
            return redirect('capp_dir_payroll')
        batch, created = svc.create_batch(company, month, year, request.user.username)
        if created:
            log_action(request, 'payroll.create', batch, _label(batch))
            messages.success(request, f'Batch created for {_label(batch)}. Process it next.')
        else:
            messages.info(request, f'A batch already exists for {_label(batch)}.')
        return redirect('capp_dir_payroll_detail', pk=batch.pk)

    return render(request, 'Capp/direct/payroll_list.html', {
        'batches': salary_processing.objects.filter(company_id=company).order_by('-year', '-month'),
        'months': MONTH_CHOICES, 'years': YEAR_CHOICES,
        'current_month': today.month, 'current_year': today.year,
        'month_names': MONTHS,
    })


@direct_perm('payroll.process')
def capp_dir_payroll_detail(request, pk):
    batch = _batch(request, pk)
    return render(request, 'Capp/direct/payroll_detail.html', {
        'batch': batch, 'label': _label(batch),
        'slips': salary_slip.objects.filter(processing_id=batch).select_related('employee_id')
                 .order_by('employee_id__name'),
        'errors': request.session.pop(ERR_KEY, []),
        'can_process': batch.status in CAN_PROCESS,
        'can_reopen': batch.status in CAN_REOPEN,
        'can_finalize': batch.status in CAN_FINALIZE and batch.total_employees > 0,
        'can_pay': batch.status in CAN_PAY,
        'can_delete': batch.status in CAN_DELETE,
        'locked': batch.status in ('APPROVED', 'PAID'),
    })


@direct_perm('payroll.process')
@require_POST
@transaction.atomic
def capp_dir_payroll_process(request, pk):
    batch = _batch(request, pk, lock=True)
    if batch.status not in CAN_PROCESS:
        return _blocked(request, batch, 'An approved batch cannot be processed again.')
    try:
        processed, skipped, error_rows = svc.process_batch(
            batch, request.owned_company, request.user.username)
    except Exception as e:                      # rebuild is one transaction; nothing half-written
        messages.error(request, f'Error processing: {e}')
        return redirect('capp_dir_payroll_detail', pk=batch.pk)
    if error_rows:
        request.session[ERR_KEY] = error_rows
    log_action(request, 'payroll.process', batch,
               f'{_label(batch)}: processed {processed}, skipped {skipped}')
    messages.success(request, f'Salary processed: {processed} employees. Skipped: {skipped}.')
    return redirect('capp_dir_payroll_detail', pk=batch.pk)


@direct_perm('payroll.process')
@require_POST
@transaction.atomic
def capp_dir_payroll_reopen(request, pk):
    batch = _batch(request, pk, lock=True)
    if batch.status not in CAN_REOPEN:
        return _blocked(request, batch, 'Only a processed batch can be reopened.')
    batch.status = 'DRAFT'
    batch.processed_at = None
    batch.updated_by = request.user.username
    batch.save()
    log_action(request, 'payroll.reopen', batch, _label(batch))
    messages.success(request, f'{_label(batch)} reopened as draft.')
    return redirect('capp_dir_payroll_detail', pk=batch.pk)


@direct_perm('payroll.finalize')
def capp_dir_payroll_finalize(request, pk):
    """GET: confirmation page. POST: approve (irreversible in Capp)."""
    if request.method == 'POST':
        return _finalize_post(request, pk)
    batch = _batch(request, pk)
    if batch.status not in CAN_FINALIZE or batch.total_employees < 1:
        return _blocked(request, batch, 'Only a processed batch with employees can be finalized.')
    items = build_checklist(request.owned_company, batch.month, batch.year)
    return render(request, 'Capp/direct/payroll_finalize.html', {
        'batch': batch, 'label': _label(batch), 'items': items,
        'warnings': sum(i['status'] == 'warn' for i in items)})


@transaction.atomic
def _finalize_post(request, pk):
    batch = _batch(request, pk, lock=True)
    if batch.status not in CAN_FINALIZE or batch.total_employees < 1:
        return _blocked(request, batch, 'Only a processed batch with employees can be finalized.')
    svc.approve_batch(batch, request.user.username)
    log_action(request, 'payroll.finalize', batch, _label(batch))
    messages.success(request, f'{_label(batch)} finalized. It is now locked.')
    return redirect('capp_dir_payroll_detail', pk=batch.pk)


@direct_perm('payroll.finalize')
@require_POST
@transaction.atomic
def capp_dir_payroll_paid(request, pk):
    batch = _batch(request, pk, lock=True)
    if batch.status not in CAN_PAY:
        return _blocked(request, batch, 'Only a finalized batch can be marked paid.')
    batch.status = 'PAID'
    batch.updated_by = request.user.username
    batch.save()
    log_action(request, 'payroll.paid', batch, _label(batch))
    messages.success(request, f'{_label(batch)} marked as paid.')
    return redirect('capp_dir_payroll_detail', pk=batch.pk)


@direct_perm('payroll.process')
@require_POST
@transaction.atomic
def capp_dir_payroll_delete(request, pk):
    batch = _batch(request, pk, lock=True)
    if batch.status not in CAN_DELETE:
        return _blocked(request, batch, 'A finalized batch cannot be deleted.')
    label = _label(batch)
    svc.delete_batch(batch)
    log_action(request, 'payroll.delete', None, label)
    messages.success(request, f'Batch for {label} deleted.')
    return redirect('capp_dir_payroll')
