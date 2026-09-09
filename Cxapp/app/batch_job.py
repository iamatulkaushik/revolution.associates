"""
Cxapp/app/batch_job.py
========================
Job-status model for Cxapp background bulk email. Mirrors
Aapp/app/batch_job.py but stays in Cxapp's independent model tree —
no cross-app FK into Aapp.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class CxBatchJob(models.Model):
    JOB_EMAIL = 'email'
    JOB_PDF = 'pdf'
    JOB_TYPE_CHOICES = [
        (JOB_EMAIL, 'Bulk Payslip Email'),
        (JOB_PDF, 'Bulk Payslip PDF'),
    ]

    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    job_type = models.CharField(max_length=10, choices=JOB_TYPE_CHOICES, default=JOB_EMAIL)
    company = models.ForeignKey('Cxapp.CxOwnerProfile', on_delete=models.CASCADE)
    month = models.PositiveSmallIntegerField()
    year = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_QUEUED)

    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    failed_detail = models.JSONField(default=list, blank=True)
    file_path = models.CharField(max_length=500, blank=True, default='')

    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']

    def mark_done(self):
        self.status = self.STATUS_DONE
        self.finished_at = timezone.now()
        self.save(update_fields=['status', 'finished_at'])

    def mark_failed(self, error_text):
        self.status = self.STATUS_FAILED
        self.error = error_text[:5000]
        self.finished_at = timezone.now()
        self.save(update_fields=['status', 'error', 'finished_at'])

    def __str__(self):
        return f'Bulk Email — {self.company} {self.month}/{self.year} ({self.status})'
