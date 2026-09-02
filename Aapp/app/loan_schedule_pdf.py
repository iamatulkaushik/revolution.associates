"""
Aapp/app/loan_schedule_pdf.py
================================
Print/record PDF for a single Loan or Advance amortization schedule,
per pt_upgrades.md: "generate schedule for print and record".
"""

from datetime import date

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table

from Aapp.app.pdf_engine import (
    build_pdf, doc_styles, INR, table_style, total_row_style, kv_table, section_divider,
)

MONTH_NAMES = {
    1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June',
    7: 'July', 8: 'August', 9: 'September', 10: 'October', 11: 'November', 12: 'December',
}


def loan_advance_schedule_pdf(record):
    """
    record: a Loan or Advance instance. Returns bytes.
    """
    is_loan = hasattr(record, 'loan_id')
    label = "Loan" if is_loan else "Advance"
    record_id = record.loan_id if is_loan else record.advance_id

    styles = doc_styles()
    story = [
        Paragraph(f"{label} Amortization Schedule — #{record_id}", styles['Heading1']),
        Spacer(1, 3 * mm),
    ]

    header_rows = [
        ("Employee", record.employee.name),
        ("Employee Code", record.employee.employeecode),
        ("Principal Amount", INR(record.principal_amount)),
        ("Interest Rate (Annual)", f"{record.interest_rate_annual}%"),
        ("Total Payable", INR(record.total_payable)),
        ("Deduction Mode", record.get_deduction_mode_display()),
        ("Status", record.get_status_display()),
    ]
    story.append(kv_table(header_rows))
    story.append(Spacer(1, 5 * mm))
    story.append(section_divider())
    story.append(Spacer(1, 3 * mm))

    schedule = record.amortization_schedule()
    data = [["Instalment #", "Month", "Year", "Amount"]]
    total = 0
    for row in schedule:
        data.append([
            str(row['instalment_no']),
            MONTH_NAMES[row['month']],
            str(row['year']),
            INR(row['amount']),
        ])
        total += row['amount']
    data.append(["", "", "Total", INR(total)])

    tbl = Table(data, colWidths=[80, 120, 80, 100])
    tbl.setStyle(table_style())
    tbl.setStyle(total_row_style())
    story.append(tbl)

    doc_meta = {
        'title': f"{label} Schedule #{record_id} - {record.employee.name}",
        'doc_number': f"{label[:2].upper()}/{record_id}",
        'doc_date': date.today().strftime('%d-%m-%Y'),
    }
    return build_pdf(story, company=record.company, doc_meta=doc_meta)
