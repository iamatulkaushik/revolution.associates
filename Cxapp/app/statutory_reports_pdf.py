"""
Cxapp/app/statutory_reports_pdf.py
====================================
Grand Total of Salary/Wages and Salary/Wages Register PDFs for the
Cxapp (self-signup) portal. Sourced from CxSalary + CxSalaryLine
component rows — mirrors Aapp.app.statutory_reports_pdf but reads
the line-item model instead of fixed columns.
"""

import calendar
from datetime import date
from decimal import Decimal

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from Aapp.app.pdf_engine import (
    build_pdf, doc_styles, INR, amount_in_words,
    table_style, total_row_style, NAVY, STEEL, LIGHT,
)

PF_LABEL = 'EPF (Statutory)'
ESI_LABEL = 'ESI (Statutory)'
LWF_LABEL = 'LABOUR (Statutory)'


def _month_name(month):
    return calendar.month_name[int(month)]


def _line_amount(salary, name, ltype):
    line = salary.lines.filter(component_type=ltype, component_name=name).first()
    return line.resolved_amount if line else Decimal('0')


def cx_grand_total_pdf(company, salaries, month, year):
    """Company-level Grand Total summary for Cxapp salaries."""
    s = doc_styles()
    mname = _month_name(month)
    story = [
        Paragraph('GRAND TOTAL OF SALARY / WAGES', s['Title']),
        Paragraph(f'For the month of {mname}, {year}', s['Subtitle']),
        Spacer(1, 5 * mm),
    ]

    total_earning = sum((sal.total_allowances or Decimal('0')) for sal in salaries)
    total_deduction = sum((sal.total_deductions or Decimal('0')) for sal in salaries)
    net_payment = sum((sal.total_amount or Decimal('0')) for sal in salaries)

    pf_total = sum(_line_amount(sal, PF_LABEL, 'deduction') for sal in salaries)
    esi_total = sum(_line_amount(sal, ESI_LABEL, 'deduction') for sal in salaries)
    lwf_total = sum(_line_amount(sal, LWF_LABEL, 'deduction') for sal in salaries)

    summary_data = [
        ['Total Employees', str(len(salaries))],
        ['Total Earning', INR(total_earning)],
        ['Total Deduction', INR(total_deduction)],
        ['E.P.F.', INR(pf_total)],
        ['E.S.I.C.', INR(esi_total)],
        ['Labour Welfare Fund', INR(lwf_total)],
        ['Net Payment', INR(net_payment)],
    ]
    story.append(Table(
        [[Paragraph(f'<b>{k}</b>', s['Label']), Paragraph(v, s['Value'])] for k, v in summary_data],
        colWidths=[220, 180],
        style=TableStyle([
            ('LINEBELOW', (0, 0), (-1, -1), 0.3, LIGHT),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]),
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f'<b>Net Payment in Words:</b> {amount_in_words(net_payment)}', s['Small']))

    doc_meta = {'title': f'Grand Total — {mname} {year}', 'doc_date': date.today()}
    return build_pdf(story, company=company.company, doc_meta=doc_meta, **company.company.pdf_letterhead_kwargs())


def cx_wages_register_pdf(company, salaries, month, year):
    """Per-employee Salary/Wages Register PDF for Cxapp salaries."""
    s = doc_styles()
    mname = _month_name(month)
    story = [
        Paragraph('SALARY / WAGES REGISTER', s['Title']),
        Paragraph(f'For the month of {mname}, {year}', s['Subtitle']),
        Spacer(1, 4 * mm),
    ]

    header = ['#', 'Emp Code', 'Name', 'Designation', 'Gross', 'PF', 'ESI', 'Deductions', 'Net Pay']
    data = [[Paragraph(h, s['TableHeader']) for h in header]]

    t_gross = t_pf = t_esi = t_ded = t_net = Decimal('0')
    for i, sal in enumerate(salaries, 1):
        pf = _line_amount(sal, PF_LABEL, 'deduction')
        esi = _line_amount(sal, ESI_LABEL, 'deduction')
        data.append([
            str(i), sal.employee_code, sal.employee_name,
            sal.designation.designation_name if sal.designation else '—',
            INR(sal.total_allowances), INR(pf), INR(esi),
            INR(sal.total_deductions), INR(sal.total_amount),
        ])
        t_gross += sal.total_allowances or Decimal('0')
        t_pf += pf
        t_esi += esi
        t_ded += sal.total_deductions or Decimal('0')
        t_net += sal.total_amount or Decimal('0')

    data.append(['', '', '', 'TOTAL', INR(t_gross), INR(t_pf), INR(t_esi), INR(t_ded), INR(t_net)])

    col_w = [20, 60, 100, 90, 60, 50, 50, 65, 65]
    tbl = Table(data, colWidths=col_w, repeatRows=1)
    ts = table_style()
    ts.add('ALIGN', (4, 1), (-1, -1), 'RIGHT')
    ts.add('FONTSIZE', (0, 0), (-1, -1), 7)
    for cmd in total_row_style():
        ts.add(*cmd)
    tbl.setStyle(ts)
    story.append(tbl)

    doc_meta = {'title': f'Wages Register — {mname} {year}', 'doc_date': date.today()}
    return build_pdf(story, company=company.company, doc_meta=doc_meta,
                      margins={'top': 30, 'bottom': 20, 'left': 8, 'right': 8},
                      **company.company.pdf_letterhead_kwargs())
