"""
Cxapp/app/tasks.py
====================
django-q2 entry points for Cxapp bulk payslip email and bulk PDF.
Mirrors Aapp/app/tasks.py, kept independent of Aapp's model tree.
"""

import io
import logging
import os

from django.conf import settings
from django_q.tasks import async_task

logger = logging.getLogger('Cxapp')


# ── Bulk email ───────────────────────────────────────────────────────────

def queue_bulk_cx_payslip_emails(company_id, month, year, requested_by_id):
    from Cxapp.app.batch_job import CxBatchJob
    job = CxBatchJob.objects.create(
        job_type=CxBatchJob.JOB_EMAIL,
        company_id=company_id,
        month=month,
        year=year,
        requested_by_id=requested_by_id,
    )
    async_task('Cxapp.app.tasks.run_bulk_cx_payslip_emails_task', job.id)
    return job


def run_bulk_cx_payslip_emails_task(job_id):
    from Cxapp.app.batch_job import CxBatchJob
    from Cxapp.app.payslip_email import send_cx_payslip_email
    from Cxapp.app.process import CxSalary

    job = CxBatchJob.objects.get(id=job_id)
    job.status = CxBatchJob.STATUS_RUNNING
    job.save(update_fields=['status'])

    try:
        qs = CxSalary.objects.filter(
            company_id=job.company_id, salary_month=job.month, salary_year=job.year
        ).select_related('employee')
        sent = 0
        failed_detail = []
        for salary in qs:
            employee = salary.employee
            success, reason = send_cx_payslip_email(salary)
            if success:
                sent += 1
            else:
                failed_detail.append({
                    'employee_id': employee.employee_id,
                    'name': f'{employee.first_name} {employee.last_name}'.strip(),
                    'reason': reason,
                })
        job.sent_count = sent
        job.failed_count = len(failed_detail)
        job.failed_detail = failed_detail
        job.save(update_fields=['sent_count', 'failed_count', 'failed_detail'])
        job.mark_done()
    except Exception as exc:
        logger.exception("Cxapp bulk payslip email task failed: job_id=%s", job_id)
        job.mark_failed(str(exc))


# ── Bulk PDF ─────────────────────────────────────────────────────────────

def queue_bulk_cx_wages_slip_pdf(company_id, month, year, requested_by_id):
    from Cxapp.app.batch_job import CxBatchJob
    job = CxBatchJob.objects.create(
        job_type=CxBatchJob.JOB_PDF,
        company_id=company_id,
        month=month,
        year=year,
        requested_by_id=requested_by_id,
    )
    async_task('Cxapp.app.tasks.run_bulk_cx_wages_slip_pdf_task', job.id)
    return job


def run_bulk_cx_wages_slip_pdf_task(job_id):
    from Cxapp.app.batch_job import CxBatchJob
    from Cxapp.app.salary_pdf import cx_salary_slip_pdf
    from Cxapp.app.process import CxSalary
    from pypdf import PdfReader, PdfWriter

    job = CxBatchJob.objects.get(id=job_id)
    job.status = CxBatchJob.STATUS_RUNNING
    job.save(update_fields=['status'])

    try:
        salaries = list(CxSalary.objects.filter(
            company_id=job.company_id, salary_month=job.month, salary_year=job.year
        ).select_related('employee', 'designation'))

        writer = PdfWriter()
        failed_detail = []
        for sal in salaries:
            try:
                reader = PdfReader(io.BytesIO(cx_salary_slip_pdf(sal)))
                for page in reader.pages:
                    writer.add_page(page)
            except Exception as exc:
                failed_detail.append({
                    'employee_id': sal.employee.employee_id,
                    'name': f'{sal.employee.first_name} {sal.employee.last_name}'.strip(),
                    'reason': str(exc),
                })

        out_dir = os.path.join(settings.MEDIA_ROOT, 'bulk_reports')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f'cx_{job.id}.pdf')
        with open(out_path, 'wb') as f:
            writer.write(f)

        job.file_path = out_path
        job.sent_count = len(salaries) - len(failed_detail)
        job.failed_count = len(failed_detail)
        job.failed_detail = failed_detail
        job.save(update_fields=['file_path', 'sent_count', 'failed_count', 'failed_detail'])
        job.mark_done()
    except Exception as exc:
        logger.exception("Cxapp bulk wages slip PDF task failed: job_id=%s", job_id)
        job.mark_failed(str(exc))
