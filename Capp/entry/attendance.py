"""
Capp/entry/attendance.py — monthly attendance entry and Excel import (AI-3: E2, E6).

Aapp stores ONE summary row per employee per month (working_days, work_pay, holidays,
leaves, overtime). Paid days = working_days + work_pay. With no row, payroll silently
assumes a full month, so the grid shows which employees have no entry yet.
Entry follows the lock rule D7 (Capp/entry/gates.py: entry_lock_reason).
"""
import base64
import calendar
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render

from Aapp.app.attandance import attendance
from Aapp.app.employee import employee
from Capp import importer
from Capp.access import capp_perm
from Capp.audit import log_action
from Capp.entry.gates import batch_for, entry_lock_reason
from Aapp.app.salary_processing import STANDARD_WORKING_HOURS, _calculate_overtime, _decimal_round
from Aapp.app.statutory_gates import get_company_gates
from Capp.masters import _style
from revolution.app.plan_gate import has_feature

D = Decimal
FIELDS = [  # name on the model, label, max
    ('working_days', 'Days worked', None), ('work_pay', 'Work-pay days', None),
    ('holidays', 'Holidays', None), ('casual_leaves', 'Casual leave', None),
    ('earned_leaves', 'Earned leave', None), ('sick_leaves', 'Sick leave', None),
    ('comp_leaves', 'Comp leave', None), ('overtime_hours', 'OT hours', D('300')),
]
LEAVES = ('casual_leaves', 'earned_leaves', 'sick_leaves', 'comp_leaves')
SESSION_KEY = 'capp_attendance_import'
MAX_BYTES = 2 * 1024 * 1024


def period(request):
    try:
        month = int(request.GET.get('month') or request.POST.get('month') or date.today().month)
        year = int(request.GET.get('year') or request.POST.get('year') or date.today().year)
    except ValueError:
        raise Http404('Bad period.')
    if not (1 <= month <= 12 and 2000 <= year <= 2100):
        raise Http404('Bad period.')
    return month, year


def monthly_basic(emp):
    """Basic the payroll bases overtime on: designation basic, or daily wage x 30."""
    d = emp.designationID
    return Decimal(str(d.dailywage)) * 30 if d.is_dailywage else Decimal(str(d.basicpay))


def ot_rates(emp):
    """(ordinary hourly rate, overtime hourly rate = double) from basic pay."""
    base = monthly_basic(emp)
    if base <= 0:
        return D('0'), D('0')
    ordinary = _decimal_round(base / D('30') / STANDARD_WORKING_HOURS)
    return ordinary, ordinary * 2


def ot_estimate(emp, hours):
    """What payroll will pay for these overtime hours (same function payroll uses)."""
    return _calculate_overtime(monthly_basic(emp), hours)


def _dec(raw):
    raw = ('' if raw is None else str(raw)).strip()
    if raw == '':
        return None
    try:
        v = D(raw)
    except InvalidOperation:
        raise ValueError('not a number')
    if v != v.quantize(D('0.01')):
        raise ValueError('at most 2 decimals')
    return v


OT_FIELDS = ('overtime_hours',)


def fields_for(company):
    """Overtime fields exist only on plans that include the `overtime` feature."""
    ok = has_feature(company, 'overtime')
    return [f for f in FIELDS if ok or f[0] not in OT_FIELDS]


def clean_row(raw, month, year, fields=None):
    """raw: {field: str}. -> (values dict | None when empty, [errors])."""
    dim, errors, vals = calendar.monthrange(year, month)[1], [], {}
    fields = fields or FIELDS
    for name, label, cap in fields:
        try:
            v = _dec(raw.get(name))
        except ValueError as e:
            errors.append(f'{label}: {e}')
            continue
        vals[name] = v
    if errors:                                           # a bad number is never "blank"
        return None, errors
    if all(v is None for v in vals.values()):
        return None, []                                   # blank row: no record
    vals = {k: (v if v is not None else D('0')) for k, v in vals.items()}
    for name, label, cap in fields:
        v = vals[name]
        if v < 0:
            errors.append(f'{label}: cannot be negative')
        if cap is not None and v > cap:
            errors.append(f'{label}: cannot exceed {cap}')
    if vals['working_days'] > dim:
        errors.append(f'Days worked: more than {dim} days in the month')
    if vals['working_days'] + vals['work_pay'] > dim:
        errors.append(f'Days worked + work-pay: more than {dim} days in the month')
    if vals['holidays'] > dim:
        errors.append(f'Holidays: more than {dim} days in the month')
    if sum(vals[k] for k in LEAVES) > vals['working_days']:
        errors.append('Leave days cannot exceed days worked (paid leave counts inside days worked)')
    return vals, errors


