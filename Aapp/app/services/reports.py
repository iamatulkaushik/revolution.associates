"""Report builders extracted from Aapp views (D5). Pure: company in, file out, no request."""
import io

from Aapp.app.services.statutory_files import NothingToGenerate, _slug


def build_form24q_xlsx(company, financial_year):
    """Form 24Q deductee prep sheet for a financial year ('2025-26'). Returns (bytes, filename)."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    from Aapp.app.form16 import tds_filing_helper_rows

    rows = tds_filing_helper_rows(company, financial_year)
    if not rows:
        raise NothingToGenerate(
            f'No employees with PAN and TDS activity found for FY {financial_year}.'
        )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Form 24Q Prep'

    headers = ['Employee Code', 'Employee Name', 'PAN', 'Gross Salary', 'TDS Deducted', 'Regime']
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='0B2545')

    for r in rows:
        ws.append([r['employee_code'], r['employee_name'], r['pan'],
                   float(r['gross_salary']), float(r['tds_deducted']), r['regime']])

    for col_letter, width in zip('ABCDEF', [14, 26, 12, 16, 16, 10]):
        ws.column_dimensions[col_letter].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.read(), f'Form24Q_Prep_{_slug(company)}_{financial_year}.xlsx'
