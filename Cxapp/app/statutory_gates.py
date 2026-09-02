"""
Cxapp/app/statutory_gates.py
==============================
Company-level statutory registration gates for the Cxapp portal.

Not a reimplementation — reads the SAME company_statury table Aapp uses
(Sapp.app.company.company_statury). Same rule everywhere in this codebase:
no registration on file, no deduction. Single source of truth stays in
one place; this module is just the Cxapp-facing import point so
Cxapp/app/employee.py doesn't need to know Sapp's internals directly.

Gates:
    shop_act    -> overtime, wages register, fines, leave balances
    epf         -> employee + employer EPF deduction
    esi         -> employee + employer ESI deduction
    labour      -> employee + employer Labour Welfare Fund deduction
    income_tax  -> income tax (TDS) deduction — requires company TAN
    pt          -> Professional Tax deduction — requires company PT number
                   AND an active PT slab on file for the company's state
                   (see Sapp.app.professional_tax.get_pt_amount)
"""

from Sapp.app.company import company_statury


def get_company_gates(company) -> dict:
    """
    Returns a dict of booleans for the given Company instance:
        {'shop_act': bool, 'epf': bool, 'esi': bool,
         'labour': bool, 'income_tax': bool, 'pt': bool}

    A gate is True only if the corresponding registration number/field
    is present and non-empty. Missing company or missing company_statury
    row means every gate is False (fail closed, not open) — identical
    behaviour to Aapp.app.statutory_gates.get_company_gates.
    """
    gates = {
        'shop_act': False,
        'epf': False,
        'esi': False,
        'labour': False,
        'income_tax': False,
        'pt': False,
    }
    if company is None:
        return gates

    gates['income_tax'] = bool(getattr(company, 'tan', ''))

    statury = company_statury.objects.filter(company=company).first()
    if statury:
        gates['shop_act'] = bool(statury.shop_act)
        gates['epf'] = bool(statury.epfo)
        gates['esi'] = bool(statury.esic)
        gates['labour'] = bool(statury.labour)
        gates['pt'] = bool(statury.pt_number)

    return gates


def gate_required(gates, gate_name, feature_name=''):
    """
    Returns (bool, message) — no exception raised, so callers decide
    whether to block silently, show a message, or zero out a value.
    """
    if gates.get(gate_name):
        return True, ''
    label = f' for {feature_name}' if feature_name else ''
    gate_labels = {
        'shop_act': 'Shop & Establishments Act',
        'epf': 'EPF',
        'esi': 'ESI',
        'labour': 'Labour Welfare Fund',
        'income_tax': 'Income Tax (TAN)',
        'pt': 'Professional Tax',
    }
    name = gate_labels.get(gate_name, gate_name)
    return False, f'{name} registration not on file{label} — action blocked.'
