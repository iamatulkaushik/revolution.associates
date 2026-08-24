"""
Aapp/app/punch_report_pdf.py
================================
Daily punch/attendance sheet PDF, per pt_upgrades.md:
"RFID attandnace sheet schedule for referance and record".
"""

from datetime import date

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table

from Aapp.app.pdf_engine import build_pdf, doc_styles, table_style, total_row_style


def punch_sheet_pdf(company, month, year):
    from Aapp.app.punch_log import DailyAttendance

    rows = (DailyAttendance.objects
            .filter(company=company, attendance_date__year=year, attendance_date__month=month)
            .select_related('employee', 'shift')
            .order_by('employee__employeecode', 'attendance_date'))

    styles = doc_styles()
    story = [
        Paragraph(f"Biometric/RFID Attendance Sheet — {month}/{year}", styles['Heading1']),
        Spacer(1, 4 * mm),
    ]

    data = [["Emp Code", "Name", "Date", "First In", "Last Out", "Late (min)", "Early (min)", "OT (hrs)", "LOP"]]
    for r in rows:
        data.append([
            r.employee.employeecode,
            r.employee.name,
            r.attendance_date.strftime('%d-%m-%Y'),
            r.first_in.strftime('%H:%M') if r.first_in else '-',
            r.last_out.strftime('%H:%M') if r.last_out else '-',
            str(r.late_minutes),
            str(r.early_leaving_minutes),
            str(r.overtime_hours),
            'Yes' if r.is_lop else '-',
        ])

    tbl = Table(data, colWidths=[60, 100, 65, 55, 55, 55, 55, 50, 40])
    tbl.setStyle(table_style())
    story.append(tbl)

    doc_meta = {
        'title': f"Punch Sheet {month}/{year}",
        'doc_date': date.today().strftime('%d-%m-%Y'),
    }
    return build_pdf(story, company=company, doc_meta=doc_meta)
