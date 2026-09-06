"""
salary_pdf.py
=============
PDF generators for Revolution Associates HRMS.

All functions return bytes — pass directly to HttpResponse or email attachment.

Functions:
  salary_slip_pdf(salary_slip_obj)          → individual pay slip
  salary_sheet_pdf(company, month, year)    → full monthly payroll register
  salary_abstract_pdf(company, month, year) → department-wise summary / abstract
  letterhead_pdf(company, content_items, doc_meta)   → generic letterhead doc
  company_profile_pdf(company)              → company profile document

Drop-in usage in any view:
  from Aapp.app.salary_pdf import salary_slip_pdf
  pdf_bytes = salary_slip_pdf(salary_slip_obj)
  return HttpResponse(pdf_bytes, content_type='application/pdf',
                      headers={'Content-Disposition': 'attachment; filename="slip.pdf"'})

NOTE: Previously sourced from the now-deleted wages_record model — all
functions here read from Aapp.app.salary_processing.salary_slip instead,
the single payroll source of truth.
"""

from datetime import date
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable,
)
from reportlab.lib.colors import HexColor

from Aapp.app.pdf_engine import (
    build_pdf, doc_styles, INR, amount_in_words,
    table_style, total_row_style, section_divider, kv_table,
    NAVY, STEEL, TEAL, CORAL, CREAM, LIGHT, WHITE, MUTED,
)

PAGE_W, _ = A4
LM, RM = 18 * mm, 18 * mm
AVAIL = PAGE_W - LM - RM


# ── helpers ───────────────────────────────────────────────────────────────────

def _wages_qs(company, month, year):
    """
    Now sourced from salary_processing.salary_slip (wages_record was
    deleted — Wages Register is a read-only view over payroll data).
    """
    from Aapp.app.salary_processing import salary_slip
    return (salary_slip.objects
            .filter(company_id=company, processing_id__month=month, processing_id__year=year)
            .select_related('employee_id', 'processing_id')
            .order_by('employee_id__employeecode'))


MONTH_NAMES = {
    1:'January', 2:'February', 3:'March', 4:'April', 5:'May', 6:'June',
    7:'July', 8:'August', 9:'September', 10:'October', 11:'November', 12:'December',
}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. INDIVIDUAL SALARY SLIP
# ═══════════════════════════════════════════════════════════════════════════════

