"""
Capp/bank_export.py
===================
Bank payment files from BankFormat definitions (stored per company).

- Employees are grouped by IFSC prefix (first 4 letters).
- Payout = salary-slip net pay minus custom deductions, rounded UP to the
  whole rupee.
- No format saved for a bank -> plain CSV fallback.
"""
import csv
import io
from collections import OrderedDict
from decimal import Decimal, ROUND_CEILING

from Capp.billing_models import BankFormat, EmployeeDeduction

D = Decimal
FALLBACK_COLUMNS = [('S.No', 'serial'), ('Employee ID', 'emp_code'), ('Name', 'name'),
                    ('IFSC', 'ifsc'), ('Account No', 'account'), ('Net Pay', 'net_pay')]


def rupee_up(x):
    return D(x).quantize(D('1'), rounding=ROUND_CEILING)


def deduction_for(emp_id, company, year, month):
    """Sum of custom deductions applying to this employee in the month."""
    total = D('0')
    qs = EmployeeDeduction.objects.filter(company=company, employee_id=emp_id,
                                          is_closed=False, is_paused=False)
    for d in qs:
        s = d.start_month
        if (s.year, s.month) > (year, month):
            continue
        if d.kind == 'ONCE' and (s.year, s.month) != (year, month):
            continue
        total += d.amount_for_month()
    return total


def build_rows(slips, company, year, month):
    """slips: salary_slip queryset (select_related employee_id)."""
    rows = []
    for slip in slips:
        e = slip.employee_id
        ded = deduction_for(e.pk, company, year, month)
        payable = (slip.net_pay or D('0')) - ded
        if payable <= 0:
            continue
        rows.append({
            'emp_code': e.employeecode, 'name': e.name, 'father_name': e.fathername,
            'department': getattr(e.departmentID, 'department_name', ''),
            'ifsc': (e.bank_ifsc or '').strip().upper(), 'account': e.bank_account,
            'address': (e.permanentaddress or e.temporaryaddress or '').replace('\n', ' ')[:60],
            'mobile': e.mobile, 'net_pay': rupee_up(payable),
        })
    return rows


def group_by_bank(rows):
    g = OrderedDict()
    for r in sorted(rows, key=lambda r: (r['ifsc'][:4], r['emp_code'])):
        g.setdefault(r['ifsc'][:4] or '----', []).append(r)
    return g


def _value(src, row, col, serial, ctx):
    if src == 'serial':
        return serial
    if src == 'fixed':
        return col.fixed_value
    if src == 'net_pay':
        return int(row['net_pay'])
    if src == 'pay_date':
        return ctx.get('pay_date', '')
    if src == 'debit_account':
        return ctx.get('debit_account', '')
    if src == 'narration':
        return ctx.get('narration', '')
    return row.get(src, '')


def render_file(fmt, rows, ctx=None):
    """Return (bytes, filename, content_type). fmt=None -> CSV fallback."""
    ctx = ctx or {}
    if fmt is None:
        headers = [h for h, _ in FALLBACK_COLUMNS]
        srcs = [s for _, s in FALLBACK_COLUMNS]
        cols = [type('C', (), {'fixed_value': '', 'width': None})() for _ in srcs]
        ftype, delim, has_header, total_row, name = 'CSV', ',', True, True, 'bank_payment'
    else:
        cl = list(fmt.columns.all())
        headers = [c.header for c in cl]
        srcs = [c.source for c in cl]
        cols = cl
        ftype, delim, has_header = fmt.file_type, (fmt.delimiter or ','), fmt.has_header
        total_row, name = fmt.add_total_row, f'bank_{fmt.ifsc_prefix}'

    table = [[_value(s, r, c, i, ctx) for s, c in zip(srcs, cols)] for i, r in enumerate(rows, 1)]
    total = sum(int(r['net_pay']) for r in rows)
    total_line = None
    if total_row and 'net_pay' in srcs:
        total_line = [''] * len(srcs)
        total_line[srcs.index('net_pay')] = total

    if ftype == 'XLSX':
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        if has_header:
            ws.append(headers)
        for r in table:
            ws.append(r)
        if total_line:
            ws.append(total_line)
        buf = io.BytesIO()
        wb.save(buf)
        return (buf.getvalue(), f'{name}.xlsx',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    allrows = ([headers] if has_header else []) + table + ([total_line] if total_line else [])
    if ftype == 'TXT':
        lines = []
        for r in allrows:
            parts = []
            for v, c in zip(r, cols):
                v = str(v)
                parts.append(v.ljust(c.width) if getattr(c, 'width', None) else v)
            lines.append(delim.join(parts))
        return '\r\n'.join(lines).encode('utf-8'), f'{name}.txt', 'text/plain'

    out = io.StringIO()
    csv.writer(out, delimiter=delim, lineterminator='\r\n').writerows(allrows)
    return out.getvalue().encode('utf-8'), f'{name}.csv', 'text/csv'


def seed_canara(company):
    """Canara layout from the owner's sample workbook."""
    fmt, created = BankFormat.objects.get_or_create(
        company=company, ifsc_prefix='CNRB',
        defaults=dict(bank_name='Canara Bank', file_type='XLSX', has_header=False,
                      add_total_row=True))
    if created:
        layout = [('serial', ''), ('emp_code', ''), ('name', ''), ('father_name', ''),
                  ('department', ''), ('ifsc', ''), ('account', ''), ('address', ''),
                  ('mobile', ''), ('net_pay', ''), ('fixed', 'B.T')]
        for i, (src, fixed) in enumerate(layout, 1):
            fmt.columns.create(position=i, header='', source=src, fixed_value=fixed)
    return fmt


def apply_month(company, year, month):
    """After payroll is paid: reduce balances once per month; close at zero.
    Idempotent: a deduction already applied for the month is skipped."""
    from datetime import date
    first = date(year, month, 1)
    done = 0
    for d in EmployeeDeduction.objects.filter(company=company, is_closed=False, is_paused=False):
        s = d.start_month
        if (s.year, s.month) > (year, month):
            continue
        if d.kind == 'ONCE' and (s.year, s.month) != (year, month):
            continue
        if d.last_applied == first:
            continue
        amt = d.amount_for_month()
        if amt <= 0:
            continue
        d.balance -= amt
        d.last_applied = first
        if d.balance <= 0:
            d.is_closed = True
        d.save()
        done += 1
    return done
