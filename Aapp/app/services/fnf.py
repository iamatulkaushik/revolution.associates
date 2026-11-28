"""Full and Final settlement and relieving, shared by Aapp and Capp (D6).

PDFs: (pdf bytes, filename) out, same filenames as the old Aapp downloads (fnf_settlement_<id>.pdf,
<type>_certificate_<id>.pdf). Raises StatutoryFileError for an unknown certificate type and
FileBuildError if a PDF cannot be built.

The calculation itself stays in FnFSettlement.compute() (Aapp, unchanged). compute_settlement wraps it so
it is safe to run again: the computed fields are reset first, the manual asset amount is passed in
explicitly (compute() adds the pending asset recoveries on top of whatever is in the field), and the
statutory gratuity ceiling is applied, which compute() does not do.

Status changes (finalize, mark paid) and relieving are plain functions with no request.
"""
import logging
from datetime import date
from decimal import Decimal

from django.utils import timezone

from Aapp.app.services.statutory_files import FileBuildError, StatutoryFileError

logger = logging.getLogger(__name__)

GRATUITY_CEILING = Decimal('2000000')      # Payment of Gratuity (Amendment) Act 2018
CERT_TYPES = ('experience', 'last_pay', 'character')
ZERO = Decimal('0')


def build_fnf_statement_pdf(settlement):
    from Aapp.app.fnf_pdf import fnf_settlement_pdf
    try:
        pdf = fnf_settlement_pdf(settlement)
    except Exception as e:
        logger.exception('FnF statement PDF failed for settlement=%s: %s', settlement.settlement_id, e)
        raise FileBuildError('Could not generate the settlement statement.')
    return pdf, f'fnf_settlement_{settlement.settlement_id}.pdf'


def build_fnf_certificate_pdf(settlement, cert_type):
    from Aapp.app.fnf_pdf import fnf_certificate_pdf
    if cert_type not in CERT_TYPES:
        raise StatutoryFileError('Unknown certificate type')
    try:
        pdf = fnf_certificate_pdf(settlement, cert_type)
    except Exception as e:
        logger.exception('FnF certificate PDF failed for settlement=%s: %s', settlement.settlement_id, e)
        raise FileBuildError('Could not generate the certificate.')
    return pdf, f'{cert_type}_certificate_{settlement.settlement_id}.pdf'


def compute_settlement(settlement, manual_asset=ZERO):
    """Fill every computed field from the employee's live records. Does not save.

    manual_asset: asset recovery raised outside the asset module; pending asset recoveries are added
    to it by compute(). Safe to call repeatedly.
    """
    settlement.leave_encashment_days = ZERO
    settlement.leave_encashment_amount = ZERO
    settlement.notice_pay_recovery = ZERO
    settlement.gratuity_amount = ZERO
    settlement.loan_outstanding_recovery = ZERO
    settlement.advance_outstanding_recovery = ZERO
    settlement.asset_recovery_amount = manual_asset or ZERO
    settlement.compute()
    if settlement.gratuity_amount > GRATUITY_CEILING:
        settlement.gratuity_amount = GRATUITY_CEILING
        settlement.net_settlement_amount = (settlement.total_earnings - settlement.total_recoveries).quantize(
            Decimal('0.01'))
    return settlement


def manual_asset_part(settlement):
    """The part of the stored asset recovery that did not come from the asset module."""
    from Aapp.app.asset_management import get_pending_asset_recovery
    return max((settlement.asset_recovery_amount or ZERO) - get_pending_asset_recovery(settlement.employee), ZERO)


def finalize_settlement(settlement):
    settlement.status = 'finalized'
    settlement.finalized_at = timezone.now()
    settlement.save(update_fields=['status', 'finalized_at', 'updated_at'])


def mark_paid(settlement):
    """Settlement paid: pending asset recoveries are now recovered, active loans and advances are
    cleared (their balance was recovered in the settlement)."""
    from Aapp.app.asset_management import AssetRecovery
    from Aapp.app.loans_advances import Advance, Loan
    settlement.status = 'paid'
    settlement.paid_at = timezone.now()
    settlement.save(update_fields=['status', 'paid_at', 'updated_at'])
    emp = settlement.employee
    AssetRecovery.objects.filter(employee=emp, status='pending').update(status='recovered', resolved_on=date.today())
    for model in (Loan, Advance):
        model.objects.filter(employee=emp, status='active').update(status='completed')


def relieve_employee(emp, leaving_date, reason):
    emp.is_working = False
    emp.dateofleaving = leaving_date
    emp.leaving_reason = reason
    emp.save()
    return emp
