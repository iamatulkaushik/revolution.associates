"""Statutory file builders (EPF ECR + challan, ESI challan + upload, LWF challan),
extracted from ecr_generator.py, esi_generator.py, lwf_generator.py and epf_esi.py (D3).

Pure functions: they take a company (and a record or month/year), never a request, and
return the file bytes/text plus a filename. The Aapp views call these and keep their own
HTTP handling; Capp (DIRECT mode) calls them too. Output is unchanged.

Gating by registration (EPF/ESIC/LWF numbers) is the caller's job, as before.
"""
import calendar
import io
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class StatutoryFileError(Exception):
    """Base class. str(e) is the user-facing message."""


class NothingToGenerate(StatutoryFileError):
    """No eligible employees / data for the period."""


class AlreadyExists(StatutoryFileError):
    """A record for the period already exists."""


class FileBuildError(StatutoryFileError):
    """The PDF could not be built."""


def _slug(company):
    return company.company_name.replace(' ', '_')


# ── EPF ───────────────────────────────────────────────────────────────────────

def create_epf_ecr(company, month, year, user):
    """Create the monthly EpfMonthlyEcr header from processed salary slips."""
    from Aapp.app.epf_esi import EpfMonthlyEcr, _compute_epf_ecr_totals

    if EpfMonthlyEcr.objects.filter(company=company, salary_month=month, salary_year=year).exists():
        raise AlreadyExists(f'An ECR for {month}/{year} already exists. Edit it instead.')

    totals = _compute_epf_ecr_totals(company, month, year)
    if totals['total_members'] == 0:
        raise NothingToGenerate(
            f'No EPF-enrolled employees with salary processed for {month}/{year}.')

    ecr = EpfMonthlyEcr(company=company, salary_month=month, salary_year=year,
                        created_by=user, **totals)
    ecr.save()
    return ecr


def build_ecr_text(company, ecr):
    """ECR-2.0 text. Returns (content, filename, skipped_employee_codes)."""
    from Aapp.app.ecr_generator import _member_lines

    lines, skipped = _member_lines(company, ecr.salary_month, ecr.salary_year)
    if not lines:
        raise NothingToGenerate(
            'No EPF-enrolled employees with salary slips found for '
            f'{ecr.salary_month}/{ecr.salary_year}. Ensure UAN is set on '
            'employee records and salary has been processed for this period.'
        )
    if skipped:
        logger.warning(
            'ECR %s/%s for %s: skipped %d employee(s) with no UAN: %s',
            ecr.salary_month, ecr.salary_year, company.company_name,
            len(skipped), ', '.join(skipped)
        )
    content = '\n'.join(lines) + '\n'
    fname = f'ECR_{_slug(company)}_{ecr.salary_month}_{ecr.salary_year}.txt'
    return content, fname, skipped


def build_epf_challan_pdf(company, ecr):
    """EPF combined challan PDF from the ECR header totals. Returns (pdf, filename)."""
    from Aapp.app.pdf_engine import build_pdf, doc_styles, kv_table, INR, section_divider
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    doc_styles()
    story = []
    story.append(kv_table([
        ('Establishment Name', company.company_name),
        ('Wage Month', f'{ecr.salary_month}/{ecr.salary_year}'),
        ('Total Members', str(ecr.total_members)),
    ]))
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())

    rows = [
        ['A/C No.', 'Particulars', 'Amount (₹)'],
        ['1',  'EPF Contribution (Employee 12% + Employer 3.67%)',
         INR(Decimal(ecr.employee_epf) + Decimal(ecr.employer_epf))],
        ['2',  'EPF Admin Charges (0.5%, min ₹500)', INR(ecr.admin_charges)],
        ['10', 'EPS Contribution (Employer 8.33%)',  INR(ecr.employer_eps)],
        ['21', 'EDLI Contribution (0.5%)',            INR(ecr.edli_contribution)],
        ['22', 'EDLI Admin Charges',                  INR(Decimal('0.00'))],
        ['',   'TOTAL REMITTANCE',                    INR(ecr.total_contribution)],
    ]
    t = Table(rows, colWidths=[60, 300, 120])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0B2545')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEBELOW', (0, -2), (-1, -2), 1, colors.black),
        ('GRID', (0, 0), (-1, -2), 0.4, colors.HexColor('#CBD5E1')),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'EPF Combined Challan',
            'doc_number': ecr.challan_no or f'ECR-{ecr.salary_month}-{ecr.salary_year}',
        })
    except Exception as e:
        logger.exception('EPF challan PDF failed for ecr_id=%s: %s', ecr.ecr_id, e)
        raise FileBuildError('Could not generate EPF challan.')

    return pdf, f'EPF_Challan_{_slug(company)}_{ecr.salary_month}_{ecr.salary_year}.pdf'


# ── ESI ───────────────────────────────────────────────────────────────────────

def _eligible_esi_slips(company, month, year):
    from Aapp.app.esi_generator import _esi_slips
    slips = _esi_slips(company, month, year)
    return [s for s in slips if (getattr(s.employee_id, 'esic_number', '') or '').strip()]


