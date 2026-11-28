"""
Capp/importer.py — import the owner's Excel employee master.

Reads .xls / .xlsx. The DATA sheet (headers found by name, not position)
provides the employee master; any other sheet that has "ID No." and "IFSC"
columns (bank sheets) supplies missing IFSC / mobile / address by ID.

parse() is pure (no DB writes). apply() writes inside per-row savepoints.
"""
import io
import re
from datetime import date, datetime
from decimal import Decimal

from django.db import IntegrityError, transaction

from Aapp.app.branch_department import department
from Aapp.app.designation import designation
from Aapp.app.employee import employee
from Capp.billing_models import ClientEmployee

ALIASES = {
    'code': ['idno', 'empid', 'employeeid', 'empcode'],
    'name': ['name', 'employeename'],
    'father': ['fathersname', 'fathername'],
    'dob': ['datofbirth', 'dateofbirth', 'dob'],
    'department': ['department', 'dept'],
    'designation': ['designation'],
    'account': ['acno', 'accountno', 'accountnumber'],
    'aadhaar': ['aadhaarno', 'aadharno', 'aadhaar', 'aadhar'],
    'doj': ['doj', 'dateofjoining'],
    'mobile': ['mno', 'mobile', 'mobileno'],
    'esi': ['esi', 'esino', 'esic'],
    'uan': ['uan'],
    'basic': ['basic'],
    'hra': ['hra'],
    'other': ['otheralow', 'otherallowance', 'other'],
    'temp_addr': ['temparoryaddress', 'temporaryaddress'],
    'perm_addr': ['permanentaddress'],
    'ifsc': ['ifsc'],
    'address': ['adress', 'address'],
}
GENDERS = ('Male', 'Female', 'Other')


def _norm(h):
    return re.sub(r'[^a-z0-9]', '', str(h).lower())


def read_sheets(fileobj, filename):
    """-> {sheet_name: [[cell, ...], ...]} with dates already as datetime."""
    data = fileobj.read()
    if filename.lower().endswith('.xls'):
        import xlrd
        wb = xlrd.open_workbook(file_contents=data)
        out = {}
        for sh in wb.sheets():
            rows = []
            for r in range(sh.nrows):
                row = []
                for c in range(sh.ncols):
                    cell = sh.cell(r, c)
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        row.append(xlrd.xldate.xldate_as_datetime(cell.value, wb.datemode))
                    elif cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                        row.append(None)
                    else:
                        row.append(cell.value)
                rows.append(row)
            out[sh.name] = rows
        return out
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    return {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}


def _header_map(rows, need):
    """Find the header row (within the first 6) containing all `need` fields."""
    for i, row in enumerate(rows[:6]):
        cols = {}
        for j, h in enumerate(row):
            n = _norm(h) if h is not None else ''
            for field, names in ALIASES.items():
                if n in names and field not in cols:
                    cols[field] = j
        if all(f in cols for f in need):
            return i, cols
    return None, None


def to_text(v):
    """Excel cell -> clean text. Returns (text, precision_warning)."""
    if v is None:
        return '', False
    if isinstance(v, float):
        if v == int(v):
            return str(int(v)), abs(v) >= 1e15       # floats lose digits past 15
        return str(v), False
    return re.sub(r'\s+', ' ', str(v)).strip(), False


