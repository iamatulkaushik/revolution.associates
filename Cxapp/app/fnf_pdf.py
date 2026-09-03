"""
Cxapp/app/fnf_pdf.py
=======================
FnF settlement statement and certificate PDFs for the Cxapp portal.
Reuses Aapp.app.pdf_engine directly (pure utility, no models) — same
pattern as Cxapp/app/salary_pdf.py.
"""

from datetime import date

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer

from Aapp.app.pdf_engine import build_pdf, doc_styles, INR, kv_table, section_divider


def cx_fnf_settlement_pdf(settlement):
    styles = doc_styles()
    emp = settlement.employee
    date_of_joining = getattr(getattr(emp, 'employment', None), 'date_of_joining', None)

    story = [
        Paragraph(f"Full &amp; Final Settlement Statement — #{settlement.settlement_id}", styles['Heading1']),
        Spacer(1, 3 * mm),
    ]

    header_rows = [
        ("Employee", emp.name),
        ("Employee Code", emp.employee_code),
        ("Date of Joining", date_of_joining.strftime('%d-%m-%Y') if date_of_joining else '-'),
        ("Last Working Day", settlement.last_working_day.strftime('%d-%m-%Y')),
        ("Status", settlement.get_status_display()),
    ]
    story.append(kv_table(header_rows))
    story.append(Spacer(1, 5 * mm))
    story.append(section_divider())

    story.append(Paragraph("Earnings", styles['Heading2']))
    earning_rows = [
        ("Pending Salary", INR(settlement.pending_salary)),
        ("Leave Encashment", f"{INR(settlement.leave_encashment_amount)} ({settlement.leave_encashment_days} days)"),
        ("Notice Pay (if excess served)", INR(max(settlement.notice_pay_recovery, 0))),
        ("Gratuity", INR(settlement.gratuity_amount)),
        ("Total Earnings", INR(settlement.total_earnings)),
    ]
    story.append(kv_table(earning_rows))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Deductions / Recoveries", styles['Heading2']))
    deduction_rows = [
        ("Notice Shortfall Recovery", INR(abs(min(settlement.notice_pay_recovery, 0)))),
        ("Loan Outstanding", INR(settlement.loan_outstanding_recovery)),
        ("Advance Outstanding", INR(settlement.advance_outstanding_recovery)),
        ("Asset Recovery", INR(settlement.asset_recovery_amount)),
        ("Other Deductions", INR(settlement.other_deductions)),
        ("Total Recoveries", INR(settlement.total_recoveries)),
    ]
    story.append(kv_table(deduction_rows))
    story.append(Spacer(1, 5 * mm))
    story.append(section_divider())
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(
        f"<b>Net Settlement Amount: {INR(settlement.net_settlement_amount)}</b>", styles['Heading1']
    ))

    doc_meta = {
        'title': f"FnF Settlement #{settlement.settlement_id} - {emp.name}",
        'doc_number': f"FNF/{settlement.settlement_id}",
        'doc_date': date.today().strftime('%d-%m-%Y'),
    }
    return build_pdf(story, company=settlement.company, doc_meta=doc_meta)


def cx_fnf_certificate_pdf(settlement, cert_type):
    emp = settlement.employee
    date_of_joining = getattr(getattr(emp, 'employment', None), 'date_of_joining', None)
    styles = doc_styles()

    doj_str = date_of_joining.strftime('%d-%m-%Y') if date_of_joining else '-'
    lwd_str = settlement.last_working_day.strftime('%d-%m-%Y')

    if cert_type == 'experience':
        title = "Experience Certificate"
        body = (
            f"This is to certify that {emp.name} (Employee Code: {emp.employee_code}) was employed "
            f"with this organization from {doj_str} to {lwd_str}. During this period, their conduct "
            f"and performance were found satisfactory. We wish them success in their future endeavours."
        )
    elif cert_type == 'last_pay':
        title = "Last Pay Certificate"
        body = (
            f"This is to certify that {emp.name} (Employee Code: {emp.employee_code}) has been paid "
            f"their full and final dues as per the settlement statement dated "
            f"{date.today().strftime('%d-%m-%Y')}, with a net settlement amount of "
            f"{INR(settlement.net_settlement_amount)}. This certificate may be used for reference "
            f"by any future employer or financial institution regarding last drawn pay and dues clearance."
        )
    else:  # character
        title = "Character Certificate"
        body = (
            f"This is to certify that {emp.name} (Employee Code: {emp.employee_code}) has, to the best "
            f"of our knowledge, maintained good conduct, punctuality, and behaviour during their tenure "
            f"with this organization from {doj_str} to {lwd_str}. No disciplinary action was pending "
            f"against them at the time of separation, unless otherwise noted in company records."
        )

    story = [
        Paragraph(title, styles['Heading1']),
        Spacer(1, 6 * mm),
        Paragraph(body, styles['Normal']),
        Spacer(1, 10 * mm),
        Paragraph("Authorized Signatory", styles['Small']),
    ]

    doc_meta = {
        'title': f"{title} - {emp.name}",
        'doc_number': f"CERT/{cert_type.upper()}/{settlement.settlement_id}",
        'doc_date': date.today().strftime('%d-%m-%Y'),
    }
    return build_pdf(story, company=settlement.company, doc_meta=doc_meta)
