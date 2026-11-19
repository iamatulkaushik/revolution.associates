"""Capp/invoice_export.py — invoice PDF (with employee annexure) and Excel."""
import calendar
import io

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, PageBreak

from Aapp.app.pdf_engine import (INR, amount_in_words, build_pdf, doc_styles, table_style)

PERIOD = lambda inv: f'{calendar.month_name[inv.month]} {inv.year}'


def _rows(inv):
    """(label, amount) rows of the bill, in order."""
    if inv.kind == 'OT':
        rows = [('Overtime wages', inv.pay)]
    else:
        rows = [('Wages (gross)', inv.pay), ('EPF employer contribution', inv.epf_employer),
                ('ESI employer contribution', inv.esi_employer), ('Labour welfare fund', inv.lwf),
                ('Attendance bonus', inv.att_bonus)]
        rows = [r for r in rows if r[0] == 'Wages (gross)' or r[1]]
    rows.append((f'Service charge @ {inv.service_charge_pct}%', inv.service_charge))
    rows.append(('Sub total', inv.subtotal))
    half = inv.gst_pct / 2
    rows += [(f'SGST @ {half}%', inv.sgst), (f'CGST @ {half}%', inv.cgst)]
    if inv.extra_charges:
        rows.append((inv.extra_label or 'Other charges', inv.extra_charges))
    return rows


def invoice_pdf(inv):
    st = doc_styles()
    story = [Paragraph('INVOICE' if inv.kind == 'SALARY' else 'INVOICE - OVERTIME', st['Title'])]
    meta = Table([
        [Paragraph(f'<b>To:</b> {inv.client.name}<br/>{inv.client.address or ""}'
                   f'<br/>GSTIN: {inv.client.gstin or "-"}', st['Normal']),
         Paragraph(f'<b>Invoice No:</b> {inv.number}<br/>'
                   f'<b>Date:</b> {inv.invoice_date:%d-%m-%Y}<br/>'
                   f'<b>Period:</b> {PERIOD(inv)}', st['Normal'])]],
        colWidths=[95 * mm, 75 * mm])
    story += [meta, Spacer(1, 6 * mm)]

    data = [['Particulars', 'Amount']] + [[l, INR(a)] for l, a in _rows(inv)]
    data.append(['TOTAL', INR(inv.total)])
    t = Table(data, colWidths=[120 * mm, 50 * mm])
    t.setStyle(table_style())
    story += [t, Spacer(1, 4 * mm),
              Paragraph(f'<b>Amount in words:</b> {amount_in_words(inv.total)}', st['Normal'])]

    story.append(PageBreak())
    story.append(Paragraph(f'Annexure - Employee details, {PERIOD(inv)}', st['Heading1']))
    if inv.kind == 'OT':
        head = ['#', 'Code', 'Name', 'OT hours', 'OT pay']
        body = [[i, l.emp_code, l.name, f'{l.ot_hours:g}', INR(l.ot_pay)]
                for i, l in enumerate(inv.lines.all(), 1)]
        widths = [10, 22, 70, 25, 35]
    else:
        head = ['#', 'Code', 'Name', 'Days', 'Gross', 'EPF', 'ESI', 'LWF', 'Bonus']
        body = [[i, l.emp_code, l.name, f'{l.paid_days:g}', INR(l.gross), INR(l.epf_employer),
                 INR(l.esi_employer), INR(l.lwf), INR(l.att_bonus)]
                for i, l in enumerate(inv.lines.all(), 1)]
        widths = [8, 18, 44, 12, 24, 20, 20, 14, 18]
    tt = Table([head] + body, colWidths=[w * mm for w in widths], repeatRows=1)
    tt.setStyle(table_style())
    story.append(tt)
    meta = {'title': f'Invoice {inv.number}', 'doc_number': inv.number,
            'doc_date': inv.invoice_date.strftime('%d-%m-%Y')}
    return build_pdf(story, company=inv.company, doc_meta=meta)


def invoice_xlsx(inv):
    import openpyxl
    from openpyxl.styles import Font
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Invoice'
    ws.append([f'Invoice {inv.number}', inv.client.name])
    ws.append(['Period', PERIOD(inv), 'Date', inv.invoice_date.strftime('%d-%m-%Y')])
    ws.append([])
    ws.append(['Particulars', 'Amount'])
    for c in ws[4]:
        c.font = Font(bold=True)
    for label, amt in _rows(inv):
        ws.append([label, float(amt)])
    ws.append(['TOTAL', float(inv.total)])
    ws.column_dimensions['A'].width = 38
    ws.column_dimensions['B'].width = 18

    an = wb.create_sheet('Employees')
    if inv.kind == 'OT':
        an.append(['Code', 'Name', 'Designation', 'OT hours', 'OT pay'])
        for l in inv.lines.all():
            an.append([l.emp_code, l.name, l.designation, float(l.ot_hours), float(l.ot_pay)])
    else:
        an.append(['Code', 'Name', 'Designation', 'Days', 'Gross', 'EPF employer',
                   'ESI employer', 'LWF', 'Bonus'])
        for l in inv.lines.all():
            an.append([l.emp_code, l.name, l.designation, float(l.paid_days), float(l.gross),
                       float(l.epf_employer), float(l.esi_employer), float(l.lwf),
                       float(l.att_bonus)])
    for c in an[1]:
        c.font = Font(bold=True)

    pay = wb.create_sheet('Payment')
    pay.append(['Invoice total', float(inv.total)])
    pay.append(['Received', float(inv.received_amount)])
    pay.append(['TDS deducted', float(inv.tds_amount)])
    pay.append(['Outstanding', float(inv.outstanding)])
    pay.append(['Received on', inv.received_on.strftime('%d-%m-%Y') if inv.received_on else ''])
    pay.append(['Reference', inv.payment_ref])
    pay.append(['Status', inv.get_status_display()])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
