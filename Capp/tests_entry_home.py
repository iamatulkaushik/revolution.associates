"""E5 operator home block."""
from datetime import date
from decimal import Decimal as D

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.loans_advances import Loan
from Aapp.app.salary_processing import salary_processing
from Capp.entry.attendance import save_row
from Capp.foundation.models import CompanyOperator
from Capp.models import CompanyOwnerProfile
from Capp.tests_foundation import make_employee
from Capp.tests_masters import make_company

HOST = {'HTTP_HOST': 'capp.localhost'}


@override_settings(ALLOWED_HOSTS=['*'])
class OperatorHomeTests(TestCase):
    def setUp(self):
        self.co = make_company('JSK', 'AAAAA1111A')
        self.owner = User.objects.create_user('owner', password='pw-Strong-1')
        CompanyOwnerProfile.objects.create(user=self.owner, company=self.co)
        self.u = User.objects.create_user('op', password='pw-Strong-1')
        self.op = CompanyOperator.objects.create(user=self.u, company=self.co, can_view_employees=True,
                                                 can_view_attendance=True, can_edit_attendance=True)
        self.e1, self.e2 = make_employee(self.co, '1'), make_employee(self.co, '2')

    def home(self, name='op'):
        self.client.login(username=name, password='pw-Strong-1')
        return self.client.get('/dashboard/', **HOST)

    def test_operator_sees_block_owner_does_not(self):
        r = self.home()
        self.assertContains(r, 'My work')
        self.assertEqual(r.context['operator_home']['attendance_missing'], 2)
        self.assertNotContains(self.home('owner'), 'My work')

    def test_counts_follow_the_work(self):
        t = date.today()
        save_row(self.co, self.e1, t.month, t.year, {'working_days': D('20')}, self.u)
        h = self.home().context['operator_home']
        self.assertEqual((h['attendance_entered'], h['attendance_missing']), (1, 1))

    def test_links_only_for_held_permissions(self):
        labels = {l['label'] for l in self.home().context['operator_home']['links']}
        self.assertEqual(labels, {'Enter attendance'})            # no add-employee, no downloads
        self.op.can_add_employees = True; self.op.save()
        labels = {l['label'] for l in self.home().context['operator_home']['links']}
        self.assertEqual(labels, {'Enter attendance', 'Add employee'})

    def test_lock_and_plan_usage_shown(self):
        t = date.today()
        salary_processing.objects.create(company_id=self.co, month=t.month, year=t.year, status='PROCESSED')
        r = self.home()
        self.assertFalse(r.context['operator_home']['entry_open'])
        self.assertContains(r, 'Entry is closed')
        self.assertContains(r, 'Plan usage')

    def test_loans_line_only_on_plans_with_loans(self):
        self.assertNotIn('loans_entered', self.home().context['operator_home'])
        type(self.co).objects.filter(pk=self.co.pk).update(plan='silver')
        Loan.objects.create(employee=self.e1, company=self.co, principal_amount=D('100'),
                            deduction_mode='instalments', number_of_instalments=2, deduction_start_month=1,
                            deduction_start_year=2027, created_by='op')
        self.assertEqual(self.home().context['operator_home']['loans_entered'], 1)
