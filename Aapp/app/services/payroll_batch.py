"""Salary batch lifecycle, extracted from Aapp/app/salary_processing.py (D2).

Pure functions: they take a company / batch and a username, never a request.
Behaviour is identical to the views they were taken from; the Aapp views now
call these, and Capp (DIRECT mode) calls them too. Status guards live in the
callers, exactly as before (Aapp blocks only APPROVED).
"""
from collections import namedtuple
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

ProcessResult = namedtuple('ProcessResult', 'processed skipped error_rows')


def create_batch(company, month, year, username):
    """Get-or-create the DRAFT batch. Returns (batch, created)."""
    from Aapp.app.salary_processing import salary_processing
    existing = salary_processing.objects.filter(
        company_id=company, month=month, year=year).first()
    if existing:
        return existing, False
    batch = salary_processing.objects.create(
        company_id=company, month=month, year=year, status='DRAFT', created_by=username)
    return batch, True


def process_batch(batch, company, username):
    """Rebuild every slip of the batch and mark it PROCESSED.

    Raises whatever the database raises; the whole rebuild is one transaction.
    """
    from Aapp.app.employee import employee
    from Aapp.app.salary_processing import (
        _decimal_round, calculate_employee_salary, salary_slip)

    with transaction.atomic():
        salary_slip.objects.filter(processing_id=batch).delete()

        employees = employee.objects.filter(
            CompanyID=company, is_working=True
        ).select_related('perm_state', 'temp_state', 'designationID')

        processed = 0
        skipped = 0
        error_rows = []
        total_gross = Decimal('0')
        total_deductions = Decimal('0')
        total_net = Decimal('0')
        total_employer = Decimal('0')

        for emp in employees:
            desig = emp.designationID

            if not desig:
                skipped += 1
                error_rows.append(f'{emp.employeecode} - {emp.name}: No designation assigned')
                continue

            try:
                calc = calculate_employee_salary(emp, desig, batch.month, batch.year, company=company)

                salary_slip.objects.create(
                    processing_id=batch,
                    employee_id=emp,
                    company_id=company,
                    designation_id=desig,
                    **calc,
                    created_by=username,
                )

                total_gross += calc['gross_earnings']
                total_deductions += calc['total_deductions']
                total_net += calc['net_pay']
                total_employer += calc['employer_total_cost']
                processed += 1

            except Exception as e:
                skipped += 1
                error_rows.append(f'{emp.employeecode} - {emp.name}: {str(e)}')

        batch.total_employees = processed
        batch.total_gross = _decimal_round(total_gross)
        batch.total_deductions = _decimal_round(total_deductions)
        batch.total_net = _decimal_round(total_net)
        batch.total_employer_cost = _decimal_round(total_employer)
        batch.status = 'PROCESSED'
        batch.processed_at = timezone.now()
        batch.updated_by = username
        batch.save()

    return ProcessResult(processed, skipped, error_rows)


def approve_batch(batch, username):
    batch.status = 'APPROVED'
    batch.approved_at = timezone.now()
    batch.updated_by = username
    batch.save()


def delete_batch(batch):
    batch.delete()
