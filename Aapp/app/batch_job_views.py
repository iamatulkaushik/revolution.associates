"""
Aapp/app/batch_job_views.py
=============================
Status page + JSON polling endpoint for background bulk jobs
(email and PDF). Same pattern for both job types.
"""

import os

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404, FileResponse
from django.shortcuts import get_object_or_404, render

from Aapp.app.batch_job import BatchJob


def _company(request):
    from Aapp.app.salary_processing import _get_selected_company
    return _get_selected_company(request)


@login_required
def batch_job_status_page(request, job_id):
    """Renders the polling page. JS on the page hits batch_job_status_json."""
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    job = get_object_or_404(BatchJob, id=job_id, company_id=company)
    return render(request, 'Aapp/salary/batch_job_status.html', {'job': job})


@login_required
def batch_job_status_json(request, job_id):
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    job = get_object_or_404(BatchJob, id=job_id, company_id=company)
    return JsonResponse({
        'status': job.status,
        'job_type': job.job_type,
        'sent_count': job.sent_count,
        'failed_count': job.failed_count,
        'failed_detail': job.failed_detail,
        'error': job.error,
        'download_url': (
            f'/salary/reports/bulk-job/{job.id}/download/'
            if job.job_type == BatchJob.JOB_PDF and job.status == BatchJob.STATUS_DONE
            else None
        ),
    })


@login_required
def batch_job_download(request, job_id):
    """Serves the finished bulk PDF from disk."""
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    job = get_object_or_404(
        BatchJob, id=job_id, company_id=company,
        job_type=BatchJob.JOB_PDF, status=BatchJob.STATUS_DONE,
    )
    if not job.file_path or not os.path.exists(job.file_path):
        raise Http404('File not found.')
    return FileResponse(
        open(job.file_path, 'rb'),
        as_attachment=True,
        filename=f'wages_slips_{job.month}_{job.year}.pdf',
    )
