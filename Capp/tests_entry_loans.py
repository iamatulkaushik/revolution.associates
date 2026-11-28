"""E3 loans and advances entry: plan gate, scoping, lock rule, golden parity with Aapp."""
from decimal import Decimal as D

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.loans_advances import Advance, Loan, LoanForm
from Aapp.app.salary_processing import salary_processing
from Capp.foundation.models import CappAuditLog, CompanyOperator
from Capp.models import CompanyOwnerProfile
from Capp.tests_foundation import make_employee
from Capp.tests_masters import make_company

HOST = {'HTTP_HOST': 'capp.localhost'}


@override_settings(ALLOWED_HOSTS=['*'])
class LoanEntryTests(TestCase):
    def setUp(self):
        self.co = make_company('JSK', 'AAAAA1111A')
        self.co.plan = 'silver'; self.co.save()
        self.other = make_company('Other', 'BBBBB2222B')
        self.owner = User.objects.create_user('owner', password='pw-Strong-1')
        CompanyOwnerProfile.objects.create(user=self.owner, company=self.co)
        self.client.login(username='owner', password='pw-Strong-1')
        self.emp = make_employee(self.co, '1')

    def data(self, **kw):
        d = {'employee': self.emp.pk, 'principal_amount': '12000', 'interest_rate_annual': '0',
             'purpose': 'Medical', 'deduction_mode': 'instalments', 'number_of_instalments': '6',
             'deduction_start_month': '12', 'deduction_start_year': '2026'}
        d.update(kw)
        return d

    def add(self, kind='loans', **kw):
        d = self.data(**kw)
        if kind == 'advances':
            d['reason'] = d.pop('purpose')
        return self.client.post(f'/entry/{kind}/add/', d, **HOST)

    def test_loan_created_and_schedule_matches_aapp_form(self):
        self.assertEqual(self.add().status_code, 302)
        loan = Loan.objects.get()
        self.assertEqual((loan.company, loan.created_by, loan.employee), (self.co, 'owner', self.emp))
        aapp_form = LoanForm(self.data())                         # Aapp's own form, same inputs
        self.assertTrue(aapp_form.is_valid(), aapp_form.errors)
        theirs = aapp_form.save(commit=False)
        theirs.company = self.co
        self.assertEqual(loan.amortization_schedule(), theirs.amortization_schedule())    # golden
        self.assertEqual(len(loan.amortization_schedule()), 6)
        self.assertTrue(CappAuditLog.objects.filter(action='create', model='Loan').exists())

    def test_advance_with_interest_and_fixed_amount(self):
        r = self.add('advances', deduction_mode='fixed_amount', number_of_instalments='',
                     fixed_deduction_amount='5000', interest_rate_annual='12')
        self.assertEqual(r.status_code, 302, getattr(r, 'context', None) and r.context['form'].errors)
        adv = Advance.objects.get()
        self.assertEqual(sum(row['amount'] for row in adv.amortization_schedule()), adv.total_payable)

    def test_validation(self):
        cases = [('principal_amount', '0'), ('interest_rate_annual', '99'),
                 ('number_of_instalments', '0'), ('deduction_start_year', '1999')]
        for field, value in cases:
            r = self.add(**{field: value})
            self.assertEqual(r.status_code, 200, field)
            self.assertIn(field, r.context['form'].errors, field)
        r = self.add(deduction_mode='fixed_amount', number_of_instalments='', fixed_deduction_amount='99999')
        self.assertIn('fixed_deduction_amount', r.context['form'].errors)
        r = self.add(number_of_instalments='')                    # instalment mode needs a count
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Loan.objects.count(), 0)

    def test_other_company_employee_cannot_be_selected(self):
        theirs = make_employee(self.other, '9')
        r = self.add(employee=theirs.pk)
        self.assertEqual(r.status_code, 200)
        self.assertIn('employee', r.context['form'].errors)
        self.assertEqual(Loan.objects.count(), 0)

    def test_relieved_employee_cannot_be_selected(self):
        gone = make_employee(self.co, '5', working=False)
        self.assertEqual(self.add(employee=gone.pk).status_code, 200)

    def test_copper_plan_is_gated(self):
        self.co.plan = 'copper'; self.co.save()
        for url in ('/entry/loans/', '/entry/loans/add/', '/entry/advances/'):
            r = self.client.get(url, **HOST)
            self.assertEqual(r.status_code, 302, url)
        self.assertEqual(self.add().status_code, 302)
        self.assertEqual(Loan.objects.count(), 0)
        labels = {i['label'] for g in self.client.get('/dashboard/', **HOST).context['capp_nav']
                  for i in g.get('items', [])}
        self.assertNotIn('Loans', labels)

    def test_menu_shows_loans_on_silver(self):
        labels = {i['label'] for g in self.client.get('/dashboard/', **HOST).context['capp_nav']
                  for i in g.get('items', [])}
        self.assertTrue({'Loans', 'Advances'} <= labels)

    def test_associate_lock_on_start_month(self):
        salary_processing.objects.create(company_id=self.co, month=12, year=2026, status='PROCESSED')
        r = self.add()
        self.assertEqual(r.status_code, 200)
        self.assertIn('deduction_start_month', r.context['form'].errors)
        self.assertEqual(self.add(deduction_start_month='1', deduction_start_year='2027').status_code, 302)

    def test_edit_stop_and_schedule_pages_and_pdf(self):
        self.add()
        loan = Loan.objects.get()
        pk = loan.loan_id
        self.assertContains(self.client.get(f'/entry/loans/{pk}/schedule/', **HOST), '2000.00')
        self.assertTrue(self.client.get(f'/entry/loans/{pk}/pdf/', **HOST).content.startswith(b'%PDF'))
        r = self.client.post(f'/entry/loans/{pk}/edit/', self.data(
            principal_amount='1', number_of_instalments='3', purpose='changed'), **HOST)
        self.assertEqual(r.status_code, 302)
        loan.refresh_from_db()
        self.assertEqual((loan.principal_amount, loan.number_of_instalments, loan.purpose),
                         (D('12000.00'), 3, 'changed'))          # principal and employee are locked
        self.client.get(f'/entry/loans/{pk}/stop/', **HOST)
        loan.refresh_from_db(); self.assertEqual(loan.status, 'active')      # GET never changes data
        self.client.post(f'/entry/loans/{pk}/stop/', **HOST)
        loan.refresh_from_db(); self.assertEqual(loan.status, 'cancelled')
        self.assertTrue(CappAuditLog.objects.filter(action='stop').exists())

    def test_other_tenant_is_404(self):
        theirs = make_employee(self.other, '9')
        loan = Loan.objects.create(employee=theirs, company=self.other, principal_amount=D('100'),
                                   deduction_mode='instalments', number_of_instalments=2,
                                   deduction_start_month=1, deduction_start_year=2027)
        for suffix in ('schedule/', 'pdf/', 'edit/'):
            self.assertEqual(self.client.get(f'/entry/loans/{loan.loan_id}/{suffix}', **HOST).status_code, 404)
        self.assertEqual(self.client.post(f'/entry/loans/{loan.loan_id}/stop/', **HOST).status_code, 404)

    def test_unknown_kind_is_404(self):
        self.assertEqual(self.client.get('/entry/grants/', **HOST).status_code, 404)

    def test_operator_flags(self):
        u = User.objects.create_user('op', password='pw-Strong-1')
        op = CompanyOperator.objects.create(user=u, company=self.co, can_view_employees=True)
        self.client.login(username='op', password='pw-Strong-1')
        self.assertEqual(self.client.get('/entry/loans/', **HOST).status_code, 200)       # view ok
        self.assertEqual(self.client.get('/entry/loans/add/', **HOST).status_code, 302)   # edit denied
        self.assertEqual(self.client.post('/entry/loans/add/', self.data(), **HOST).status_code, 403)
        op.can_edit_loans = True; op.save()
        self.assertEqual(self.client.post('/entry/loans/add/', self.data(), **HOST).status_code, 302)
        self.assertEqual(Loan.objects.get().created_by, 'op')
