"""
Aapp/app/payslip_email.py
==========================
Emails generated payslip PDFs to employees. Reuses salary_slip_pdf()
byte output (same PDF as download_salary_slip) as an email attachment
rather than a browser download.

Two entry points:
  - send_payslip_email(rec)      : one employee, one salary_slip record
  - send_bulk_payslip_emails(...) : whole company for a month/year,
    skips employees with no email on file, returns a per-employee result
    list so the calling view can show a summary instead of a blind
    "done" message.

Failures are per-employee and never raise — one bad address shouldn't
stop the rest of the run. Matches the fail-silently-and-log approach
used in Cxapp/app/email_verify.py and Sapp/app/password_reset.py.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMessage

from Aapp.app.salary_pdf import salary_slip_pdf, _wages_qs

logger = logging.getLogger('Aapp')

MONTH_NAMES = {
    1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June',
    7: 'July', 8: 'August', 9: 'September', 10: 'October', 11: 'November', 12: 'December',
}


def send_payslip_email(rec):
    """Email one salary_slip record's PDF to its employee.
    Returns (success: bool, reason: str)."""
    emp = rec.employee_id
    email = (emp.email or '').strip()
    if not email:
        return False, 'No email on file'

    month = rec.processing_id.month
    year = rec.processing_id.year
    month_name = MONTH_NAMES.get(month, str(month))
    company_name = rec.company_id.company_name

    try:
        pdf_bytes = salary_slip_pdf(rec)
    except Exception:
        logger.exception("Payslip PDF generation failed: employee='%s'", emp.employeecode)
        return False, 'PDF generation failed'

    try:
        msg = EmailMessage(
            subject=f'Salary Slip — {month_name} {year} — {company_name}',
            body=(
                f'Dear {emp.first_name if hasattr(emp, "first_name") else emp.employeecode},\n\n'
                f'Please find attached your salary slip for {month_name} {year}.\n\n'
                f'This is a system-generated email. For any queries, please contact HR.\n\n'
                f'— {company_name}'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach(f'Salary_Slip_{emp.employeecode}_{month}_{year}.pdf', pdf_bytes, 'application/pdf')
        msg.send(fail_silently=False)
        logger.info("Payslip emailed: employee='%s' month=%s year=%s", emp.employeecode, month, year)
        return True, 'Sent'
    except Exception:
        logger.exception("Payslip email send failed: employee='%s'", emp.employeecode)
        return False, 'Send failed'


def send_bulk_payslip_emails(company, month, year):
    """Email payslips to every employee with a wage record and an email
    on file for the given company/month/year. Returns a list of dicts:
    [{'employeecode', 'name', 'success', 'reason'}, ...]"""
    qs = _wages_qs(company, month, year)
    results = []
    for rec in qs:
        emp = rec.employee_id
        success, reason = send_payslip_email(rec)
        results.append({
            'employeecode': emp.employeecode,
            'name': f'{getattr(emp, "first_name", "")} {getattr(emp, "last_name", "")}'.strip() or emp.employeecode,
            'success': success,
            'reason': reason,
        })
    return results
