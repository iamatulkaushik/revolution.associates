"""
Aapp/app/tasks.py
===================
django-q2 entry points. Each queue_* function is called from the view
(fast, returns immediately). Each *_task function runs in the qcluster
worker process and does the actual slow work, writing results to a
BatchJob row instead of returning them to a browser.
"""

import io
import logging
import os

from django.conf import settings
from django_q.tasks import async_task

logger = logging.getLogger('Aapp')


# ── Bulk email ───────────────────────────────────────────────────────────

def queue_bulk_payslip_emails(company_id, month, year, requested_by_id):
    from Aapp.app.batch_job import BatchJob
    job = BatchJob.objects.create(
        job_type=BatchJob.JOB_EMAIL,
        company_id_id=company_id,
        month=month,
        year=year,
        requested_by_id=requested_by_id,
    )
    async_task('Aapp.app.tasks.run_bulk_payslip_emails_task', job.id)
    return job


def run_bulk_payslip_emails_task(job_id):
    from Aapp.app.batch_job import BatchJob
    from Aapp.app.payslip_email import send_payslip_email
    from Aapp.app.salary_pdf import _wages_qs

    job = BatchJob.objects.get(id=job_id)
    job.status = BatchJob.STATUS_RUNNING
    job.save(update_fields=['status'])

    try:
        qs = _wages_qs(job.company_id, job.month, job.year)
        sent = 0
        failed_detail = []
        for rec in qs:
            emp = rec.employee_id
            success, reason = send_payslip_email(rec)
            if success:
                sent += 1
            else:
                failed_detail.append({
                    'employeecode': emp.employeecode,
                    'name': f'{getattr(emp, "first_name", "")} {getattr(emp, "last_name", "")}'.strip()
                            or emp.employeecode,
                    'reason': reason,
                })
        job.sent_count = sent
        job.failed_count = len(failed_detail)
        job.failed_detail = failed_detail
        job.save(update_fields=['sent_count', 'failed_count', 'failed_detail'])
        job.mark_done()
    except Exception as exc:
        logger.exception("Bulk payslip email task failed: job_id=%s", job_id)
        job.mark_failed(str(exc))


# ── Bulk PDF ─────────────────────────────────────────────────────────────

def queue_bulk_wages_slip_pdf(company_id, month, year, requested_by_id):
    from Aapp.app.batch_job import BatchJob
    job = BatchJob.objects.create(
        job_type=BatchJob.JOB_PDF,
        company_id_id=company_id,
        month=month,
        year=year,
        requested_by_id=requested_by_id,
    )
    async_task('Aapp.app.tasks.run_bulk_wages_slip_pdf_task', job.id)
    return job


def run_bulk_wages_slip_pdf_task(job_id):
    from Aapp.app.batch_job import BatchJob
    from Aapp.app.statutory.wages_act import wages_slip_pdf
    from Aapp.app.salary_processing import salary_processing, salary_slip
    from pypdf import PdfReader, PdfWriter

    job = BatchJob.objects.get(id=job_id)
    job.status = BatchJob.STATUS_RUNNING
    job.save(update_fields=['status'])

    try:
        batch = salary_processing.objects.filter(
            company_id=job.company_id, month=job.month, year=job.year
        ).first()
        slips = list(
            salary_slip.objects.filter(processing_id=batch)
            .select_related('employee_id', 'designation_id')
            .order_by('employee_id__employeecode')
        ) if batch else []

        writer = PdfWriter()
        failed_detail = []
        for slip in slips:
            try:
                pdf_bytes = wages_slip_pdf(job.company_id, slip)
                reader = PdfReader(io.BytesIO(pdf_bytes))
                for page in reader.pages:
                    writer.add_page(page)
            except Exception as exc:
                failed_detail.append({
                    'employeecode': slip.employee_id.employeecode,
                    'name': slip.employee_id.employeecode,
                    'reason': str(exc),
                })

        out_dir = os.path.join(settings.MEDIA_ROOT, 'bulk_reports')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f'{job.id}.pdf')
        with open(out_path, 'wb') as f:
            writer.write(f)

        job.file_path = out_path
        job.sent_count = len(slips) - len(failed_detail)
        job.failed_count = len(failed_detail)
        job.failed_detail = failed_detail
        job.save(update_fields=['file_path', 'sent_count', 'failed_count', 'failed_detail'])
        job.mark_done()
    except Exception as exc:
        logger.exception("Bulk wages slip PDF task failed: job_id=%s", job_id)
        job.mark_failed(str(exc))
