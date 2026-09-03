"""
Sapp/app/audit_trail.py
==========================
Audit log for changes to Designation, Salary, and Attendance tables,
per pt_upgrades.md: "special watch log table for designation, Salary,
Attandance", "available only to Sapp Module", "anychanges in
selected/mentioned tables logtable entry for proper use/user/cause".

Signal receivers here are module-level functions (not nested in a
class/form — the exact bug pattern already fixed once in this codebase
for State/District, and just fixed again in Sapp/app/bank.py). They
are connected explicitly in Sapp/apps.py's ready(), not relied upon to
"just work" from decoration alone, so the connection is visible and
traceable in one place.

Access: views in this module check request.user.is_superuser (or
whatever the Sapp-role check is — see get_object_or_404 gate below);
Aapp/Cxapp have no views into this log at all, matching "available
only to Sapp Module".
"""

from django.db import models
from django.db.models.signals import post_save, post_delete, pre_save
from django.forms.widgets import Select, TextInput

from Sapp.middleware import get_current_user, get_current_ip


ACTION_CHOICES = [
    ('create', 'Created'),
    ('update', 'Updated'),
    ('delete', 'Deleted'),
]

WATCHED_TABLE_CHOICES = [
    ('designation', 'Designation'),
    ('salary_slip', 'Salary Slip'),
    ('attendance', 'Attendance'),
]


class AuditLogEntry(models.Model):
    """One row per detected change on a watched table."""
    log_id = models.AutoField(primary_key=True)
    table_name = models.CharField(max_length=30, choices=WATCHED_TABLE_CHOICES)
    record_id = models.CharField(max_length=50, help_text="Primary key of the changed record, as text")
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)

    changed_by_username = models.CharField(max_length=150, null=True, blank=True,
                                            help_text="Null if change happened outside a request (e.g. management command)")
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    field_changes = models.JSONField(null=True, blank=True,
                                      help_text='{"field": {"old": ..., "new": ...}, ...} — best-effort diff')
    cause = models.CharField(max_length=255, blank=True,
                              help_text="Optional free-text reason, set by the view before saving when available")

    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'Sapp'
        db_table = 'sa_audit_log'
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['table_name', 'occurred_at']),
            models.Index(fields=['record_id']),
        ]
        verbose_name = "Audit Log Entry"
        verbose_name_plural = "Audit Log Entries"

    def __str__(self):
        return f"[{self.occurred_at}] {self.table_name} #{self.record_id} {self.action} by {self.changed_by_username or 'system'}"


# =====================================================================
# Change detection helpers
# =====================================================================

# Fields to track per watched model. Kept explicit (not "all fields")
# so the diff stays readable and doesn't churn on auto_now/updated_at
# timestamp fields on every save.
TRACKED_FIELDS = {
    'designation': ['basicpay', 'hra', 'da', 'ed_epf_per', 'ed_professionaltax', 'ed_income_tax'],
    'salary_slip': ['gross_earnings', 'net_pay', 'total_deductions', 'income_tax', 'professional_tax'],
    'attendance': ['working_days', 'overtime_hours', 'present_days'],
}

# Cache of pre-save snapshots, keyed by (model_label, pk), so post_save
# can compute a diff without a second DB query. Cleared per-entry once
# consumed. This is process-local and fine for a single-worker/thread
# save; under heavy concurrent writes to the *same* row it's a
# best-effort diff, not a transactional guarantee — acceptable for an
# audit trail (the row is only used for the changed-fields display, not
# as a source of truth for the salary numbers themselves).
_pre_save_snapshots = {}


def _snapshot_key(instance):
    return (instance.__class__.__name__, instance.pk)


def capture_pre_save_snapshot(sender, instance, **kwargs):
    """pre_save receiver — module-level function, connected in apps.py."""
    if instance.pk is None:
        return  # new record, nothing to diff against

    table_key = _table_key_for_sender(sender)
    if not table_key:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    snapshot = {f: getattr(old, f, None) for f in TRACKED_FIELDS.get(table_key, [])}
    _pre_save_snapshots[_snapshot_key(instance)] = snapshot


