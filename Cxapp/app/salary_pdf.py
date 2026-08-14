"""
Cxapp/app/salary_pdf.py
========================
Individual salary slip PDF for the Cxapp (self-signup Company Owner)
portal. Reuses Aapp.app.pdf_engine's letterhead system directly
(shared, not reimplemented) — same pattern Aapp.app.salary_pdf uses.

Access:
    Owner + HR — Cxapp/app/process.py::cxapp_salary_slip_pdf
    Employee (own slip only) — Cxapp/app/employee_portal.py::emp_salary_slip_pdf

Usage:
    from Cxapp.app.salary_pdf import cx_salary_slip_pdf
    pdf_bytes = cx_salary_slip_pdf(salary)
"""

from datetime import date
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from reportlab.lib.colors import HexColor

from Aapp.app.pdf_engine import (
    build_pdf, doc_styles, INR, amount_in_words,
    table_style, NAVY, STEEL, TEAL, CREAM, LIGHT, WHITE, MUTED,
)

PAGE_W, _ = A4
LM, RM = 18 * mm, 18 * mm
AVAIL = PAGE_W - LM - RM


def cx_salary_slip_pdf(salary):
    """
    Args:
        salary: Cxapp.app.process.CxSalary instance (with .lines prefetched
                or not — fetched here if needed)

    Returns: bytes (PDF)
    """
    employee = salary.employee
    company = salary.company.company
    s = doc_styles()
    month_name = salary.get_salary_month_display()

    kyc = getattr(employee, 'kyc', None)
    pan = getattr(kyc, 'pan_number', '') or '—'
    bank = getattr(getattr(employee, 'banking', None), 'account_number', '') or '—'

    story = [
        Paragraph('SALARY SLIP', s['Title']),
        Paragraph(f'{month_name} {salary.salary_year}', s['Subtitle']),
        Spacer(1, 4 * mm),
    ]

    emp_info = [
        [('Employee Name', salary.employee_name.title()), ('Employee Code', salary.employee_code)],
        [('Designation', salary.designation.designation_name), ('Date of Joining', str(salary.date_of_joining.strftime('%d-%b-%Y') or '—'))],
        [('PAN', pan), ('UAN', salary.uan or '—')],
        [('ESI No.', salary.esi or '—'), ('Bank Account', bank)],
    ]
    flat_pairs = []
    for row in emp_info:
        flat_pairs.extend(row)

    col_w = [AVAIL * 0.22, AVAIL * 0.28, AVAIL * 0.22, AVAIL * 0.28]
    info_data = []
    it = iter(flat_pairs)
    for (lk, lv), (rk, rv) in zip(it, it):
        info_data.append([
            Paragraph(f'<b>{lk}</b>', s['Label']),
            Paragraph(str(lv), s['Value']),
            Paragraph(f'<b>{rk}</b>', s['Label']),
            Paragraph(str(rv), s['Value']),
        ])

    info_ts = TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.3, LIGHT),
        ('BACKGROUND', (0, 0), (-1, -1), CREAM),
    ])
    story.append(Table(info_data, colWidths=col_w, style=info_ts))
    story.append(Spacer(1, 5 * mm))

    half = AVAIL / 2 - 3 * mm
    allowance_lines = salary.lines.filter(component_type='allowance')
    deduction_lines = salary.lines.filter(component_type='deduction')

    earn_data = [[Paragraph('EARNINGS', s['TableHeader']), Paragraph('AMOUNT (₹)', s['TableHeader'])]]
    for line in allowance_lines:
        earn_data.append([line.component_name, INR(line.resolved_amount)])
    earn_ts = table_style(header_bg=STEEL)
    earn_ts.add('ALIGN', (1, 1), (1, -1), 'RIGHT')
    earn_tbl = Table(earn_data, colWidths=[half * 0.6, half * 0.4], style=earn_ts)

    ded_data = [[Paragraph('DEDUCTIONS', s['TableHeader']), Paragraph('AMOUNT (₹)', s['TableHeader'])]]
    for line in deduction_lines:
        ded_data.append([line.component_name, INR(line.resolved_amount)])
    if not deduction_lines:
        ded_data.append(['—', INR(0)])
    ded_ts = table_style(header_bg=NAVY)
    ded_ts.add('ALIGN', (1, 1), (1, -1), 'RIGHT')
    ded_tbl = Table(ded_data, colWidths=[half * 0.6, half * 0.4], style=ded_ts)

    combined = Table(
        [[earn_tbl, Spacer(6 * mm, 1), ded_tbl]],
        colWidths=[half, 6 * mm, half],
        style=TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]),
    )
    story.append(combined)
    story.append(Spacer(1, 5 * mm))

    net_data = [[
        Paragraph('<b>Gross Wages</b>', s['TableHeader']),
        Paragraph(INR(salary.total_allowances), s['TableHeader']),
        Paragraph('<b>Total Deductions</b>', s['TableHeader']),
        Paragraph(INR(salary.total_deductions), s['TableHeader']),
        Paragraph('<b>Net Wages</b>', s['TableHeader']),
        Paragraph(INR(salary.total_amount), s['TableHeader']),
    ]]
    net_ts = TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, -1), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LINEAFTER', (0, 0), (-2, -1), 0.5, TEAL),
    ])
    cw = [AVAIL / 6] * 6
    story.append(Table(net_data, colWidths=cw, style=net_ts))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(
        f'<b>Net Amount in Words:</b> {amount_in_words(salary.total_amount)}', s['Small'],
    ))
    story.append(Spacer(1, 8 * mm))

    sig_ts = TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('LINEABOVE', (0, 0), (0, 0), 0.5, MUTED),
        ('LINEABOVE', (-1, 0), (-1, 0), 0.5, MUTED),
    ])
    sig_data = [[
        Paragraph("Employee's Signature", s['Small']), '',
        Paragraph("Authorised Signatory", s['Small']),
    ]]
    story.append(Table(sig_data, colWidths=[AVAIL * 0.35, AVAIL * 0.3, AVAIL * 0.35], style=sig_ts))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        'This is a computer-generated document. No signature is required if sent digitally.', s['Small'],
    ))

    doc_meta = {
        'title': f'Salary Slip — {month_name} {salary.salary_year}',
        'doc_date': date.today(),
        'ref': f'EMP/{salary.employee_code}/{salary.salary_month}/{salary.salary_year}',
    }
    return build_pdf(story, company=company, doc_meta=doc_meta, **company.pdf_letterhead_kwargs())
