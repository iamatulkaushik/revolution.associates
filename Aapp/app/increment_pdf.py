"""
Aapp/app/increment_pdf.py
============================
Print/record PDF for a single Increment, per pt_upgrades.md:
"saprate schedule for print and record" (for the Increment module).
"""

from datetime import date

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer

from Aapp.app.pdf_engine import build_pdf, doc_styles, INR, kv_table, section_divider

MONTH_NAMES = {
    1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June',
    7: 'July', 8: 'August', 9: 'September', 10: 'October', 11: 'November', 12: 'December',
}


def increment_schedule_pdf(increment):
    styles = doc_styles()
    story = [
        Paragraph(f"Increment Order — #{increment.increment_id}", styles['Heading1']),
        Spacer(1, 3 * mm),
    ]

    rows = [
        ("Employee", increment.employee.name),
        ("Employee Code", increment.employee.employeecode),
        ("Effective From", f"{MONTH_NAMES[increment.effective_from_month]} {increment.effective_from_year}"),
        ("Old Basic Pay", INR(increment.old_basicpay)),
        ("New Basic Pay", INR(increment.new_basicpay)),
        ("Increase", f"{INR(increment.basic_increase)} ({increment.increase_percent}%)"),
        ("Old HRA", INR(increment.old_hra)),
        ("New HRA", INR(increment.new_hra)),
        ("Reason", increment.reason or '-'),
        ("Status", increment.get_status_display()),
    ]
    story.append(kv_table(rows))
    story.append(Spacer(1, 5 * mm))
    story.append(section_divider())
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "This increment applies to all salary processing from the effective month onward. "
        "If this increment is backdated, corresponding Arrear records should be generated "
        "separately via the Arrear module.",
        styles['Small']
    ))

    doc_meta = {
        'title': f"Increment Order #{increment.increment_id} - {increment.employee.name}",
        'doc_number': f"INC/{increment.increment_id}",
        'doc_date': date.today().strftime('%d-%m-%Y'),
    }
    return build_pdf(story, company=increment.company, doc_meta=doc_meta)