def log_save(sender, instance, created, **kwargs):
    """post_save receiver — module-level function, connected in apps.py."""
    table_key = _table_key_for_sender(sender)
    if not table_key:
        return

    key = _snapshot_key(instance)
    old_snapshot = _pre_save_snapshots.pop(key, None)

    field_changes = None
    if not created and old_snapshot is not None:
        diff = {}
        for field in TRACKED_FIELDS.get(table_key, []):
            new_val = getattr(instance, field, None)
            old_val = old_snapshot.get(field)
            if old_val != new_val:
                diff[field] = {'old': str(old_val), 'new': str(new_val)}
        field_changes = diff or None
        if field_changes is None:
            return  # no tracked field actually changed — don't log a no-op

    user = get_current_user()
    AuditLogEntry.objects.create(
        table_name=table_key,
        record_id=str(instance.pk),
        action='create' if created else 'update',
        changed_by_username=user.username if user else None,
        ip_address=get_current_ip() or None,
        field_changes=field_changes,
    )


def log_delete(sender, instance, **kwargs):
    """post_delete receiver — module-level function, connected in apps.py."""
    table_key = _table_key_for_sender(sender)
    if not table_key:
        return

    user = get_current_user()
    AuditLogEntry.objects.create(
        table_name=table_key,
        record_id=str(instance.pk),
        action='delete',
        changed_by_username=user.username if user else None,
        ip_address=get_current_ip() or None,
    )


def _table_key_for_sender(sender):
    """Maps a model class to its WATCHED_TABLE_CHOICES key, or None if not watched."""
    name = sender.__name__
    if name == 'designation':
        return 'designation'
    if name == 'salary_slip':
        return 'salary_slip'
    if name == 'attendance':
        return 'attendance'
    return None


def connect_audit_signals():
    """
    Called once from Sapp/apps.py's ready(). Imports the watched models
    here (not at module top) to avoid the app-loading-order problems
    that caused the original State/District signal bug — models must
    be fully loaded before connecting signals against them.
    """
    from Aapp.app.designation import designation
    from Aapp.app.salary_processing import salary_slip
    from Aapp.app.attandance import attendance

    for model in (designation, salary_slip, attendance):
        pre_save.connect(capture_pre_save_snapshot, sender=model, weak=False, dispatch_uid=f'audit_presave_{model.__name__}')
        post_save.connect(log_save, sender=model, weak=False, dispatch_uid=f'audit_postsave_{model.__name__}')
        post_delete.connect(log_delete, sender=model, weak=False, dispatch_uid=f'audit_delete_{model.__name__}')


# =====================================================================
# VIEWS — Sapp-only access
# =====================================================================

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages


def _require_sapp(request):
    """Sapp access gate — superuser check, matching Sapp's existing admin-only pattern."""
    return request.user.is_authenticated and request.user.is_superuser


@staff_member_required
def audit_log_list(request):
    if not _require_sapp(request):
        messages.error(request, 'Audit trail is available to Sapp administrators only.')
        return redirect('/')

    table_filter = request.GET.get('table', '')
    logs = AuditLogEntry.objects.all()
    if table_filter:
        logs = logs.filter(table_name=table_filter)
    logs = logs.order_by('-occurred_at')[:500]  # cap for page load; older entries via export

    rows = [{
        'cells': [
            l.occurred_at.strftime('%d-%m-%Y %H:%M:%S'), l.get_table_name_display(),
            l.record_id, l.get_action_display(), l.changed_by_username or 'system',
            l.ip_address or '-',
            ', '.join(l.field_changes.keys()) if l.field_changes else '-',
        ],
        'actions': [],
    } for l in logs]

    return render(request, 'Sapp/audit/list.html', {
        'page_title': 'Audit Trail',
        'columns': ['Timestamp', 'Table', 'Record ID', 'Action', 'Changed By', 'IP Address', 'Fields Changed'],
        'rows': rows,
        'table_filter': table_filter,
        'watched_tables': WATCHED_TABLE_CHOICES,
    })


@staff_member_required
def audit_log_detail(request, log_id):
    if not _require_sapp(request):
        messages.error(request, 'Audit trail is available to Sapp administrators only.')
        return redirect('/')

    from django.shortcuts import get_object_or_404
    entry = get_object_or_404(AuditLogEntry, log_id=log_id)
    return render(request, 'Sapp/audit/detail.html', {'entry': entry})
