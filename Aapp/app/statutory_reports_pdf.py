"""
Aapp/app/statutory_reports_pdf.py
==================================
PDF variants of legacy Saral-style monthly reports:
  - Grand Total of Salary/Wages (company-level summary)
  - Salary/Wages Register (per-employee earnings/deductions ledger)
  - Wages Slip (contractor-style single-employee wage slip)

All figures sourced from Aapp.app.salary_processing.salary_slip — no
new calculation, pure presentation via the shared pdf_engine.
"""

import calendar
from datetime import date
from decimal import Decimal

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from Aapp.app.pdf_engine import (
    build_pdf, doc_styles, INR, amount_in_words,
    table_style, total_row_style, NAVY, STEEL, LIGHT, WHITE, CREAM,
)


def _month_name(month):
    return calendar.month_name[int(month)]


def _sum(slips, field):
    return sum((getattr(s, field) or Decimal('0')) for s in slips)


# =====================================================================
# 1. GRAND TOTAL OF SALARY / WAGES
# =====================================================================

def grand_total_pdf(company, slips, month, year):
    """
    Company-level single-page summary — total earnings, total deductions,
    PF/ESI/LWF breakup, net payment, days summary.
    """
    s = doc_styles()
    mname = _month_name(month)
    story = [
        Paragraph('GRAND TOTAL OF SALARY / WAGES', s['Title']),
        Paragraph(f'For the month of {mname}, {year}', s['Subtitle']),
        Spacer(1, 5 * mm),
    ]

    earning_fields = [
        ('Basic', 'basic_earned'), ('DA', 'da_earned'), ('HRA', 'hra_earned'),
        ('Conveyance', 'conveyance_earned'), ('Medical', 'medical_allowance_earned'),
        ('Special Allowance', 'special_allowance_earned'), ('CCA', 'cca_earned'),
        ('Lunch Allowance', 'lunch_allowance_earned'), ('Washing Allowance', 'washing_allowance_earned'),
        ('Cycle Allowance', 'cycle_allowance_earned'), ('Other Allowance', 'other_allowance_earned'),
        ('OT Amount', 'overtime_amount'), ('Bonus', 'bonus_amount'),
    ]
    earn_data = [[Paragraph('Earning Head', s['TableHeader']), Paragraph('Amount (₹)', s['TableHeader'])]]
    total_earning = Decimal('0')
    for label, field in earning_fields:
        amt = _sum(slips, field)
        if amt:
            earn_data.append([label, INR(amt)])
        total_earning += amt
    earn_data.append(['Total Earning', INR(total_earning)])
    earn_tbl = Table(earn_data, colWidths=[260, 140])
    ts = table_style(header_bg=STEEL)
    ts.add('ALIGN', (1, 1), (1, -1), 'RIGHT')
    ts.add('FONTNAME', (0, -1), (-1, -1), 'Ubuntu')
    for cmd in total_row_style():
        ts.add(*cmd)
    earn_tbl.setStyle(ts)
    story += [earn_tbl, Spacer(1, 6 * mm)]

    ded_fields = [
        ('E.P.F.', 'pf_deduction'), ('E.S.I.C.', 'esi_deduction'),
        ('Labour Welfare Fund', 'labour_welfare_deduction'),
        ('Professional Tax', 'professional_tax'), ('Income Tax', 'income_tax'),
        ('Loan Deduction', 'loan_deduction'), ('Advance', 'advance_deduction'),
        ('Late Fine', 'late_fine'), ('Other Deduction', 'other_deduction'),
    ]
    ded_data = [[Paragraph('Deduction Head', s['TableHeader']), Paragraph('Amount (₹)', s['TableHeader'])]]
    total_deduction = Decimal('0')
    for label, field in ded_fields:
        amt = _sum(slips, field)
        if amt:
            ded_data.append([label, INR(amt)])
        total_deduction += amt
    ded_data.append(['Total Deduction', INR(total_deduction)])
    ded_tbl = Table(ded_data, colWidths=[260, 140])
    ts2 = table_style(header_bg=NAVY)
    ts2.add('ALIGN', (1, 1), (1, -1), 'RIGHT')
    for cmd in total_row_style():
        ts2.add(*cmd)
    ded_tbl.setStyle(ts2)
    story += [ded_tbl, Spacer(1, 6 * mm)]

    net_payment = total_earning - total_deduction
    pf_employer = _sum(slips, 'pf_employer_contribution')
    esi_employer = _sum(slips, 'esi_employer_contribution')

    summary_data = [
        ['Total Employees', str(len(slips))],
        ['Total Earning', INR(total_earning)],
        ['Total Deduction', INR(total_deduction)],
        ['Net Payment', INR(net_payment)],
        ['P.F. Employer Share', INR(pf_employer)],
        ['E.S.I.C. Employer Share', INR(esi_employer)],
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
    return build_pdf(story, company=company, doc_meta=doc_meta, **_letterhead_kwargs(company))


# =====================================================================
# 2. SALARY / WAGES REGISTER
# =====================================================================

def wages_register_pdf(company, slips, month, year):
    """Per-employee row ledger — one row per employee, all earning/deduction columns."""
    s = doc_styles()
    mname = _month_name(month)
    story = [
        Paragraph('SALARY / WAGES REGISTER', s['Title']),
        Paragraph(f'For the month of {mname}, {year}', s['Subtitle']),
        Spacer(1, 4 * mm),
    ]

    header = ['#', 'Emp Code', 'Name', 'Designation', 'Basic', 'DA', 'HRA',
              'Gross', 'PF', 'ESI', 'PT', 'Other Ded.', 'Net Pay']
    data = [[Paragraph(h, s['TableHeader']) for h in header]]

    totals = {k: Decimal('0') for k in ['basic_earned', 'da_earned', 'hra_earned',
              'gross_earnings', 'pf_deduction', 'esi_deduction',
              'professional_tax', 'total_deductions', 'net_pay']}

    for i, sl in enumerate(slips, 1):
        emp = sl.employee_id
        other_ded = (sl.total_deductions - sl.pf_deduction - sl.esi_deduction - sl.professional_tax)
        row = [
            str(i),
            emp.employeecode,
            emp.name,
            sl.designation_id.designation_name if sl.designation_id else '—',
            INR(sl.basic_earned), INR(sl.da_earned), INR(sl.hra_earned),
            INR(sl.gross_earnings), INR(sl.pf_deduction), INR(sl.esi_deduction),
            INR(sl.professional_tax), INR(other_ded), INR(sl.net_pay),
        ]
        data.append(row)
        for k in totals:
            totals[k] += getattr(sl, k)

    other_ded_total = totals['total_deductions'] - totals['pf_deduction'] - totals['esi_deduction'] - totals['professional_tax']
    data.append([
        '', '', '', 'TOTAL',
        INR(totals['basic_earned']), INR(totals['da_earned']), INR(totals['hra_earned']),
        INR(totals['gross_earnings']), INR(totals['pf_deduction']), INR(totals['esi_deduction']),
        INR(totals['professional_tax']), INR(other_ded_total), INR(totals['net_pay']),
    ])

    col_w = [20, 55, 90, 75, 50, 45, 45, 55, 45, 40, 40, 55, 55]
    tbl = Table(data, colWidths=col_w, repeatRows=1)
    ts = table_style()
    ts.add('ALIGN', (4, 1), (-1, -1), 'RIGHT')
    ts.add('FONTSIZE', (0, 0), (-1, -1), 7)
    for cmd in total_row_style():
        ts.add(*cmd)
    tbl.setStyle(ts)
    story.append(tbl)

    doc_meta = {'title': f'Wages Register — {mname} {year}', 'doc_date': date.today()}
    return build_pdf(story, company=company, doc_meta=doc_meta, margins={'top': 30, 'bottom': 20, 'left': 8, 'right': 8},
                      **_letterhead_kwargs(company))


# =====================================================================
# 3. WAGES SLIP (contractor-style single-employee slip)
# =====================================================================

def wages_slip_pdf(company, slip):
    """Single-employee wage slip — Payment of Wages Act format."""
    s = doc_styles()
    emp = slip.employee_id
    mname = _month_name(slip.processing_id.month)
    year = slip.processing_id.year

    story = [
        Paragraph('WAGES SLIP', s['Title']),
        Paragraph(f'Wages Period: {mname}, {year}', s['Subtitle']),
        Spacer(1, 5 * mm),
    ]

    info_pairs = [
        ('Employee Name', emp.name),
        ('Employee Code', emp.employeecode),
        ('Designation', slip.designation_id.designation_name if slip.designation_id else '—'),
        ('UAN', getattr(emp, 'uan_number', '') or '—'),
        ('ESIC No.', getattr(emp, 'esic_number', '') or '—'),
        ('Paid Days', str(slip.paid_days)),
    ]
    info_data = [[Paragraph(f'<b>{k}</b>', s['Label']), Paragraph(str(v), s['Value'])] for k, v in info_pairs]
    story.append(Table(info_data, colWidths=[180, 220], style=TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 0.3, LIGHT),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ])))
    story.append(Spacer(1, 5 * mm))

    ded_total = slip.total_deductions
    net = slip.net_pay

    summary = [
        ['Wages Payable', INR(slip.gross_earnings)],
        ['E.P.F.', INR(slip.pf_deduction)],
        ['E.S.I.C.', INR(slip.esi_deduction)],
        ['Advance', INR(slip.advance_deduction)],
        ['LWF', INR(slip.labour_welfare_deduction)],
        ['Total Deductions', INR(ded_total)],
        ['Net Wages Paid', INR(net)],
    ]
    tbl = Table(
        [[Paragraph(f'<b>{k}</b>', s['Label']), Paragraph(v, s['Value'])] for k, v in summary],
        colWidths=[220, 180],
        style=TableStyle([('LINEBELOW', (0, 0), (-1, -1), 0.3, LIGHT),
                          ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]),
    )
    story += [tbl, Spacer(1, 4 * mm)]
    story.append(Paragraph(f'<b>Net Wages in Words:</b> {amount_in_words(net)}', s['Small']))
    story.append(Spacer(1, 10 * mm))

    sig_data = [["Employee's Signature", '', "Employer's Signature"]]
    story.append(Table(sig_data, colWidths=[150, 100, 150], style=TableStyle([
        ('LINEABOVE', (0, 0), (0, 0), 0.5, NAVY),
        ('LINEABOVE', (-1, 0), (-1, 0), 0.5, NAVY),
        ('FONTNAME', (0, 0), (-1, -1), 'Ubuntu'), ('FONTSIZE', (0, 0), (-1, -1), 8),
    ])))

    doc_meta = {
        'title': f'Wages Slip — {emp.employeecode} — {mname} {year}',
        'doc_date': date.today(),
    }
    return build_pdf(story, company=company, doc_meta=doc_meta, **_letterhead_kwargs(company))


def _letterhead_kwargs(company):
    """Use company's configured letterhead mode if available, else default."""
    fn = getattr(company, 'pdf_letterhead_kwargs', None)
    return fn() if callable(fn) else {}