def build_esi_challan_pdf(company, month, year):
    """ESIC challan PDF. ESIC rounds up per slip here, in the challan file only."""
    from Aapp.app.esi_generator import _ceil_rupee, _wage_rupees
    from Aapp.app.pdf_engine import build_pdf, kv_table, INR, section_divider
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    eligible = _eligible_esi_slips(company, month, year)
    if not eligible:
        raise NothingToGenerate(
            f'No ESI-eligible employees with ESIC number found for {calendar.month_name[month]} {year}. '
            'Ensure ESIC number is set on employee records and salary has been processed.'
        )

    total_wages = sum((Decimal(_wage_rupees(s.gross_earnings)) for s in eligible), Decimal('0'))
    total_employee = sum((_ceil_rupee(s.esi_deduction) for s in eligible), Decimal('0'))
    total_employer = sum((_ceil_rupee(s.esi_employer_contribution) for s in eligible), Decimal('0'))
    total_contribution = total_employee + total_employer

    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Contribution Month', f'{calendar.month_name[month]} {year}'),
        ('No. of Insured Persons', str(len(eligible))),
    ])]
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())

    rows = [
        ['Particulars', 'Amount (₹)'],
        ['Total Wages', INR(total_wages)],
        ['Employee Contribution (0.75%)', INR(total_employee)],
        ['Employer Contribution (3.25%)', INR(total_employer)],
        ['TOTAL CONTRIBUTION', INR(total_contribution)],
    ]
    t = Table(rows, colWidths=[300, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0B2545')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEBELOW', (0, -2), (-1, -2), 1, colors.black),
        ('GRID', (0, 0), (-1, -2), 0.4, colors.HexColor('#CBD5E1')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'ESI Monthly Contribution Challan',
            'doc_number': f'ESI-{month}-{year}',
        })
    except Exception as e:
        logger.exception('ESI challan PDF failed for %s/%s: %s', month, year, e)
        raise FileBuildError('Could not generate ESI challan.')

    return pdf, f'ESI_Challan_{_slug(company)}_{month}_{year}.pdf'


def build_esi_upload_xlsx(company, month, year):
    """ESIC monthly contribution member upload. Returns (bytes, filename)."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    from Aapp.app.esi_generator import ESIC_REASON_ON_LEAVE, _wage_rupees

    eligible = _eligible_esi_slips(company, month, year)
    if not eligible:
        raise NothingToGenerate(
            f'No ESI-eligible employees with ESIC number found for {calendar.month_name[month]} {year}.'
        )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'ESI Monthly Upload'

    headers = ['IP Number', 'IP Name', 'No. of Days', 'Total Monthly Wages',
               'Reason for Zero Wages', 'Last Working Day']
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='0B2545')

    for s in eligible:
        emp = s.employee_id
        wages = _wage_rupees(s.gross_earnings)
        days = int(s.paid_days or 0)
        row = [
            (emp.esic_number or '').strip(),
            (emp.name or '').strip().upper(),
            str(days),
            str(wages),
            '' if wages > 0 else ESIC_REASON_ON_LEAVE,
            '',
        ]
        ws.append(row)
        for col_idx in range(1, len(row) + 1):
            ws.cell(row=ws.max_row, column=col_idx).number_format = '@'

    for col_letter, width in zip('ABCDEF', [14, 28, 12, 18, 20, 16]):
        ws.column_dimensions[col_letter].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.read(), f'ESI_Upload_{_slug(company)}_{month}_{year}.xlsx'


# ── LWF ───────────────────────────────────────────────────────────────────────

def build_lwf_challan_pdf(company, rec):
    """LWF challan PDF for one LabourWelfareFundContribution. Returns (pdf, filename)."""
    from Aapp.app.pdf_engine import build_pdf, kv_table, INR, section_divider
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Contribution Period', f'{rec.get_contribution_period_display()} {rec.year}'),
        ('Total Employees', str(rec.total_employees)),
        ('Due Date', rec.due_date.strftime('%d %b %Y') if rec.due_date else '—'),
    ])]
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())

    rows = [
        ['Particulars', 'Amount (₹)'],
        ['Employee Contribution', INR(rec.employee_contribution)],
        ['Employer Contribution', INR(rec.employer_contribution)],
    ]
    if rec.is_late and rec.late_interest_amount:
        rows.append(['Late Interest (Sec. 9A @ 12%)', INR(rec.late_interest_amount)])
    rows.append(['TOTAL CONTRIBUTION', INR(rec.total_contribution + (rec.late_interest_amount if rec.is_late else 0))])

    t = Table(rows, colWidths=[300, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0B2545')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEBELOW', (0, -2), (-1, -2), 1, colors.black),
        ('GRID', (0, 0), (-1, -2), 0.4, colors.HexColor('#CBD5E1')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'Labour Welfare Fund Challan',
            'doc_number': rec.challan_no or f'LWF-{rec.contribution_period}-{rec.year}',
        })
    except Exception as e:
        logger.exception('LWF challan PDF failed for lwf_id=%s: %s', rec.lwf_id, e)
        raise FileBuildError('Could not generate LWF challan.')

    return pdf, f'LWF_Challan_{_slug(company)}_{rec.contribution_period}_{rec.year}.pdf'