def salary_slip_pdf(salary_slip_obj):
    """
    Generate a single employee salary slip with company letterhead.

    Args:
        salary_slip_obj: Aapp.app.salary_processing.salary_slip instance

    Returns: bytes (PDF)

    Usage:
        from Aapp.app.salary_pdf import salary_slip_pdf
        pdf = salary_slip_pdf(rec)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="slip_{rec.employee_id.employeecode}.pdf"'
        return response
    """
    r   = salary_slip_obj
    emp = r.employee_id
    co  = r.company_id
    month = r.processing_id.month
    year = r.processing_id.year
    s   = doc_styles()
    month_name = MONTH_NAMES.get(month, str(month))

    # other_earnings / other_deductions are aggregates on salary_slip —
    # wages_record had single fields for these, salary_slip breaks them
    # into individual allowance/deduction line items. Sum them back into
    # the same two summary lines this PDF has always shown, so the layout
    # (and every downstream consumer expecting these two numbers) is
    # unchanged.
    other_earnings = (
        r.conveyance_earned + r.medical_allowance_earned + r.lunch_allowance_earned +
        r.cca_earned + r.special_allowance_earned + r.travel_allowance_earned +
        r.washing_allowance_earned + r.cycle_allowance_earned + r.other_allowance_earned +
        r.bonus_amount
    )
    other_deductions = r.loan_deduction + r.advance_deduction + r.late_fine + r.other_deduction

    story = []

    # ── Employee info header ──────────────────────────────────────────────────
    story.append(Paragraph('SALARY SLIP', s['Title']))
    story.append(Paragraph(f'{month_name} {year}', s['Subtitle']))
    story.append(Spacer(1, 4 * mm))

    emp_info = [
        [('Employee Name', emp.name),
         ('Employee Code', emp.employeecode)],
        [('Designation', emp.designationID.designationname),
         ('Department', emp.departmentID.department_name)],
        [('Date of Joining', emp.dateofjoining.strftime('%d/%m/%Y') if emp.dateofjoining else '—'),
         ('Bank Account', getattr(emp, 'bank_account', '—') or '—')],
        [('PAN', getattr(emp, 'pan_number', '—') or '—'),
         ('UAN', getattr(emp, 'uan_number', '—') or '—')],
        [('ESIC No.', getattr(emp, 'esic_number', '—') or '—'),
         ('EPF No.', getattr(emp, 'epf_memberID', '—') or '—')],
    ]

    # Flatten to two-column wide kv_table
    flat_pairs = []
    for row in emp_info:
        flat_pairs.extend(row)

    # Build as 4-column table: label | value | label | value
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
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ('LINEBELOW',     (0, 0), (-1, -1), 0.3, LIGHT),
        ('BACKGROUND',    (0, 0), (-1, -1), CREAM),
    ])
    story.append(Table(info_data, colWidths=col_w, style=info_ts))
    story.append(Spacer(1, 5 * mm))

    # ── Earnings vs Deductions ────────────────────────────────────────────────
    half = AVAIL / 2 - 3 * mm

    # Earnings table
    earn_data = [
        [Paragraph('EARNINGS', s['TableHeader']),
         Paragraph('AMOUNT (₹)', s['TableHeader'])],
        ['Basic Wages',        INR(r.basic_earned)],
        ['Dearness Allowance', INR(r.da_earned)],
        ['HRA',                INR(r.hra_earned)],
        ['Overtime Wages',     INR(r.overtime_amount)],
        ['Other Earnings',     INR(other_earnings)],
    ]
    earn_ts = table_style(header_bg=STEEL)
    earn_ts.add('ALIGN', (1, 1), (1, -1), 'RIGHT')
    earn_ts.add('FONTNAME', (-1, -1), (-1, -1), 'Ubuntu')
    earn_tbl = Table(earn_data, colWidths=[half * 0.6, half * 0.4], style=earn_ts)

    # Deductions table
    ded_data = [
        [Paragraph('DEDUCTIONS', s['TableHeader']),
         Paragraph('AMOUNT (₹)', s['TableHeader'])],
        ['EPF',               INR(r.pf_deduction)],
        ['ESI',               INR(r.esi_deduction)],
        ['Professional Tax',  INR(r.professional_tax)],
        ['Income Tax',        INR(r.income_tax)],
        ['Labour Welfare',    INR(r.labour_welfare_deduction)],
        ['Other Deductions',  INR(other_deductions)],
    ]
    ded_ts = table_style(header_bg=NAVY)
    ded_ts.add('ALIGN', (1, 1), (1, -1), 'RIGHT')
    ded_tbl = Table(ded_data, colWidths=[half * 0.6, half * 0.4], style=ded_ts)

    # Side-by-side
    combined = Table(
        [[earn_tbl, Spacer(6 * mm, 1), ded_tbl]],
        colWidths=[half, 6 * mm, half],
        style=TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]),
    )
    story.append(combined)
    story.append(Spacer(1, 5 * mm))

    # ── Net Wages summary bar ─────────────────────────────────────────────────
    net_data = [
        [Paragraph('<b>GROSS WAGES</b>', s['TableHeader']),
         Paragraph(INR(r.gross_earnings), s['TableHeader']),
         Paragraph('<b>TOTAL DEDUCTIONS</b>', s['TableHeader']),
         Paragraph(INR(r.total_deductions), s['TableHeader']),
         Paragraph('<b>NET WAGES</b>', s['TableHeader']),
         Paragraph(INR(r.net_pay), s['TableHeader'])],
    ]
    net_ts = TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), NAVY),
        ('TEXTCOLOR',     (0, 0), (-1, -1), WHITE),
        ('FONTNAME',      (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 10),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LINEAFTER',     (0, 0), (-2, -1), 0.5, TEAL),
    ])
    cw = [AVAIL / 6] * 6
    story.append(Table(net_data, colWidths=cw, style=net_ts))
    story.append(Spacer(1, 3 * mm))

    # Amount in words
    story.append(Paragraph(
        f'<b>Net Amount in Words:</b> {amount_in_words(r.net_pay)}',
        s['Small'],
    ))
    story.append(Spacer(1, 20 * mm))

    # ── Signature row ─────────────────────────────────────────────────────────
    sig_ts = TableStyle([
        ('ALIGN',   (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',  (0, 0), (-1, -1), 'BOTTOM'),
        ('FONTNAME',(0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE',(0, 0), (-1, -1), 8),
        ('LINEABOVE', (0, 0), (0, 0), 0.5, MUTED),
        ('LINEABOVE', (-1, 0), (-1, 0), 0.5, MUTED),
    ])
    sig_data = [[
        Paragraph("Employee's Signature", s['Small']),
        '',
        Paragraph("Authorised Signatory", s['Small']),
    ]]
    story.append(Table(sig_data, colWidths=[AVAIL * 0.35, AVAIL * 0.3, AVAIL * 0.35], style=sig_ts))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        'This is a computer-generated document. No signature is required if sent digitally.',
        s['Small'],
    ))

    doc_meta = {
        'title': f'Salary Slip — {month_name} {year}',
        'doc_date': date.today(),
        'ref': f'EMP/{emp.employeecode}/{month}/{year}',
        'hide_pan': True,
        'hide_generated_by': True,
    }
    return build_pdf(story, company=co, doc_meta=doc_meta, **co.pdf_letterhead_kwargs())


# ═══════════════════════════════════════════════════════════════════════════════
# 2. MONTHLY SALARY SHEET (all employees)
# ═══════════════════════════════════════════════════════════════════════════════

def salary_sheet_pdf(company, month, year):
    """
    Full monthly salary register — all employees, all columns.
    Statutory form — maps to Factories Act Form 17 / MW Act Form III.

    Args:
        company : Company model instance
        month   : int 1-12
        year    : int

    Returns: bytes (PDF)

    Usage:
        pdf = salary_sheet_pdf(company, month=6, year=2026)
        return HttpResponse(pdf, content_type='application/pdf',
                            headers={'Content-Disposition': 'attachment; filename="salary_sheet.pdf"'})
    """
    qs = _wages_qs(company, month, year)
    s  = doc_styles()
    month_name = MONTH_NAMES.get(month, str(month))

    story = []
    story.append(Paragraph('SALARY REGISTER', s['Title']))
    story.append(Paragraph(
        f'{month_name} {year}  ·  {company.company_name}', s['Subtitle'],
    ))
    story.append(Spacer(1, 4 * mm))

    # Table header
    headers = [
        'S.No', 'Emp Code', 'Name', 'Days',
        'Basic', 'DA', 'HRA', 'OT Wages', 'Other',
        'Gross', 'EPF', 'ESI', 'P.Tax', 'Other Ded.',
        'Total Ded.', 'Net Wages',
    ]

    # Column widths — tight to fit A4 landscape (we use portrait with small font)
    col_w = [
        8, 16, 34, 10,
        18, 14, 14, 16, 14,
        18, 14, 12, 12, 16,
        18, 20,
    ]
    col_w = [c * mm for c in col_w]

    # Totals accumulators — field names match salary_slip, not the old
    # wages_record; 'other_earnings'/'other_deductions' are computed
    # per-row below (salary_slip breaks these into several line items).
    totals = {k: 0 for k in ['working_days', 'basic_earned', 'da_earned', 'hra_earned',
                               'overtime_amount', 'other_earnings', 'gross_earnings',
                               'pf_deduction', 'esi_deduction', 'professional_tax',
                               'other_deductions', 'total_deductions', 'net_pay']}

    rows = [headers]
    for i, r in enumerate(qs, 1):
        other_earnings = (
            r.conveyance_earned + r.medical_allowance_earned + r.lunch_allowance_earned +
            r.cca_earned + r.special_allowance_earned + r.travel_allowance_earned +
            r.washing_allowance_earned + r.cycle_allowance_earned + r.other_allowance_earned +
            r.bonus_amount
        )
        other_deductions = r.loan_deduction + r.advance_deduction + r.late_fine + r.other_deduction

        totals['working_days'] += float(r.working_days or 0)
        totals['basic_earned'] += float(r.basic_earned or 0)
        totals['da_earned'] += float(r.da_earned or 0)
        totals['hra_earned'] += float(r.hra_earned or 0)
        totals['overtime_amount'] += float(r.overtime_amount or 0)
        totals['other_earnings'] += float(other_earnings or 0)
        totals['gross_earnings'] += float(r.gross_earnings or 0)
        totals['pf_deduction'] += float(r.pf_deduction or 0)
        totals['esi_deduction'] += float(r.esi_deduction or 0)
        totals['professional_tax'] += float(r.professional_tax or 0)
        totals['other_deductions'] += float(other_deductions or 0)
        totals['total_deductions'] += float(r.total_deductions or 0)
        totals['net_pay'] += float(r.net_pay or 0)

        rows.append([
            str(i),
            r.employee_id.employeecode,
            r.employee_id.name[:20],
            str(r.working_days or '—'),
            INR(r.basic_earned),
            INR(r.da_earned),
            INR(r.hra_earned),
            INR(r.overtime_amount),
            INR(other_earnings),
            INR(r.gross_earnings),
            INR(r.pf_deduction),
            INR(r.esi_deduction),
            INR(r.professional_tax),
            INR(other_deductions),
            INR(r.total_deductions),
            INR(r.net_pay),
        ])

    # Totals row
    rows.append([
        'TOTAL', '', '', str(int(totals['working_days'])),
        INR(totals['basic_earned']),
        INR(totals['da_earned']),
        INR(totals['hra_earned']),
        INR(totals['overtime_amount']),
        INR(totals['other_earnings']),
        INR(totals['gross_earnings']),
        INR(totals['pf_deduction']),
        INR(totals['esi_deduction']),
        INR(totals['professional_tax']),
        INR(totals['other_deductions']),
        INR(totals['total_deductions']),
        INR(totals['net_pay']),
    ])

    ts = table_style(header_bg=NAVY)
    # Right-align numeric columns (cols 4 onwards)
    ts.add('ALIGN', (4, 1), (-1, -1), 'RIGHT')
    ts.add('FONTSIZE', (0, 0), (-1, -1), 6.5)
    # Highlight totals row
    for cmd, *args in total_row_style():
        ts.add(cmd, *args)

    tbl = Table(rows, colWidths=col_w, style=ts, repeatRows=1)
    story.append(tbl)
    story.append(Spacer(1, 4 * mm))

    # Summary
    story.append(Paragraph(
        f'Total Employees: {len(qs)} · '
        f'Total Gross: {INR(totals["gross_earnings"])} · '
        f'Total Deductions: {INR(totals["total_deductions"])} · '
        f'Total Net: {INR(totals["net_pay"])}',
        s['Small'],
    ))
    story.append(Spacer(1, 8 * mm))

    # Signature row
    sig_ts = TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LINEABOVE', (0, 0), (0, 0), 0.5, MUTED),
        ('LINEABOVE', (1, 0), (1, 0), 0.5, MUTED),
        ('LINEABOVE', (2, 0), (2, 0), 0.5, MUTED),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ])
    story.append(Table(
        [['Prepared By', 'Checked By', 'Authorised By']],
        colWidths=[AVAIL / 3] * 3,
        style=sig_ts,
    ))

    doc_meta = {
        'title': f'Salary Register — {month_name} {year}',
        'doc_date': date.today(),
    }
    return build_pdf(story, company=company, doc_meta=doc_meta, **company.pdf_letterhead_kwargs())


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SALARY ABSTRACT (department-wise summary)
# ═══════════════════════════════════════════════════════════════════════════════

