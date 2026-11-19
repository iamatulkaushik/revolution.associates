"""
Capp/billing_engine.py
======================
Pure-Python billing maths for the contractor billing module (no DB).

Rules (from owner's sample workbook + decisions):
- Bill keeps full precision; the invoice total is rounded once, half-up, to paisa.
- Overtime is never part of ESI wages. OT is billed as a separate invoice.
- ESI base is selectable per client: BASIC or GROSS (earned, excluding OT).
- ESIC rounding (round up to whole rupee) is for the challan file only.
- Bank payout is always rounded UP to the whole rupee.
- EPF rounds to the nearest rupee (as in the owner's sheet).
"""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

D = Decimal
PAISA = D('0.01')
RUPEE = D('1')


def paisa(x):
    return D(x).quantize(PAISA, rounding=ROUND_HALF_UP)


def rupee_nearest(x):
    return D(x).quantize(RUPEE, rounding=ROUND_HALF_UP)


def rupee_up(x):
    return D(x).quantize(RUPEE, rounding=ROUND_CEILING)


@dataclass(frozen=True)
class Rates:
    epf_employee: Decimal = D('0.12')
    epf_employer: Decimal = D('0.13')
    esi_employee: Decimal = D('0.0075')
    esi_employer: Decimal = D('0.0325')
    esi_wage_ceiling: Decimal = D('21000')   # gross per month, excl. OT
    lwf_employee: Decimal = D('35')          # Haryana, Jan 2026
    lwf_employer: Decimal = D('70')
    epf_wage_cap: Decimal | None = None      # None = no cap (owner's sheet)


@dataclass
class EmployeeLine:
    basic: Decimal
    hra: Decimal = D('0')
    att_bonus: Decimal = D('0')
    ot_hours: Decimal = D('0')
    ot_rate: Decimal = D('0')
    ot_amount: Decimal | None = None      # exact OT pay from payroll; overrides hours x rate
    advance_and_other: list = field(default_factory=list)  # [(title, amount)]


@dataclass
class EmployeeResult:
    gross: Decimal
    epf_employee: Decimal
    epf_employer: Decimal
    esi_employee: Decimal
    esi_employer: Decimal
    lwf_employee: Decimal
    lwf_employer: Decimal
    statutory_deduction: Decimal
    net_pay: Decimal            # gross - statutory deductions
    att_bonus: Decimal
    ot_pay: Decimal
    other_deductions: Decimal
    payable: Decimal            # net + bonus + OT - other deductions (full precision)
    bank_amount: Decimal        # payable rounded UP to whole rupee
    esi_employee_challan: Decimal   # rounded up, challan only
    esi_employer_challan: Decimal


def compute_employee(line: EmployeeLine, esi_base: str = 'GROSS',
                     rates: Rates = Rates(), epf: bool = True, esi: bool = True,
                     lwf: bool = True) -> EmployeeResult:
    """epf/esi/lwf: statutory gates. False (no registration) means no charge."""
    gross = line.basic + line.hra
    epf_wage = line.basic if rates.epf_wage_cap is None else min(line.basic, rates.epf_wage_cap)
    epf_ee = rupee_nearest(epf_wage * rates.epf_employee) if epf else D('0')
    epf_er = rupee_nearest(epf_wage * rates.epf_employer) if epf else D('0')

    esi_applicable = esi and gross <= rates.esi_wage_ceiling      # OT never counted
    esi_wage = (line.basic if esi_base == 'BASIC' else gross) if esi_applicable else D('0')
    esi_ee = esi_wage * rates.esi_employee
    esi_er = esi_wage * rates.esi_employer

    lw_ee = rates.lwf_employee if lwf else D('0')
    lw_er = rates.lwf_employer if lwf else D('0')
    statutory = epf_ee + esi_ee + lw_ee
    net = gross - statutory
    ot_pay = line.ot_amount if line.ot_amount is not None else line.ot_hours * line.ot_rate
    other = sum((a for _, a in line.advance_and_other), D('0'))
    payable = net + line.att_bonus + ot_pay - other

    return EmployeeResult(
        gross=gross, epf_employee=epf_ee, epf_employer=epf_er,
        esi_employee=esi_ee, esi_employer=esi_er,
        lwf_employee=lw_ee, lwf_employer=lw_er,
        statutory_deduction=statutory, net_pay=net, att_bonus=line.att_bonus,
        ot_pay=ot_pay, other_deductions=other, payable=payable,
        bank_amount=rupee_up(payable),
        esi_employee_challan=rupee_up(esi_ee), esi_employer_challan=rupee_up(esi_er),
    )


@dataclass
class Invoice:
    pay: Decimal
    employer_costs: dict
    service_charge: Decimal
    subtotal: Decimal
    sgst: Decimal
    cgst: Decimal
    extra_charges: Decimal
    total: Decimal              # rounded once, half-up, to paisa


def salary_invoice(results, service_charge_pct, gst_pct, extra_charges=D('0')) -> Invoice:
    pay = sum((r.gross for r in results), D('0'))
    costs = {
        'epf_employer': sum((r.epf_employer for r in results), D('0')),
        'esi_employer': sum((r.esi_employer for r in results), D('0')),
        'lwf': sum((r.lwf_employer for r in results), D('0')),
        'att_bonus': sum((r.att_bonus for r in results), D('0')),
    }
    sc = pay * service_charge_pct / 100
    subtotal = pay + sum(costs.values()) + sc
    half = gst_pct / 2 / 100
    gst_each = subtotal * half
    total = subtotal + 2 * gst_each + extra_charges
    return Invoice(pay, costs, sc, subtotal, gst_each, gst_each, extra_charges, paisa(total))


def ot_invoice(results, service_charge_pct, gst_pct, extra_charges=D('0')) -> Invoice:
    """OT only: no EPF, no ESI."""
    pay = sum((r.ot_pay for r in results), D('0'))
    sc = pay * service_charge_pct / 100
    subtotal = pay + sc
    gst_each = subtotal * (gst_pct / 2 / 100)
    total = subtotal + 2 * gst_each + extra_charges
    return Invoice(pay, {}, sc, subtotal, gst_each, gst_each, extra_charges, paisa(total))