def save_row(company, emp, month, year, vals, user):
    obj, _ = attendance.objects.get_or_create(
        employee_id=emp, salary_month=month, salary_year=year,
        defaults={'emp_code': emp.employeecode, 'companyid': company, 'branchid': emp.branchID,
                  'created_by': user, 'is_bulk': True})
    for k, v in vals.items():
        setattr(obj, k, v)
    obj.emp_code, obj.companyid, obj.branchid, obj.updated_by = emp.employeecode, company, emp.branchID, user
    # Owner rule (= Aapp payroll): overtime is paid at DOUBLE the hourly rate from basic pay.
    # The statutory OT register (Form IV) reads these three columns; payroll itself recomputes.
    obj.ordinary_rate, obj.ot_rate = ot_rates(emp)
    obj.ot_wages_paid = _decimal_round(obj.overtime_hours * obj.ot_rate)
    obj.save()
    return obj


def _status_banner(request, company, month, year):
    batch = batch_for(company, month, year)
    lock = entry_lock_reason(company, request.capp_mode, month, year)
    note = ''
    if batch and not lock and batch.status == 'PROCESSED':
        note = 'This month is already processed. Reprocess the batch after changing attendance.'
    return batch, lock, note


@capp_perm('attendance.edit')
def capp_ent_att_grid(request):
    company = request.owned_company
    month, year = period(request)
    batch, lock, note = _status_banner(request, company, month, year)
    fields = fields_for(company)
    emps = list(employee.objects.filter(CompanyID=company, is_working=True).order_by('employeecode'))
    existing = {a.employee_id_id: a for a in attendance.objects.filter(
        companyid=company, salary_month=month, salary_year=year)}
    posted = {}
    errors = {}

    if request.method == 'POST':
        if lock:
            messages.error(request, lock)
            return redirect(f"{request.path}?month={month}&year={year}")
        clean, saved = [], 0
        for e in emps:
            raw = {n: request.POST.get(f'{n}_{e.pk}', '') for n, _, _ in fields}
            posted[e.pk] = raw
            vals, errs = clean_row(raw, month, year, fields)
            if errs:
                errors[e.pk] = errs
            elif vals is not None:
                clean.append((e, vals))
        if errors:
            messages.error(request, f'{len(errors)} row(s) have problems. Nothing was saved.')
        else:
            for e, vals in clean:
                save_row(company, e, month, year, vals, request.user)
                saved += 1
            log_action(request, 'attendance_save', None, f'{month:02d}/{year}: {saved} rows')
            messages.success(request, f'Attendance saved for {saved} employee(s).')
            return redirect(f"{request.path}?month={month}&year={year}")

    rows = []
    for e in emps:
        rec = existing.get(e.pk)
        vals = posted.get(e.pk) or ({n: ('' if rec is None else f'{getattr(rec, n):g}')
                                     for n, _, _ in fields})
        rows.append({'emp': e, 'cells': [{'name': n, 'value': vals.get(n, '')} for n, _, _ in fields],
                     'entered': rec is not None, 'errors': errors.get(e.pk, [])})
    ot_on = any(n in OT_FIELDS for n, _, _ in fields)
    return render(request, 'Capp/entry/attendance_grid.html', {
        'ot_on': ot_on, 'no_shop_act': ot_on and not get_company_gates(company)['shop_act'],
        'page_title': 'Attendance Entry', 'month': month, 'year': year, 'months': list(range(1, 13)),
        'columns': [(n, l) for n, l, _ in fields], 'rows': rows, 'lock': lock, 'note': note,
        'missing': sum(1 for r in rows if not r['entered']),
        'days_in_month': calendar.monthrange(year, month)[1]})


# ── Excel import (summary columns of the owner's ATT sheet) ──────────────────

ALIASES = {
    'code': ['idno', 'empid', 'employeeid', 'empcode'],
    'days': ['att', 'attendance', 'daysworked', 'present'],
    'total_days': ['tatt'],
    'holidays': ['h', 'holidays', 'holiday'],
    'ot': ['ot', 'overtime', 'overtimehours'],
}


class AttendanceImportForm(forms.Form):
    file = forms.FileField(label='Excel file (.xls or .xlsx)')
    month = forms.IntegerField(min_value=1, max_value=12)
    year = forms.IntegerField(min_value=2000, max_value=2100)
    use_ot = forms.BooleanField(required=False, initial=True,
                                label='Also import the OT column as overtime hours',
                                help_text='The OT column is read as hours (owner confirmed). '
                                          'Ignored on plans without the overtime feature.')

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields['month'].initial = date.today().month
        self.fields['year'].initial = date.today().year
        _style(self)

    def clean_file(self):
        f = self.cleaned_data['file']
        if not f.name.lower().endswith(('.xls', '.xlsx')):
            raise forms.ValidationError('Upload an .xls or .xlsx file.')
        if f.size > MAX_BYTES:
            raise forms.ValidationError('File is larger than 2 MB.')
        return f


