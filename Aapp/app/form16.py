"""
Aapp/app/form16.py
====================
Form 16 (Part A + Part B) generation and TDS filing helper reports.

Form 16 is only issuable if the company holds a TAN (gates['income_tax'])
and the employee holds a PAN — same fail-closed pair used at deduction
time in salary_processing.py. If either is missing, generation is
refused rather than emitting a Form 16 with a blank TAN/PAN field.

Functions:
  annual_tax_summary(employee, financial_year)      -> dict of yearly totals
  form16_pdf(employee, financial_year)               -> bytes
  tds_filing_helper_rows(company, financial_year)    -> queryset-derived rows for 24Q prep
  deductions_report_pdf(company, month, year)        -> separate IT-only deductions report
"""

from datetime import date

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.colors import HexColor

from Aapp.app.pdf_engine import (
    build_pdf, doc_styles, INR, amount_in_words,
    table_style, total_row_style, section_divider, kv_table,
    NAVY, STEEL, TEAL, CORAL, CREAM, LIGHT, WHITE, MUTED,
)
from Aapp.app.income_tax import EmployeeTaxProfile, calculate_annual_tax


def _fy_bounds(financial_year):
    """'2025-26' -> ((2025, 4), (2026, 3)) i.e. Apr start_year to Mar end_year."""
    start_year = int(financial_year.split('-')[0])
    end_year = start_year + 1
    return (start_year, 4), (end_year, 3)


def _fy_month_year_pairs(financial_year):
    (sy, sm), (ey, em) = _fy_bounds(financial_year)
    pairs = []
    y, m = sy, sm
    while (y, m) != (ey, em + 1):
        pairs.append((m, y))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return pairs


def annual_tax_summary(employee_obj, financial_year):
    """
    Aggregates gross earnings and TDS deducted across all salary_slip
    rows for the employee within the given FY. Returns None if the
    employee has no PAN on file — nothing to report.
    """
    if not getattr(employee_obj, 'pan_number', None):
        return None

    from Aapp.app.salary_processing import salary_slip

    pairs = _fy_month_year_pairs(financial_year)
    q = salary_slip.objects.none()
    for m, y in pairs:
        q = q | salary_slip.objects.filter(
            employee_id=employee_obj, processing_id__month=m, processing_id__year=y
        )

    slips = list(q.select_related('processing_id', 'company_id'))
    if not slips:
        return None

    gross_total = sum((s.gross_earnings for s in slips), start=0)
    pf_total = sum((s.pf_deduction for s in slips), start=0)
    tds_total = sum((s.income_tax for s in slips), start=0)

    tax_profile = EmployeeTaxProfile.objects.filter(
        employee=employee_obj, financial_year=financial_year
    ).first()

    computed = calculate_annual_tax(gross_total, tax_profile)

    return {
        'employee': employee_obj,
        'company': slips[0].company_id,
        'financial_year': financial_year,
        'months_covered': len(slips),
        'gross_total': gross_total,
        'pf_total': pf_total,
        'tds_deducted': tds_total,
        'regime': computed['regime'],
        'taxable_income': computed['taxable_income'],
        'total_tax_liability': computed['total_tax'],
        'shortfall_or_excess': computed['total_tax'] - tds_total,
    }


