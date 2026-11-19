import unittest
from decimal import Decimal as D
from Capp.billing_engine import *


class SampleWorkbook(unittest.TestCase):
    """Owner's sample: Mohd Osama, Nov 2026, ESI on Basic as in his sheet."""
    line = EmployeeLine(basic=D('15221'), hra=D('2779'), att_bonus=D('2000'),
                        ot_hours=D('40'), ot_rate=D('150'),
                        advance_and_other=[('Advance', D('4600'))])

    def test_employee_basic_esi(self):
        r = compute_employee(self.line, esi_base='BASIC')
        self.assertEqual(r.epf_employee, D('1827'))
        self.assertEqual(r.epf_employer, D('1979'))
        self.assertEqual(r.esi_employee, D('114.1575'))
        self.assertEqual(r.esi_employer, D('494.6825'))
        self.assertEqual(r.net_pay, D('16023.8425'))
        self.assertEqual(r.payable, D('19423.8425'))
        self.assertEqual(r.bank_amount, D('19424'))
        self.assertEqual(r.esi_employee_challan, D('115'))
        self.assertEqual(r.esi_employer_challan, D('495'))

    def test_salary_invoice_matches_sheet(self):
        r = compute_employee(self.line, esi_base='BASIC')
        inv = salary_invoice([r], D('5'), D('18'))
        self.assertEqual(inv.service_charge, D('900'))
        self.assertEqual(inv.subtotal, D('23443.6825'))
        self.assertEqual(inv.total, D('27663.55'))

    def test_ot_invoice_matches_sheet(self):
        r = compute_employee(self.line)
        inv = ot_invoice([r], D('5'), D('18'))
        self.assertEqual(inv.pay, D('6000'))
        self.assertEqual(inv.sgst, D('283.5') * 2)   # 9% of 6300 = 567
        self.assertEqual(inv.total, D('7434.00'))

    def test_gross_base_and_ot_excluded(self):
        r = compute_employee(self.line, esi_base='GROSS')
        self.assertEqual(r.esi_employee, D('135'))       # 0.75% of 18000, no OT
        self.assertEqual(r.esi_employer, D('585'))

    def test_esi_ceiling(self):
        big = EmployeeLine(basic=D('20000'), hra=D('5000'))
        self.assertEqual(compute_employee(big).esi_employee, D('0'))


if __name__ == '__main__':
    unittest.main()
