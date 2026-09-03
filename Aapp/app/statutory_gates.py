"""
Single source of truth for company-level statutory registration gates.

Every deduction/entitlement that depends on the COMPANY being registered
under an act (as opposed to the employee being enrolled) must be checked
through this module. Do not re-implement these checks elsewhere — if the
gate logic needs to change, it changes here once.

Gates:
    shop_act    -> overtime, wages register, fines, leave balances
                   (annual/earned, sick, casual)
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
    row means every gate is False (fail closed, not open).
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


def shop_act_required(gates, feature_name=''):
    """
    Raises no exception — returns (bool, message) so callers can decide
    whether to block silently, show a message, or zero out a field.
    Kept simple and explicit rather than raising, since these checks run
    inside both view code (wants a message) and calculation code
    (wants a silent zero/skip).
    """
    if gates.get('shop_act'):
        return True, ''
    label = f' for {feature_name}' if feature_name else ''
    return False, f'Shop & Establishments Act registration not on file{label} — action blocked.'
