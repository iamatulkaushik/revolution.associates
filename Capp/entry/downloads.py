"""
Capp/entry/downloads.py — payroll downloads for BOTH modes (track AI-3, package E4).

One gate: the month's batch must be APPROVED (Capp/entry/gates.py).
Permission: payroll.download (owner needs can_view_wages + can_download_pdf;
operator needs can_view_wages + can_download_payroll).
Salary PDFs use Aapp's pure builders. Background wages-slips file reuses Aapp's BatchJob queue (migration added, INVENTORY R8).
"""
import io
import os
from datetime import date

from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from Capp.access import capp_perm
from Capp.audit import log_action
from Capp.entry.gates import batch_for, is_final, not_final_message

MAX_INSTANT_SLIPS = 150      # = copper plan limit; bigger batches use the background file


def _period(request, month=None, year=None):
    try:
        month = int(month if month is not None else request.GET.get('month', date.today().month))
        year = int(year if year is not None else request.GET.get('year', date.today().year))
    except (TypeError, ValueError):
        raise Http404('Bad period.')
    if not (1 <= month <= 12 and 2000 <= year <= 2100):
        raise Http404('Bad period.')
    return month, year


def _gate(request, month, year):
    """Return None when allowed, else a redirect to the hub with the reason."""
    batch = batch_for(request.owned_company, month, year)
    if is_final(batch):
        return None
    messages.error(request, not_final_message(batch, month, year))
    return redirect(f"{reverse('capp_ent_dl_hub')}?month={month}&year={year}")


def _pdf(data, fname):
    return HttpResponse(data, content_type='application/pdf',
                        headers={'Content-Disposition': f'attachment; filename="{fname}"'})


@capp_perm('payroll.download')
def capp_ent_dl_hub(request):
    company = request.owned_company
    month, year = _period(request)
    batch = batch_for(company, month, year)
    slips = batch.salary_slip_set.count() if batch else 0
    return render(request, 'Capp/entry/downloads_hub.html', {
        'page_title': 'Downloads', 'month': month, 'year': year, 'months': list(range(1, 13)),
        'batch': batch, 'final': is_final(batch), 'slip_count': slips,
        'instant_ok': 0 < slips <= MAX_INSTANT_SLIPS, 'max_instant': MAX_INSTANT_SLIPS,
        'blocked_reason': '' if is_final(batch) else not_final_message(batch, month, year)})


@capp_perm('payroll.download')
def capp_ent_dl_sheet(request, month, year):
    month, year = _period(request, month, year)
    blocked = _gate(request, month, year)
    if blocked:
        return blocked
    from Aapp.app.salary_pdf import salary_sheet_pdf
    pdf = salary_sheet_pdf(request.owned_company, month, year)
    log_action(request, 'download_salary_sheet', None, f'{month:02d}/{year}')
    return _pdf(pdf, f'SalarySheet_{month}_{year}.pdf')


@capp_perm('payroll.download')
def capp_ent_dl_abstract(request, month, year):
    month, year = _period(request, month, year)
    blocked = _gate(request, month, year)
    if blocked:
        return blocked
    from Aapp.app.salary_pdf import salary_abstract_pdf
    pdf = salary_abstract_pdf(request.owned_company, month, year)
    log_action(request, 'download_salary_abstract', None, f'{month:02d}/{year}')
    return _pdf(pdf, f'SalaryAbstract_{month}_{year}.pdf')


@capp_perm('payroll.download')
def capp_ent_dl_slip(request, slip_id):
    from Aapp.app.salary_pdf import salary_slip_pdf
    from Aapp.app.salary_processing import salary_slip
    rec = get_object_or_404(salary_slip.objects.select_related('employee_id', 'processing_id'),
                            id=slip_id, company_id=request.owned_company)
    month, year = rec.processing_id.month, rec.processing_id.year
    blocked = _gate(request, month, year)
    if blocked:
        return blocked
    log_action(request, 'download_salary_slip', rec, f'{rec.employee_id.employeecode} {month:02d}/{year}')
    return _pdf(salary_slip_pdf(rec),
                f'Slip_{rec.employee_id.employeecode}_{month}_{year}.pdf')


@capp_perm('payroll.download')
def capp_ent_dl_slips_all(request, month, year):
    month, year = _period(request, month, year)
    blocked = _gate(request, month, year)
    if blocked:
        return blocked
    from pypdf import PdfReader, PdfWriter
    from Aapp.app.salary_pdf import salary_slip_pdf
    from Aapp.app.salary_processing import salary_slip
    slips = list(salary_slip.objects.filter(
        company_id=request.owned_company, processing_id__month=month, processing_id__year=year,
    ).select_related('employee_id', 'processing_id').order_by('employee_id__employeecode'))
    if not slips:
        raise Http404('No slips.')
    if len(slips) > MAX_INSTANT_SLIPS:
        messages.error(request, f'{len(slips)} slips are too many for an instant file '
                                f'(limit {MAX_INSTANT_SLIPS}). Use the background wages-slips file below.')
        return redirect(f"{reverse('capp_ent_dl_hub')}?month={month}&year={year}")
    writer = PdfWriter()
    for rec in slips:
        for page in PdfReader(io.BytesIO(salary_slip_pdf(rec))).pages:
            writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    log_action(request, 'download_all_slips', None, f'{month:02d}/{year}: {len(slips)} slips')
    return _pdf(buf.getvalue(), f'AllSlips_{month}_{year}.pdf')


# ── background wages-slips file (Aapp BatchJob queue) ────────────────────────

@capp_perm('payroll.download')
def capp_ent_dl_wages_job_start(request, month, year):
    month, year = _period(request, month, year)
    if request.method != 'POST':
        return redirect(f"{reverse('capp_ent_dl_hub')}?month={month}&year={year}")
    blocked = _gate(request, month, year)
    if blocked:
        return blocked
    from Aapp.app.tasks import queue_bulk_wages_slip_pdf
    job = queue_bulk_wages_slip_pdf(request.owned_company.pk, month, year, request.user.pk)
    log_action(request, 'queue_wages_slips', None, f'{month:02d}/{year}: job {job.pk}')
    return redirect('capp_ent_dl_job', job_id=job.pk)


def _job(request, job_id):
    from Aapp.app.batch_job import BatchJob
    return get_object_or_404(BatchJob, id=job_id, company_id=request.owned_company,
                             job_type=BatchJob.JOB_PDF)


@capp_perm('payroll.download')
def capp_ent_dl_job(request, job_id):
    return render(request, 'Capp/entry/job.html', {'page_title': 'Wages slips file',
                                                   'job': _job(request, job_id)})


@capp_perm('payroll.download')
def capp_ent_dl_job_json(request, job_id):
    job = _job(request, job_id)
    done = job.status == job.STATUS_DONE
    return JsonResponse({
        'status': job.status, 'ok': job.sent_count, 'failed': job.failed_count, 'error': job.error,
        'download_url': reverse('capp_ent_dl_job_file', args=[job.pk]) if done else None})


@capp_perm('payroll.download')
def capp_ent_dl_job_file(request, job_id):
    job = _job(request, job_id)
    if job.status != job.STATUS_DONE or not job.file_path or not os.path.exists(job.file_path):
        raise Http404('File not ready.')
    log_action(request, 'download_wages_slips', None, f'job {job.pk}')
    return FileResponse(open(job.file_path, 'rb'), as_attachment=True,
                        filename=f'wages_slips_{job.month}_{job.year}.pdf')
