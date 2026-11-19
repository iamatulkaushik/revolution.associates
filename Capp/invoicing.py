"""
Capp/invoicing.py — build an Invoice (salary or OT) from payroll slips.

Slip mapping (Aapp.salary_slip):
  engine basic = basic_earned + da_earned   (Wage Code base)
  engine hra   = other fixed earnings = gross - OT - bonus - basic - da
  att_bonus    = bonus_amount ; OT = overtime_amount (exact)
Statutory gates (EPF/ESI/LWF) come from get_company_gates — no registration,
no charge.
"""
from datetime import date
from decimal import Decimal as D

from django.db import transaction
from django.db.models import Max

from Aapp.app.salary_processing import salary_slip
from Aapp.app.statutory_gates import get_company_gates
from Capp.billing_engine import (EmployeeLine, compute_employee, ot_invoice, salary_invoice)
from Capp.billing_models import ClientEmployee, Invoice, InvoiceLine


class InvoiceError(Exception):
    pass


def financial_year(d):
    y = d.year if d.month >= 4 else d.year - 1
    return f'{y}-{str(y + 1)[2:]}'


def _next_seq(company, fy):
    last = Invoice.objects.filter(company=company, fy=fy).aggregate(m=Max('seq'))['m']
    return (last or 0) + 1


def generate_invoice(company, client, kind, year, month, user='', extra_label='',
                     extra_charges=D('0'), invoice_date=None):
    invoice_date = invoice_date or date.today()
    if Invoice.objects.filter(client=client, kind=kind, year=year, month=month,
                              status__in=['DRAFT', 'ISSUED']).exists():
        raise InvoiceError('An invoice for this client, month and type already exists.')

    emp_ids = ClientEmployee.objects.filter(company=company, client=client) \
        .values_list('employee_id', flat=True)
    slips = list(salary_slip.objects.filter(
        company_id=company, employee_id__in=list(emp_ids),
        processing_id__month=month, processing_id__year=year,
    ).select_related('employee_id', 'designation_id').order_by('employee_id__employeecode'))
    if not slips:
        raise InvoiceError('No salary slips for the employees mapped to this client.')

    gates = get_company_gates(company)
    results = []
    for sl in slips:
        base = sl.basic_earned + sl.da_earned
        fixed_gross = sl.gross_earnings - sl.overtime_amount - sl.bonus_amount
        line = EmployeeLine(basic=base, hra=fixed_gross - base, att_bonus=sl.bonus_amount,
                            ot_hours=sl.overtime_hours, ot_amount=sl.overtime_amount)
        results.append((sl, compute_employee(line, esi_base=client.esi_base, epf=gates['epf'],
                                             esi=gates['esi'], lwf=gates['labour'])))
    res = [r for _, r in results]

    if kind == 'OT':
        if not any(r.ot_pay > 0 for r in res):
            raise InvoiceError('No overtime in this month for the mapped employees.')
        inv = ot_invoice(res, client.service_charge_pct, client.gst_pct, D(extra_charges))
    else:
        inv = salary_invoice(res, client.service_charge_pct, client.gst_pct, D(extra_charges))

    fy = financial_year(invoice_date)
    with transaction.atomic():
        seq = _next_seq(company, fy)
        obj = Invoice.objects.create(
            company=company, client=client, kind=kind, year=year, month=month, fy=fy, seq=seq,
            number=f'INV/{fy}/{seq:04d}', invoice_date=invoice_date, esi_base=client.esi_base,
            service_charge_pct=client.service_charge_pct, gst_pct=client.gst_pct,
            pay=inv.pay, epf_employer=inv.employer_costs.get('epf_employer', 0),
            esi_employer=inv.employer_costs.get('esi_employer', 0),
            lwf=inv.employer_costs.get('lwf', 0), att_bonus=inv.employer_costs.get('att_bonus', 0),
            service_charge=inv.service_charge, subtotal=inv.subtotal, sgst=inv.sgst, cgst=inv.cgst,
            extra_label=extra_label, extra_charges=inv.extra_charges, total=inv.total,
            created_by=user)
        for sl, r in results:
            if kind == 'OT' and r.ot_pay <= 0:
                continue
            InvoiceLine.objects.create(
                invoice=obj, employee=sl.employee_id, emp_code=sl.employee_id.employeecode,
                name=sl.employee_id.name,
                designation=getattr(sl.designation_id, 'designationname', ''),
                paid_days=sl.paid_days, ot_hours=sl.overtime_hours,
                gross=0 if kind == 'OT' else r.gross,
                epf_employer=0 if kind == 'OT' else r.epf_employer,
                esi_employer=0 if kind == 'OT' else r.esi_employer,
                lwf=0 if kind == 'OT' else r.lwf_employer,
                att_bonus=0 if kind == 'OT' else r.att_bonus, ot_pay=r.ot_pay)
    return obj