def salary_abstract_pdf(company, month, year):
    """
    Department-wise salary abstract — totals per department, then grand total.
    Useful for management review and statutory submission.

    Returns: bytes (PDF)
    """
    from collections import defaultdict
    qs = _wages_qs(company, month, year)
    s  = doc_styles()
    month_name = MONTH_NAMES.get(month, str(month))

    # Group by department
    dept_data = defaultdict(lambda: {
        'count': 0, 'gross': 0, 'epf': 0, 'esi': 0,
        'pt': 0, 'lwf': 0, 'other_ded': 0, 'total_ded': 0, 'net': 0,
    })
    for r in qs:
        dept = (getattr(r.employee_id, 'department_name', None) or
                getattr(getattr(r.employee_id, 'department', None), 'department_name', None) or
                'Unassigned')
        other_deductions = r.loan_deduction + r.advance_deduction + r.late_fine + r.other_deduction
        d = dept_data[dept]
        d['count'] += 1
        d['gross']     += float(r.gross_earnings or 0)
        d['epf']       += float(r.pf_deduction or 0)
        d['esi']       += float(r.esi_deduction or 0)
        d['pt']        += float(r.professional_tax or 0)
        d['lwf']       += float(r.labour_welfare_deduction or 0)
        d['other_ded'] += float(other_deductions or 0)
        d['total_ded'] += float(r.total_deductions or 0)
        d['net']       += float(r.net_pay or 0)

    story = []
    story.append(Paragraph('SALARY ABSTRACT', s['Title']))
    story.append(Paragraph(
        f'{month_name} {year}  ·  {company.company_name}', s['Subtitle'],
    ))
    story.append(Spacer(1, 5 * mm))

    # Abstract table
    headers = ['Department', 'Employees', 'Gross Wages', 'EPF', 'ESI',
               'P.Tax', 'LWF', 'Other Ded.', 'Total Ded.', 'Net Wages']
    col_w = [40, 22, 28, 20, 18, 18, 16, 22, 24, 28]
    col_w = [c * mm for c in col_w]

    grand = {k: 0 for k in ['count','gross','epf','esi','pt','lwf','other_ded','total_ded','net']}
    rows = [headers]
    for dept_name, d in sorted(dept_data.items()):
        for k in grand: grand[k] += d[k]
        rows.append([
            dept_name,
            str(d['count']),
            INR(d['gross']),
            INR(d['epf']),
            INR(d['esi']),
            INR(d['pt']),
            INR(d['lwf']),
            INR(d['other_ded']),
            INR(d['total_ded']),
            INR(d['net']),
        ])

    rows.append([
        'GRAND TOTAL', str(grand['count']),
        INR(grand['gross']), INR(grand['epf']), INR(grand['esi']),
        INR(grand['pt']), INR(grand['lwf']), INR(grand['other_ded']),
        INR(grand['total_ded']), INR(grand['net']),
    ])

    ts = table_style(header_bg=NAVY)
    ts.add('ALIGN', (1, 1), (-1, -1), 'RIGHT')
    for cmd, *args in total_row_style():
        ts.add(cmd, *args)

    story.append(Table(rows, colWidths=col_w, style=ts, repeatRows=1))
    story.append(Spacer(1, 5 * mm))

    # Statutory breakdown note
    story.append(section_divider())
    story.append(Paragraph('<b>Statutory Deductions Summary</b>', s['Heading2']))
    stat_pairs = [
        ('EPF Employer Share (3.67%)', INR(grand['epf'])),
        ('EPS Employer Share (8.33%)', '—'),
        ('ESI Employer Share (3.25%)', INR(grand['esi'] * (3.25 / 0.75) if grand['esi'] else 0)),
        ('Employee EPF (12%)', INR(grand['epf'])),
        ('Employee ESI (0.75%)', INR(grand['esi'])),
        ('Professional Tax (Employee)', INR(grand['pt'])),
        ('Labour Welfare Fund', INR(grand['lwf'])),
        ('Total Net Payable to Employees', INR(grand['net'])),
    ]
    story.append(kv_table(stat_pairs, col_widths=[AVAIL * 0.55, AVAIL * 0.45]))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(
        f'<b>Net Wages in Words:</b> {amount_in_words(grand["net"])}', s['Small'],
    ))
    story.append(Spacer(1, 10 * mm))

    sig_ts = TableStyle([
        ('ALIGN',    (0, 0), (-1, -1), 'CENTER'),
        ('LINEABOVE',(0, 0), (0, 0), 0.5, MUTED),
        ('LINEABOVE',(1, 0), (1, 0), 0.5, MUTED),
        ('LINEABOVE',(2, 0), (2, 0), 0.5, MUTED),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ])
    story.append(Table(
        [['Accounts Department', 'HR Manager', 'Director / Owner']],
        colWidths=[AVAIL / 3] * 3, style=sig_ts,
    ))

    doc_meta = {
        'title': f'Salary Abstract — {month_name} {year}',
        'doc_date': date.today(),
    }
    return build_pdf(story, company=company, doc_meta=doc_meta, **company.pdf_letterhead_kwargs())


