"""Capp/entry/gates.py — the single "is payroll final?" rule for every download.

Finalized = batch status APPROVED. PAID is accepted for forward compatibility only:
Aapp never sets it today (docs/capp_upgrade/INVENTORY.md R1).
"""
from Aapp.app.salary_processing import salary_processing

FINAL_STATUSES = ('APPROVED', 'PAID')


def batch_for(company, month, year):
    return salary_processing.objects.filter(company_id=company, month=month, year=year).first()


def is_final(batch):
    return batch is not None and batch.status in FINAL_STATUSES


def not_final_message(batch, month, year):
    if batch is None:
        return f'No payroll batch exists for {month:02d}/{year} yet.'
    return (f'The {month:02d}/{year} payroll batch is {batch.get_status_display() if hasattr(batch, "get_status_display") else batch.status}. '
            'Downloads open after the batch is approved. Ask your associate to approve it.')


def entry_lock_reason(company, mode, month, year):
    """Why attendance/loan ENTRY for this month is locked, or None (decision D7).

    ASSOCIATE: locked as soon as the associate processes the batch (not DRAFT).
    DIRECT:    owner may keep editing while the batch is DRAFT or PROCESSED
               (then reprocess); locked once it is APPROVED.
    """
    batch = batch_for(company, month, year)
    if batch is None:
        return None
    if mode == 'DIRECT':
        if batch.status in FINAL_STATUSES:
            return f'The {month:02d}/{year} batch is approved. Entry is closed.'
        return None
    if batch.status != 'DRAFT':
        return (f'Your associate has already processed the {month:02d}/{year} payroll. '
                'Entry is closed. Ask your associate to reopen it.')
    return None