def _find_sheet(sheets):
    best = None
    for name, rows in sheets.items():
        for i, row in enumerate(rows[:6]):
            cols = {}
            for j, h in enumerate(row):
                n = importer._norm(h) if h is not None else ''
                for field, names in ALIASES.items():
                    if n in names and field not in cols:
                        cols[field] = j
            if 'code' in cols and ('days' in cols or 'total_days' in cols):
                score = (name.strip().lower() == 'att', len(cols))
                if best is None or score > best[0]:
                    best = (score, name, i, cols)
    return best[1:] if best else None


def parse_attendance(sheets, company, month, year, use_ot):
    found = _find_sheet(sheets)
    if not found:
        return [], ['No attendance sheet found (needs ID No. and ATT or TATT columns).']
    name, hdr, cols = found
    notes = [f'Read sheet "{name}".']
    if use_ot and not has_feature(company, 'overtime'):
        notes.append('The OT column was ignored: your plan has no overtime feature.')
    by_code = {e.employeecode: e for e in employee.objects.filter(CompanyID=company)}
    out, seen = [], set()
    for idx, r in enumerate(sheets[name][hdr + 1:], start=hdr + 2):
        def cell(f):
            j = cols.get(f)
            return r[j] if j is not None and j < len(r) else None
        code = importer.to_text(cell('code'))[0]
        if not code:
            continue
        raw = {'working_days': importer.to_text(cell('days') if 'days' in cols else cell('total_days'))[0],
               'holidays': importer.to_text(cell('holidays'))[0]}
        if use_ot and has_feature(company, 'overtime'):
            raw['overtime_hours'] = importer.to_text(cell('ot'))[0]
        vals, issues = clean_row(raw, month, year, fields_for(company))
        emp = by_code.get(code)
        if emp is None:
            issues.append('ID not found in this company.')
        elif not emp.is_working:
            issues.append('Employee is relieved.')
        if code in seen:
            issues.append('Duplicate ID in the sheet.')
        seen.add(code)
        if vals is None and not issues:
            issues.append('No attendance values in the row.')
        est = None
        if emp is not None and vals and vals.get('overtime_hours'):
            est = ot_estimate(emp, vals['overtime_hours'])        # shown so a wrong OT column is obvious
        out.append({'row': idx, 'code': code, 'name': emp.name if emp else '', 'issues': issues,
                    'vals': {k: str(v) for k, v in (vals or {}).items()}, 'emp_pk': emp.pk if emp else None,
                    'ot_estimate': est})
    return out, notes


@capp_perm('attendance.edit')
def capp_ent_att_import(request):
    company = request.owned_company
    form = AttendanceImportForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and 'confirm' in request.POST:
        saved = request.session.get(SESSION_KEY)
        if not saved:
            messages.error(request, 'Import expired. Upload the file again.')
            return redirect('capp_ent_att_import')
        month, year = saved['month'], saved['year']
        lock = entry_lock_reason(company, request.capp_mode, month, year)
        if lock:
            messages.error(request, lock)
            return redirect('capp_ent_att_import')
        rows, _ = parse_attendance(importer.read_sheets(io.BytesIO(base64.b64decode(saved['b64'])),
                                                        saved['name']), company, month, year, saved['use_ot'])
        done = 0
        for r in rows:
            if r['issues']:
                continue
            emp = employee.objects.filter(pk=r['emp_pk'], CompanyID=company, is_working=True).first()
            vals, errs = clean_row({k: v for k, v in r['vals'].items()}, month, year, fields_for(company))
            if emp and vals and not errs:
                save_row(company, emp, month, year, vals, request.user)
                done += 1
        request.session.pop(SESSION_KEY, None)
        log_action(request, 'attendance_import', None, f'{month:02d}/{year}: {done} rows')
        messages.success(request, f'Attendance imported for {done} employee(s).')
        return redirect(f'/entry/attendance/?month={month}&year={year}')

    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        lock = entry_lock_reason(company, request.capp_mode, d['month'], d['year'])
        if lock:
            form.add_error(None, lock)
        else:
            f = d['file']
            raw = f.read()
            try:
                rows, notes = parse_attendance(importer.read_sheets(io.BytesIO(raw), f.name), company,
                                               d['month'], d['year'], d['use_ot'])
            except Exception as e:
                form.add_error('file', f'Could not read the workbook: {e}')
            else:
                request.session[SESSION_KEY] = {'name': f.name, 'b64': base64.b64encode(raw).decode(),
                                                'month': d['month'], 'year': d['year'], 'use_ot': d['use_ot']}
                ok = sum(1 for r in rows if not r['issues'])
                return render(request, 'Capp/entry/attendance_import_preview.html', {
                    'page_title': 'Attendance Import Preview', 'rows': rows, 'notes': notes,
                    'ok': ok, 'bad': len(rows) - ok, 'month': d['month'], 'year': d['year']})
    return render(request, 'Capp/masters/form.html', {
        'form': form, 'page_title': 'Import Attendance from Excel', 'multipart': True,
        'cancel_url': 'capp_ent_att_grid',
        'locked': [('Reads', 'ATT sheet: ID No., ATT (or TATT), H, optional OT'), ('Saves', 'one monthly row per employee')]})
