"""
Aapp/app/pt_schedule.py
=========================
Professional Tax schedule — print/record document listing PT deducted
per employee for a month, grouped by state (per pt_upgrades.md:
"generate schedule for print and record").

Distinct from form16.deductions_report_pdf (income tax only) — this is
PT-specific and grouped by state since a company's workforce can span
multiple PT-levying states simultaneously.
"""

from datetime import date

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table

from Aapp.app.pdf_engine import (
    build_pdf, doc_styles, INR, table_style, total_row_style, section_divider,
)


def pt_schedule_pdf(company, month, year):
    """
    Returns bytes: PT schedule for the given company/month, grouped by
    employee state, each with a subtotal, plus a grand total line.
    """
    from Aapp.app.salary_processing import salary_slip

    slips = (salary_slip.objects
             .filter(company_id=company, processing_id__month=month, processing_id__year=year)
             .exclude(professional_tax=0)
             .select_related('employee_id', 'employee_id__perm_state', 'employee_id__temp_state')
             .order_by('employee_id__employeecode'))

    by_state = {}
    for s in slips:
        emp = s.employee_id
        state_obj = emp.perm_state or emp.temp_state
        state_name = state_obj.name.title() if state_obj else 'Unknown'
        by_state.setdefault(state_name, []).append(s)

    styles = doc_styles()
    story = [
        Paragraph(f"Professional Tax Schedule — {month}/{year}", styles['Heading1']),
        Spacer(1, 4 * mm),
    ]

    grand_total = 0
    for state_name in sorted(by_state.keys()):
        story.append(Paragraph(state_name, styles['Heading2']))
        data = [["Emp Code", "Name", "Gross", "PT Deducted"]]
        state_total = 0
        for s in by_state[state_name]:
            data.append([
                s.employee_id.employeecode,
                s.employee_id.name,
                INR(s.gross_earnings),
                INR(s.professional_tax),
            ])
            state_total += s.professional_tax
        data.append(["", "", f"{state_name} Subtotal", INR(state_total)])
        grand_total += state_total

        tbl = Table(data, colWidths=[80, 160, 100, 100])
        tbl.setStyle(table_style())
        tbl.setStyle(total_row_style())
        story.append(tbl)
        story.append(Spacer(1, 5 * mm))

    story.append(section_divider())
    story.append(Paragraph(f"<b>Grand Total PT Deducted: {INR(grand_total)}</b>", styles['Heading2']))

    doc_meta = {
        'title': f"PT Schedule {month}/{year}",
        'doc_date': date.today().strftime('%d-%m-%Y'),
    }
    return build_pdf(story, company=company, doc_meta=doc_meta)
