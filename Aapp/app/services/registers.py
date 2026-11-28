"""Fines, deductions and overtime register builders, extracted from phase2_generator.py (D5b).

Pure: company + month/year in, (pdf bytes, filename) out. Raises NothingToGenerate when the
period has no records and FileBuildError when the PDF cannot be built. Output is unchanged.
"""
import calendar
import logging

from Aapp.app.services.statutory_files import FileBuildError, NothingToGenerate, _slug

logger = logging.getLogger(__name__)


def _parts():
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib.units import mm
    from Aapp.app.pdf_engine import build_pdf, kv_table, INR, _basefont_bold
    from Aapp.app.phase2_generator import HEADER_STYLE
    return Table, TableStyle, Spacer, mm, build_pdf, kv_table, INR, _basefont_bold, HEADER_STYLE


def _finish(company, month, year, rows, widths, align_cols, title, doc_prefix, what, file_prefix):
    Table, TableStyle, Spacer, mm, build_pdf, kv_table, INR, bold, HEADER_STYLE = _parts()
    story = [kv_table([('Establishment Name', company.company_name), ('Period', f'{month}/{year}')])]
    story.append(Spacer(1, 6 * mm))
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle(HEADER_STYLE + [
        ('ALIGN',) + align_cols + ('RIGHT',),
        ('FONTNAME', (0, -1), (-1, -1), bold),
    ]))
    story.append(t)
    try:
        pdf = build_pdf(story, company, doc_meta={'title': title, 'doc_number': f'{doc_prefix}-{month}-{year}'})
    except Exception as e:
        logger.exception('%s PDF failed for %s/%s: %s', what, month, year, e)
        raise FileBuildError(f'Could not generate {what}.')
    return pdf, f'{file_prefix}_{_slug(company)}_{month}_{year}.pdf'


def build_fines_register_pdf(company, month, year):
    from Aapp.app.wages import wages_fine
    from Aapp.app.pdf_engine import INR
    records = (wages_fine.objects.filter(company=company, salary_month=month, salary_year=year)
               .select_related('employee').order_by('employee__name', 'fine_date'))
    if not records.exists():
        raise NothingToGenerate(f'No fines recorded for {calendar.month_name[month]} {year}.')
    rows = [['Employee', 'Date', 'Reason', 'Amount (₹)']]
    total = 0
    for f in records:
        rows.append([f.employee.name, f.fine_date.strftime('%d-%b-%Y'), f.fine_reason, INR(f.fine_amount)])
        total += f.fine_amount
    rows.append(['', '', 'TOTAL', INR(total)])
    return _finish(company, month, year, rows, [140, 80, 200, 90], ((3, 0), (3, -1)),
                   'Fines Register (Form I)', 'FINES', 'Fines register', 'Fines_Register')


def build_deductions_register_pdf(company, month, year):
    from Aapp.app.wages import wages_deduction
    from Aapp.app.pdf_engine import INR
    records = (wages_deduction.objects.filter(company=company, salary_month=month, salary_year=year)
               .select_related('employee').order_by('employee__name'))
    if not records.exists():
        raise NothingToGenerate(f'No deductions recorded for {calendar.month_name[month]} {year}.')
    rows = [['Employee', 'Type', 'Reason', 'Amount (₹)']]
    total = 0
    for d in records:
        rows.append([d.employee.name, d.get_deduction_type_display(), d.reason, INR(d.deduction_amount)])
        total += d.deduction_amount
    rows.append(['', '', 'TOTAL', INR(total)])
    return _finish(company, month, year, rows, [140, 100, 180, 90], ((3, 0), (3, -1)),
                   'Deductions Register (Form II)', 'DEDUCT', 'Deductions register', 'Deductions_Register')


def build_ot_register_pdf(company, month, year):
    from Aapp.app.attandance import MinimumWagesOvertimeRegister
    from Aapp.app.pdf_engine import INR
    records = (MinimumWagesOvertimeRegister.objects
               .filter(attendance__companyid=company,
                       attendance__salary_month=month, attendance__salary_year=year)
               .select_related('attendance').order_by('attendance__emp_code', 'ot_date'))
    if not records.exists():
        raise NothingToGenerate(f'No overtime records found for {calendar.month_name[month]} {year}.')
    rows = [['Emp Code', 'OT Date', 'Hours', 'Ordinary Rate', 'OT Rate', 'OT Wages Paid']]
    total = 0
    for r in records:
        rows.append([r.attendance.emp_code, r.ot_date.strftime('%d-%b-%Y'),
                     str(r.overtime_hours), INR(r.ordinary_rate), INR(r.ot_rate), INR(r.ot_wages_paid)])
        total += r.ot_wages_paid
    rows.append(['', '', '', '', 'TOTAL', INR(total)])
    return _finish(company, month, year, rows, [80, 80, 60, 90, 90, 100], ((2, 0), (5, -1)),
                   'Overtime Register (Form IV)', 'OT', 'Overtime register', 'Overtime_Register')