def to_date(v):
    if v in (None, ''):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for fmt in ('%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d.%m.%y', '%d/%m/%y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _num(v):
    try:
        return Decimal(str(v)) if v not in (None, '') else Decimal('0')
    except Exception:
        return Decimal('0')


def parse(sheets, company):
    """-> (rows, notes). rows: list of dicts with 'issues' and JSON-safe 'data'."""
    notes = []
    master = None
    for name, rows in sheets.items():
        if name.strip().lower() == 'data':
            master = name
            break
    if master is None:
        for name, rows in sheets.items():
            if _header_map(rows, ('code', 'name', 'aadhaar'))[0] is not None:
                master = name
                break
    if master is None:
        return [], ['No employee sheet found (needs ID No., Name, Aadhaar columns).']
    hdr, cols = _header_map(sheets[master], ('code', 'name'))
    if hdr is None:
        return [], [f'Sheet "{master}": header row with ID No. and Name not found.']

    # supplement from bank-type sheets
    extra = {}
    for name, rows in sheets.items():
        if name == master:
            continue
        h2, c2 = _header_map(rows, ('code', 'ifsc'))
        if h2 is None:
            continue
        for r in rows[h2 + 1:]:
            code, _ = to_text(r[c2['code']]) if c2['code'] < len(r) else ('', False)
            if code:
                e = extra.setdefault(code, {})
                for f in ('ifsc', 'mobile', 'address'):
                    if f in c2 and c2[f] < len(r) and f not in e:
                        t, _ = to_text(r[c2[f]])
                        if t:
                            e[f] = t.upper() if f == 'ifsc' else t
        notes.append(f'IFSC/mobile/address also read from sheet "{name}".')

    from revolution.app.plan_limits import remaining
    room = remaining(company)                  # None = unlimited
    out, seen = [], set()
    for idx, r in enumerate(sheets[master][hdr + 1:], start=hdr + 2):
        def cell(f):
            j = cols.get(f)
            return r[j] if j is not None and j < len(r) else None
        code, _ = to_text(cell('code'))
        name_ = to_text(cell('name'))[0]
        if not code or not name_:
            continue                                    # blank / total rows
        issues = []
        d = {'code': code, 'name': name_.upper(), 'father': to_text(cell('father'))[0].upper()}
        for f in ('account', 'aadhaar', 'mobile', 'esi', 'uan'):
            t, warn = to_text(cell(f))
            if warn:
                issues.append(f'{f}: number too long for Excel; save the column as Text and retry.')
            d[f] = t
        for f in ('department', 'designation'):
            d[f] = to_text(cell(f))[0].upper()
        d['dob'] = to_date(cell('dob'))
        d['doj'] = to_date(cell('doj'))
        for f in ('temp_addr', 'perm_addr'):
            d[f] = to_text(cell(f))[0].upper()
        d['basic'], d['hra'], d['other'] = _num(cell('basic')), _num(cell('hra')), _num(cell('other'))
        ex = extra.get(code, {})
        d['ifsc'] = (to_text(cell('ifsc'))[0].upper() if 'ifsc' in cols else '') or ex.get('ifsc', '')
        d['mobile'] = d['mobile'] or ex.get('mobile', '')
        if not d['temp_addr']:
            d['temp_addr'] = ex.get('address', '').upper() or d['perm_addr']

        if code in seen:
            issues.append('Duplicate ID in the sheet.')
        seen.add(code)
        for f, label in (('doj', 'Date of joining'), ('dob', 'Date of birth')):
            if not d[f]:
                issues.append(f'{label} missing or unreadable.')
        if not (d['aadhaar'].isdigit() and len(d['aadhaar']) == 12):
            issues.append('Aadhaar must be 12 digits.')
        if not (d['mobile'].isdigit() and len(d['mobile']) == 10):
            issues.append('Mobile must be 10 digits.')
        if not (d['account'].isdigit() and 9 <= len(d['account']) <= 18):
            issues.append('Account number must be 9-18 digits.')
        if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', d['ifsc']):
            issues.append('IFSC missing or invalid (add an IFSC column or a bank sheet).')
        if not d['designation'] or not d['department']:
            issues.append('Department and designation are required.')
        if not d['temp_addr']:
            issues.append('Address missing.')

        # database conflicts
        ex_emp = employee.objects.filter(employeecode=code).first()
        action = 'create'
        if ex_emp:
            if ex_emp.CompanyID_id != company.pk:
                issues.append('ID already used by another company.')
            action = 'update'
        for field, val, label in (('aadhar_number', d['aadhaar'], 'Aadhaar'),
                                  ('bank_account', d['account'], 'Account'),
                                  ('mobile', d['mobile'], 'Mobile')):
            if val and employee.objects.filter(**{field: val}).exclude(
                    pk=getattr(ex_emp, 'pk', None)).exists():
                issues.append(f'{label} already registered to another employee.')
        # Plan limit: only NEW employees use up room; updates are always allowed.
        if action == 'create' and not issues and room is not None:
            if room <= 0:
                issues.append('Plan limit reached: upgrade the plan to add more employees.')
            else:
                room -= 1
        out.append({'row': idx, 'code': code, 'name': d['name'], 'action': action,
                    'issues': issues, 'data': d})
    return out, notes


def apply(rows, company, branch, user, gender='Male', client=None):
    """Write rows that have no issues. -> dict of counts."""
    created = updated = skipped = 0
    for r in rows:
        if r['issues']:
            skipped += 1
            continue
        d = r['data']
        try:
            with transaction.atomic():
                dept, _ = department.objects.get_or_create(
                    companyid=company, branch=branch, department_name__iexact=d['department'],
                    defaults={'department_name': d['department'], 'created_by': user})
                desig = designation.objects.filter(
                    company=company, designationname__iexact=d['designation'],
                    is_deleted=False).first()
                if not desig:
                    zero = {f.name: Decimal('0') for f in designation._meta.fields
                            if f.get_internal_type() == 'DecimalField' and not f.has_default()}
                    zero.update(basicpay=d['basic'], hra=d['hra'], other1=d['other'])
                    desig = designation.objects.create(
                        company=company, designationname=d['designation'],
                        created_by=user.username, updated_by=user.username, **zero)
                vals = dict(name=d['name'], fathername=d['father'], dateofbirth=d['dob'],
                            dateofjoining=d['doj'], mobile=d['mobile'],
                            aadhar_number=d['aadhaar'], aadhar_name=d['name'],
                            bank_name=d['name'], bank_account=d['account'], bank_ifsc=d['ifsc'],
                            esic_number=d['esi'][:10], uan_number=d['uan'],
                            temporaryaddress=d['temp_addr'], permanentaddress=d['perm_addr'],
                            designationID=desig, departmentID=dept)
                emp = employee.objects.filter(employeecode=d['code'], CompanyID=company).first()
                if emp:
                    for k, v in vals.items():
                        setattr(emp, k, v)
                    emp.save()
                    updated += 1
                else:
                    emp = employee.objects.create(employeecode=d['code'], gender=gender, email='',
                                                  branchID=branch, CompanyID=company, **vals)
                    created += 1
                if client:
                    ClientEmployee.objects.update_or_create(
                        employee=emp, defaults={'company': company, 'client': client})
        except IntegrityError as e:
            skipped += 1
            r['issues'].append(f'Database error: {e}')
    return {'created': created, 'updated': updated, 'skipped': skipped}
