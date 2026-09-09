"""
Cxapp/app/batch_job_views.py
==============================
Status page + JSON polling endpoint for Cxapp background bulk email
and bulk PDF jobs.
"""

import os

from django.http import JsonResponse, Http404, FileResponse
from django.shortcuts import get_object_or_404, render

from Cxapp.app.batch_job import CxBatchJob


def cxapp_batch_job_status_page(request, job_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_batch_job_status_page)(request, job_id)


def _batch_job_status_page(request, job_id):
    job = get_object_or_404(CxBatchJob, id=job_id, company=request.cx_owner_profile)
    return render(request, 'Cxapp/processing/batch_job_status.html', {'job': job})


def cxapp_batch_job_status_json(request, job_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_batch_job_status_json)(request, job_id)


def _batch_job_status_json(request, job_id):
    job = get_object_or_404(CxBatchJob, id=job_id, company=request.cx_owner_profile)
    return JsonResponse({
        'status': job.status,
        'job_type': job.job_type,
        'sent_count': job.sent_count,
        'failed_count': job.failed_count,
        'failed_detail': job.failed_detail,
        'error': job.error,
        'download_url': (
            f'/cxapp/salary/bulk-job/{job.id}/download/'
            if job.job_type == CxBatchJob.JOB_PDF and job.status == CxBatchJob.STATUS_DONE
            else None
        ),
    })


def cxapp_batch_job_download(request, job_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_batch_job_download)(request, job_id)


def _batch_job_download(request, job_id):
    job = get_object_or_404(
        CxBatchJob, id=job_id, company=request.cx_owner_profile,
        job_type=CxBatchJob.JOB_PDF, status=CxBatchJob.STATUS_DONE,
    )
    if not job.file_path or not os.path.exists(job.file_path):
        raise Http404('File not found.')
    return FileResponse(
        open(job.file_path, 'rb'),
        as_attachment=True,
        filename=f'wages_slips_{job.month}_{job.year}.pdf',
    )