# ═══════════════════════════════════════════════════════════════════════════════
# 4. GENERIC LETTERHEAD DOCUMENT
# ═══════════════════════════════════════════════════════════════════════════════

def letterhead_pdf(company, content_items, doc_meta=None):
    """
    Generic branded document — reports, notices, letters, compliance certificates.

    content_items: list of dicts, each:
        {'type': 'heading', 'text': '...'}
        {'type': 'para',    'text': '...'}
        {'type': 'kv',      'pairs': [('Key','Value'), ...]}
        {'type': 'table',   'headers': [...], 'rows': [[...], ...], 'col_widths': [...]}
        {'type': 'spacer',  'height': 5}  (mm)
        {'type': 'divider'}
        {'type': 'signature', 'labels': ['Left Label', 'Right Label']}

    Returns: bytes (PDF)

    Example — quotation:
        items = [
            {'type': 'heading', 'text': 'QUOTATION'},
            {'type': 'kv', 'pairs': [('To', 'ABC Corp'), ('Date', '17/07/2026'), ('Valid Till', '31/07/2026')]},
            {'type': 'table',
             'headers': ['Service', 'Qty', 'Rate', 'Amount'],
             'rows': [['HRMS Subscription', '1', '₹5000/mo', '₹5000']]},
            {'type': 'signature', 'labels': ['Client', 'Authorised Signatory']},
        ]
        pdf = letterhead_pdf(company, items, doc_meta={'title': 'Quotation', 'doc_number': 'Q/2026/001'})
    """
    s = doc_styles()
    story = []

    for item in content_items:
        t = item.get('type', 'para')

        if t == 'heading':
            level = item.get('level', 1)
            style = s['Heading1'] if level == 1 else s['Heading2']
            story.append(Paragraph(item['text'], style))

        elif t == 'para':
            story.append(Paragraph(item['text'], s['Normal']))

        elif t == 'kv':
            story.append(kv_table(item['pairs']))

        elif t == 'table':
            headers = item['headers']
            rows = item['rows']
            raw_widths = item.get('col_widths')
            if raw_widths:
                col_w = [w * mm for w in raw_widths]
            else:
                col_w = [AVAIL / len(headers)] * len(headers)
            tbl_data = [headers] + rows
            ts = table_style()
            tbl = Table(tbl_data, colWidths=col_w, style=ts, repeatRows=1)
            story.append(tbl)

        elif t == 'spacer':
            story.append(Spacer(1, item.get('height', 5) * mm))

        elif t == 'divider':
            story.append(section_divider())

        elif t == 'signature':
            labels = item.get('labels', ['Signature', 'Authorised Signatory'])
            count = len(labels)
            col_w = [AVAIL / count] * count
            ts = TableStyle([
                ('ALIGN',    (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('LINEABOVE',(0, 0), (-1, 0), 0.5, MUTED),
            ])
            story.append(Spacer(1, 10 * mm))
            story.append(Table([labels], colWidths=col_w, style=ts))

    return build_pdf(story, company=company, doc_meta=doc_meta or {'title': 'Document'}, **company.pdf_letterhead_kwargs())


# ═══════════════════════════════════════════════════════════════════════════════
# 5. COMPANY PROFILE PDF
# ═══════════════════════════════════════════════════════════════════════════════

def company_profile_pdf(company):
    """
    Official company profile document — suitable for tenders, registrations.
    Pulls all available fields from the Company model instance.

    Returns: bytes (PDF)
    """
    s = doc_styles()

    def g(field, default='—'):
        return str(getattr(company, field, None) or default)

    story = []
    story.append(Paragraph('COMPANY PROFILE', s['Title']))
    story.append(Spacer(1, 2 * mm))

    # Section 1 — Basic info
    story.append(Paragraph('Company Information', s['Heading1']))
    story.append(section_divider())
    story.append(kv_table([
        ('Company Name',    g('company_name')),
        ('Tagline',         g('tagline1') or g('company_tagline')),
        ('Type',            g('company_type') or g('industry_type')),
        ('Nature of Work',  g('nature_of_work') or g('business_description')),
        ('Incorporation Date', g('incorporation_date') or g('reg_date') or g('start_date')),
        ('CIN',             g('cin')),
    ]))
    story.append(Spacer(1, 2 * mm))

    # Section 2 — Statutory IDs
    story.append(Paragraph('Statutory Registration Numbers', s['Heading1']))
    story.append(section_divider())
    story.append(kv_table([
        ('PAN',             g('pan')),
        ('GSTIN',           g('gstin') or g('gst_no')),
        ('EPFO Code',       g('epf_code') or g('pf_code')),
        ('ESIC Code',       g('esi_code') or g('esic_code')),
        ('PT Reg. No.',     g('pt_reg_no') or g('professional_tax_no')),
        ('Factory Licence', g('factory_license_no')),
        ('Shops Act Reg.',  g('shop_act_no') or g('registration_number')),
        ('LWF Code',        g('lwf_code')),
    ]))
    story.append(Spacer(1, 2 * mm))

    # Section 3 — Contact
    story.append(Paragraph('Contact Details', s['Heading1']))
    story.append(section_divider())
    story.append(kv_table([
        ('Registered Address',  f"{g('address1') or ''} {g('address2') or ''} {g('address3') or ''} {g('district_id') or ''}-{g('pin') or ''},{g('state_id') or ''}".strip(', ')),
        ('Mobile',             g('mobile') or g('phone')),
        ('Email',              g('email1') or g('email')),
        ('Website',            g('website')),
    ]))
    story.append(Spacer(1, 2 * mm))

    # Section 4 — Workforce summary (live query)
    try:
        from Aapp.app.employee import employee as Employee
        emp_count  = Employee.objects.filter(CompanyID=company, is_working=True).count()
        total_emp  = Employee.objects.filter(CompanyID=company).count()
        story.append(Paragraph('Workforce Summary', s['Heading1']))
        story.append(section_divider())
        story.append(kv_table([
            ('Active Employees',   str(emp_count)),
            ('Total Employees',    str(total_emp)),
        ]))
        story.append(Spacer(1, 2 * mm))
    except Exception:
        pass  # model import may differ — skip silently

    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        'This profile has been generated from the company records maintained in '
        'Revolution Associates HRMS. For official use only.',
        s['Small'],
    ))

    doc_meta = {
        'ref': f'CP/{g("pan")}/{date.today().year}',
        'title': 'Company Pro',
        'doc_date': date.today(),
    }
    return build_pdf(story, company=company, doc_meta=doc_meta, **company.pdf_letterhead_kwargs())