def form16_pdf(employee_obj, financial_year):
    """
    Returns Form 16 (Part A + Part B combined single document) as bytes.
    Refuses (returns None) if company has no TAN or employee has no PAN.
    """
    from Aapp.app.statutory_gates import get_company_gates

    summary = annual_tax_summary(employee_obj, financial_year)
    if not summary:
        return None

    company = summary['company']
    gates = get_company_gates(company)
    if not gates['income_tax']:
        return None  # no TAN, cannot issue Form 16

    styles = doc_styles()
    story = []

    story.append(Paragraph("FORM 16", styles['Heading1']))
    story.append(Paragraph(
        "Certificate under Section 203 of the Income-tax Act, 1961 for tax deducted at source on salary",
        styles['Small']
    ))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("PART A", styles['Heading2']))
    part_a_rows = [
        ("Employer TAN", getattr(company, 'tan', '') or '-'),
        ("Employer PAN", getattr(company, 'pan', '') or '-'),
        ("Employer Name & Address", getattr(company, 'company_name', '')),
        ("Employee PAN", employee_obj.pan_number or '-'),
        ("Employee Name", employee_obj.name),
        ("Financial Year", financial_year),
        ("Assessment Year", f"{int(financial_year.split('-')[0]) + 1}-{str(int(financial_year.split('-')[0]) + 2)[-2:]}"),
        ("Total TDS Deducted", INR(summary['tds_deducted'])),
    ]
    story.append(kv_table(part_a_rows))
    story.append(Spacer(1, 6 * mm))
    story.append(section_divider())

    story.append(Paragraph("PART B — Details of Salary Paid and Tax Deducted", styles['Heading2']))
    part_b_rows = [
        ("Gross Salary", INR(summary['gross_total'])),
        ("Tax Regime Opted", "New Regime (115BAC)" if summary['regime'] == 'new' else "Old Regime"),
        ("Total Taxable Income", INR(summary['taxable_income'])),
        ("Total Tax Liability (incl. cess)", INR(summary['total_tax_liability'])),
        ("Total TDS Deducted During FY", INR(summary['tds_deducted'])),
        ("Balance (Payable / Refundable)", INR(summary['shortfall_or_excess'])),
    ]
    story.append(kv_table(part_b_rows))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f"In words: {amount_in_words(summary['total_tax_liability'])}",
        styles['Small']
    ))

    doc_meta = {
        'title': f"Form 16 - {employee_obj.name} - FY{financial_year}",
        'doc_number': f"F16/{employee_obj.employeecode}/{financial_year}",
        'doc_date': date.today().strftime('%d-%m-%Y'),
    }
    return build_pdf(story, company=company, doc_meta=doc_meta)


def tds_filing_helper_rows(company, financial_year):
    """
    Auto-prepared rows for Form 24Q filing — one row per employee with
    PAN, gross, and TDS totals for the FY. Employees without a PAN are
    excluded (they cannot appear on a 24Q deductee annexure).
    Returns a list of dicts, ready to hand to an Excel export.
    """
    from Aapp.app.employee import employee as employee_model

    rows = []
    employees = employee_model.objects.filter(CompanyID=company, is_working=True).exclude(
        pan_number__isnull=True
    ).exclude(pan_number='')

    for emp in employees:
        summary = annual_tax_summary(emp, financial_year)
        if summary:
            rows.append({
                'employee_code': emp.employeecode,
                'employee_name': emp.name,
                'pan': emp.pan_number,
                'gross_salary': summary['gross_total'],
                'tds_deducted': summary['tds_deducted'],
                'regime': summary['regime'],
            })
    return rows


def deductions_report_pdf(company, month, year):
    """
    Separate report showing ONLY income-tax deductions for a given
    month — per pt_upgrades.md "saprate report for income tax deductions",
    distinct from the general salary sheet.
    """
    from Aapp.app.salary_processing import salary_slip

    slips = (salary_slip.objects
             .filter(company_id=company, processing_id__month=month, processing_id__year=year)
             .exclude(income_tax=0)
             .select_related('employee_id')
             .order_by('employee_id__employeecode'))

    styles = doc_styles()
    story = [Paragraph("Income Tax Deductions Report", styles['Heading1']), Spacer(1, 4 * mm)]

    data = [["Emp Code", "Name", "PAN", "Gross", "TDS Deducted"]]
    total_tds = 0
    for s in slips:
        data.append([
            s.employee_id.employeecode,
            s.employee_id.name,
            s.employee_id.pan_number or '-',
            INR(s.gross_earnings),
            INR(s.income_tax),
        ])
        total_tds += s.income_tax

    data.append(["", "", "", "Total", INR(total_tds)])

    tbl = Table(data, colWidths=[70, 140, 80, 90, 90])
    tbl.setStyle(table_style())
    tbl.setStyle(total_row_style())
    story.append(tbl)

    doc_meta = {
        'title': f"IT Deductions Report {month}/{year}",
        'doc_date': date.today().strftime('%d-%m-%Y'),
    }
    return build_pdf(story, company=company, doc_meta=doc_meta)
