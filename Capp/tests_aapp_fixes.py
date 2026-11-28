"""Regression tests for the small fixes made inside Aapp (owner-approved)."""
from datetime import date
from decimal import Decimal as D

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase, override_settings

from Aapp.app import loans_advances as la
from Capp.tests_foundation import make_employee
from Capp.tests_masters import make_company


@override_settings(ROOT_URLCONF='Aapp.urls', ALLOWED_HOSTS=['*'])
class LoanEmployeeScopingTests(TestCase):
    """create_loan / alter_loan / create_advance / alter_advance accepted an employee of another
    company on POST (the queryset was restricted only on GET)."""

    def setUp(self):
        self.co = make_company('Mine', 'AAAAA1111A')
        self.co.plan = 'silver'; self.co.save()
        self.other = make_company('Theirs', 'BBBBB2222B')
        self.user = User.objects.create_superuser('assoc', 'a@x.com', 'pw')
        self.mine = make_employee(self.co, '1')
        self.theirs = make_employee(self.other, '2')

    def call(self, view, data, **kw):
        req = RequestFactory().post('/x/', data)
        req.user = self.user
        req.session = {'selected_company_id': self.co.pk}
        req.selected_company = self.co
        req._messages = FallbackStorage(req)
        return view(req, **kw)

    def data(self, emp, field):
        return {'employee': emp.pk, 'principal_amount': '1000', 'interest_rate_annual': '0',
                field: 'x', 'deduction_mode': 'instalments', 'number_of_instalments': '2',
                'deduction_start_month': '1', 'deduction_start_year': '2027'}

    def test_create_rejects_other_company_employee(self):
        r = self.call(la.create_loan, self.data(self.theirs, 'purpose'))
        self.assertEqual(r.status_code, 200)                      # form re-rendered with an error
        self.assertEqual(la.Loan.objects.count(), 0)
        r = self.call(la.create_advance, self.data(self.theirs, 'reason'))
        self.assertEqual(la.Advance.objects.count(), 0)

    def test_create_accepts_own_employee(self):
        self.assertEqual(self.call(la.create_loan, self.data(self.mine, 'purpose')).status_code, 302)
        self.assertEqual(self.call(la.create_advance, self.data(self.mine, 'reason')).status_code, 302)

    def test_alter_cannot_move_a_loan_to_another_company_employee(self):
        loan = la.Loan.objects.create(employee=self.mine, company=self.co, principal_amount=D('1000'),
                                      deduction_mode='instalments', number_of_instalments=2,
                                      deduction_start_month=1, deduction_start_year=2027)
        r = self.call(la.alter_loan, self.data(self.theirs, 'purpose'), loan_id=loan.loan_id)
        self.assertEqual(r.status_code, 200)
        loan.refresh_from_db(); self.assertEqual(loan.employee, self.mine)
        adv = la.Advance.objects.create(employee=self.mine, company=self.co, principal_amount=D('1000'),
                                        deduction_mode='instalments', number_of_instalments=2,
                                        deduction_start_month=1, deduction_start_year=2027)
        self.call(la.alter_advance, self.data(self.theirs, 'reason'), advance_id=adv.advance_id)
        adv.refresh_from_db(); self.assertEqual(adv.employee, self.mine)

    def test_alter_still_works_for_a_relieved_employees_loan(self):
        loan = la.Loan.objects.create(employee=self.mine, company=self.co, principal_amount=D('1000'),
                                      deduction_mode='instalments', number_of_instalments=2,
                                      deduction_start_month=1, deduction_start_year=2027)
        self.mine.is_working = False; self.mine.save()
        r = self.call(la.alter_loan, self.data(self.mine, 'purpose'), loan_id=loan.loan_id)
        self.assertEqual(r.status_code, 302)
