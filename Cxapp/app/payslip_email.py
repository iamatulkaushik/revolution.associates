"""
Cxapp/app/payslip_email.py
============================
Emails generated payslip PDFs to Cxapp employees. Reuses
cx_salary_slip_pdf() byte output (same PDF as the owner/HR download
and the employee self-service download) as an email attachment.

Email lives on CxEmployeeContact.email (not on CxEmployee directly).
Employees without a contact record or without an email on file are
skipped and reported back — never raises.

Two entry points:
  - send_cx_payslip_email(salary)                 : one CxSalary record
  - send_bulk_cx_payslip_emails(company, m, y)     : whole company, one month
"""

import logging

from django.conf import settings
from django.core.mail import EmailMessage

from Cxapp.app.salary_pdf import cx_salary_slip_pdf
from Cxapp.app.process import CxSalary

logger = logging.getLogger('Cxapp')

MONTH_NAMES = {
    1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June',
    7: 'July', 8: 'August', 9: 'September', 10: 'October', 11: 'November', 12: 'December',
}


def send_cx_payslip_email(salary):
    """Email one CxSalary record's PDF to its employee.
    Returns (success: bool, reason: str)."""
    employee = salary.employee
    contact = getattr(employee, 'contact', None)
    email = (contact.email if contact else '').strip()
    if not email:
        return False, 'No email on file'

    month_name = MONTH_NAMES.get(salary.salary_month, str(salary.salary_month))
    year = salary.salary_year
    company_name = salary.company.company.company_name

    try:
        pdf_bytes = cx_salary_slip_pdf(salary)
    except Exception:
        logger.exception("Cxapp payslip PDF generation failed: employee_id='%s'", employee.employee_id)
        return False, 'PDF generation failed'

    try:
        msg = EmailMessage(
            subject=f'Salary Slip — {month_name} {year} — {company_name}',
            body=(
                f'Dear {employee.first_name},\n\n'
                f'Please find attached your salary slip for {month_name} {year}.\n\n'
                f'This is a system-generated email. For any queries, please contact your employer.\n\n'
                f'— {company_name}'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach(f'Salary_Slip_{employee.employee_id}_{salary.salary_month}_{year}.pdf',
                   pdf_bytes, 'application/pdf')
        msg.send(fail_silently=False)
        logger.info("Cxapp payslip emailed: employee_id='%s' month=%s year=%s",
                    employee.employee_id, salary.salary_month, year)
        return True, 'Sent'
    except Exception:
        logger.exception("Cxapp payslip email send failed: employee_id='%s'", employee.employee_id)
        return False, 'Send failed'


def send_bulk_cx_payslip_emails(company, month, year):
    """Email payslips to every employee with a CxSalary record for the
    given company/month/year. Returns a list of dicts:
    [{'employee_id', 'name', 'success', 'reason'}, ...]"""
    qs = CxSalary.objects.filter(company=company, salary_month=month, salary_year=year).select_related('employee')
    results = []
    for salary in qs:
        employee = salary.employee
        success, reason = send_cx_payslip_email(salary)
        results.append({
            'employee_id': employee.employee_id,
            'name': f'{employee.first_name} {employee.last_name}'.strip(),
            'success': success,
            'reason': reason,
        })
    return results
