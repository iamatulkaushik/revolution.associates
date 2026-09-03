"""
Aapp/app/arrear_pdf.py
=========================
Print/record PDF for a single Arrear, per pt_upgrades.md: "saprate
schedule for print and record" — includes the statutory recompute
(PF/labour/PT/IT) as its own clearly separated section, per: "if
deductions in arrear, compliances of epf, labour, i.tax etc saprate
schedule".
"""

from datetime import date

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer

from Aapp.app.pdf_engine import build_pdf, doc_styles, INR, kv_table, section_divider

MONTH_NAMES = {
    1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June',
    7: 'July', 8: 'August', 9: 'September', 10: 'October', 11: 'November', 12: 'December',
}


def arrear_schedule_pdf(arrear):
    styles = doc_styles()
    story = [
        Paragraph(f"Arrear Statement — #{arrear.arrear_id}", styles['Heading1']),
        Spacer(1, 3 * mm),
    ]

    header_rows = [
        ("Employee", arrear.employee.name),
        ("Employee Code", arrear.employee.employeecode),
        ("Arrear Period", f"{MONTH_NAMES[arrear.arrear_month]} {arrear.arrear_year}"),
        ("Payout Month", f"{MONTH_NAMES[arrear.payout_month]} {arrear.payout_year}"),
        ("Old Basic Paid", INR(arrear.old_basic_paid)),
        ("Revised Basic", INR(arrear.revised_basic)),
        ("Old HRA Paid", INR(arrear.old_hra_paid)),
        ("Revised HRA", INR(arrear.revised_hra)),
        ("Gross Shortfall", INR(arrear.gross_shortfall)),
    ]
    story.append(kv_table(header_rows))
    story.append(Spacer(1, 5 * mm))
    story.append(section_divider())
    story.append(Spacer(1, 3 * mm))

    # Separate statutory recompute section — kept visually and
    # structurally apart from the salary shortfall section above.
    story.append(Paragraph("Statutory Deduction Recompute on Shortfall", styles['Heading2']))
    recompute_rows = [
        ("PF Recompute", INR(arrear.pf_recompute)),
        ("Labour Welfare Recompute", INR(arrear.labour_recompute)),
        ("Professional Tax Recompute", INR(arrear.pt_recompute)),
        ("Income Tax Recompute", INR(arrear.income_tax_recompute)),
        ("Net Arrear Payable", INR(arrear.net_arrear_payable)),
    ]
    story.append(kv_table(recompute_rows))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f"Status: {'Paid' if arrear.is_paid else 'Pending Payout'}",
        styles['Small']
    ))

    doc_meta = {
        'title': f"Arrear #{arrear.arrear_id} - {arrear.employee.name}",
        'doc_number': f"ARR/{arrear.arrear_id}",
        'doc_date': date.today().strftime('%d-%m-%Y'),
    }
    return build_pdf(story, company=arrear.company, doc_meta=doc_meta)
