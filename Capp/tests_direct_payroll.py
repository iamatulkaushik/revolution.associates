"""D2 tests - payroll batch lifecycle (DIRECT) and the extracted Aapp service."""
from datetime import date
from decimal import Decimal as D
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.branch_department import branch, department
from Aapp.app.designation import designation
from Aapp.app.employee import employee
from Aapp.app.salary_processing import (
    calculate_employee_salary, salary_processing, salary_slip)
from Aapp.app.services import payroll_batch as svc
from Capp.models import CompanyOwnerProfile
from Capp.tests_bank_export import ZERO
from Capp.tests_masters import HOST, make_company

BASE = '/direct/payroll/'


def direct(fn):
    return patch('Capp.direct.guards.get_mode', return_value='DIRECT')(fn)


def add_staff(company, user, n=2, basic='15000'):
    br = branch.objects.create(branch_name='B', companyid=company, created_by=user)
    dp = department.objects.create(department_name='D', branch=br, companyid=company, created_by=user)
    ds = designation.objects.create(designationname='Helper', company=company, created_by='t',
                                    updated_by='t', **{**ZERO, 'basicpay': D(basic)})
    out = []
    for i in range(n):
        out.append(employee.objects.create(
            employeecode=f'{company.pk}0{i}', name=f'EMP{company.pk}{i}', fathername='F', gender='Male',
            dateofbirth=date(1990, 1, 1), temporaryaddress='SNP HR', mobile=f'9{company.pk}0000000{i}'[:10],
            email=f'e{company.pk}{i}@x.com', aadhar_number=f'{company.pk}1112222333{i}'[:12], aadhar_name='x',
            bank_name='B', bank_account=f'12345678901{i}', bank_ifsc='CNRB0018281',
            dateofjoining=date(2020, 1, 1), designationID=ds, departmentID=dp, branchID=br,
            CompanyID=company, temp_state=None))
    return out


@override_settings(ALLOWED_HOSTS=['*'])
class PayrollLifecycleTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK', 'AAAAA1111A')
        self.c2 = make_company('Other', 'BBBBB2222B')
        self.user = User.objects.create_user('owner', password='x')
        CompanyOwnerProfile.objects.create(user=self.user, company=self.c1)
        self.client.login(username='owner', password='x')
        self.emps = add_staff(self.c1, self.user)

    def go(self, url, data=None, **k):
        return self.client.post(url, data or {}, **HOST, **k)

    def make_batch(self, **kw):
        return salary_processing.objects.create(company_id=self.c1, month=11, year=2026, **kw)

    # -- access ----------------------------------------------------------------
    def test_associate_mode_blocks_every_url(self):
        b = self.make_batch()
        for suffix in ('', f'{b.pk}/', f'{b.pk}/finalize/'):
            self.assertEqual(self.client.get(BASE + suffix, **HOST).status_code, 302, suffix)
        for suffix in ('process/', 'reopen/', 'finalize/', 'paid/', 'delete/'):
            self.assertEqual(self.go(f'{BASE}{b.pk}/{suffix}').status_code, 302, suffix)
        b.refresh_from_db()
        self.assertEqual(b.status, 'DRAFT')
        self.assertTrue(salary_processing.objects.filter(pk=b.pk).exists())

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(BASE, **HOST).status_code, 302)

    @direct
    def test_permission_denied_changes_nothing(self, _):
        b = self.make_batch()
        with patch('Capp.access.has_perm', return_value=False):
            self.assertEqual(self.go(f'{BASE}{b.pk}/process/').status_code, 302)
        b.refresh_from_db()
        self.assertEqual(b.status, 'DRAFT')
        self.assertEqual(salary_slip.objects.count(), 0)

    # -- full month ----------------------------------------------------------------
    @direct
    def test_full_month(self, _):
        self.assertEqual(self.client.get(BASE, **HOST).status_code, 200)
        r = self.go(BASE, {'month': 11, 'year': 2026})
        b = salary_processing.objects.get(company_id=self.c1, month=11, year=2026)
        self.assertEqual((r.status_code, b.status), (302, 'DRAFT'))

        self.go(f'{BASE}{b.pk}/process/')
        b.refresh_from_db()
        self.assertEqual((b.status, b.total_employees), ('PROCESSED', 2))
        self.assertEqual(self.client.get(f'{BASE}{b.pk}/', **HOST).status_code, 200)

        self.assertEqual(self.client.get(f'{BASE}{b.pk}/finalize/', **HOST).status_code, 200)
        self.go(f'{BASE}{b.pk}/finalize/')
        b.refresh_from_db()
        self.assertEqual(b.status, 'APPROVED')
        self.assertIsNotNone(b.approved_at)

        self.go(f'{BASE}{b.pk}/paid/')
        b.refresh_from_db()
        self.assertEqual(b.status, 'PAID')

    @direct
    def test_duplicate_month_reuses_batch(self, _):
        self.go(BASE, {'month': 11, 'year': 2026})
        self.go(BASE, {'month': 11, 'year': 2026})
        self.assertEqual(salary_processing.objects.filter(company_id=self.c1).count(), 1)

    @direct
    def test_bad_month_rejected(self, _):
        self.go(BASE, {'month': 13, 'year': 2026})
        self.go(BASE, {'month': 'x', 'year': 'y'})
        self.assertEqual(salary_processing.objects.count(), 0)

    # -- guards ----------------------------------------------------------------
    @direct
    def test_approved_batch_is_locked(self, _):
        b = self.make_batch()
        self.go(f'{BASE}{b.pk}/process/')
        self.go(f'{BASE}{b.pk}/finalize/')
        slips_before = list(salary_slip.objects.values_list('pk', flat=True))
        for suffix in ('process/', 'reopen/', 'delete/'):
            self.go(f'{BASE}{b.pk}/{suffix}')
        b.refresh_from_db()
        self.assertEqual(b.status, 'APPROVED')
        self.assertEqual(list(salary_slip.objects.values_list('pk', flat=True)), slips_before)

    @direct
    def test_paid_batch_is_locked(self, _):
        b = self.make_batch(status='PAID', total_employees=1)
        for suffix in ('process/', 'reopen/', 'delete/', 'finalize/', 'paid/'):
            self.go(f'{BASE}{b.pk}/{suffix}')
        b.refresh_from_db()
        self.assertEqual(b.status, 'PAID')

    @direct
    def test_finalize_and_paid_need_right_status(self, _):
        b = self.make_batch()                              # DRAFT
        self.go(f'{BASE}{b.pk}/finalize/')
        self.go(f'{BASE}{b.pk}/paid/')
        b.refresh_from_db()
        self.assertEqual(b.status, 'DRAFT')

    @direct
    def test_empty_batch_cannot_be_finalized(self, _):
        b = self.make_batch(status='PROCESSED', total_employees=0)
        self.go(f'{BASE}{b.pk}/finalize/')
        b.refresh_from_db()
        self.assertEqual(b.status, 'PROCESSED')

    @direct
    def test_reopen_processed_then_reprocess_and_delete(self, _):
        b = self.make_batch()
        self.go(f'{BASE}{b.pk}/process/')
        self.go(f'{BASE}{b.pk}/reopen/')
        b.refresh_from_db()
        self.assertEqual(b.status, 'DRAFT')
        self.go(f'{BASE}{b.pk}/process/')
        self.go(f'{BASE}{b.pk}/process/')                   # reprocess is allowed before approval
        self.assertEqual(salary_slip.objects.filter(processing_id=b).count(), 2)
        self.go(f'{BASE}{b.pk}/delete/')
        self.assertFalse(salary_processing.objects.filter(pk=b.pk).exists())

    @direct
    def test_get_on_action_urls_not_allowed(self, _):
        b = self.make_batch()
        for suffix in ('process/', 'reopen/', 'paid/', 'delete/'):
            self.assertEqual(self.client.get(f'{BASE}{b.pk}/{suffix}', **HOST).status_code, 405, suffix)

    # -- tenant isolation ----------------------------------------------------------
    @direct
    def test_other_company_batch_is_404(self, _):
        other = salary_processing.objects.create(company_id=self.c2, month=11, year=2026,
                                                 status='PROCESSED', total_employees=1)
        self.assertEqual(self.client.get(f'{BASE}{other.pk}/', **HOST).status_code, 404)
        self.assertEqual(self.client.get(f'{BASE}{other.pk}/finalize/', **HOST).status_code, 404)
        for suffix in ('process/', 'reopen/', 'finalize/', 'paid/', 'delete/'):
            self.assertEqual(self.go(f'{BASE}{other.pk}/{suffix}').status_code, 404, suffix)
        other.refresh_from_db()
        self.assertEqual(other.status, 'PROCESSED')

    @direct
    def test_list_shows_only_own_batches(self, _):
        salary_processing.objects.create(company_id=self.c2, month=10, year=2026)
        self.make_batch()
        r = self.client.get(BASE, **HOST)
        self.assertEqual([b.company_id for b in r.context['batches']], [self.c1])

    # -- audit -------------------------------------------------------------------
    @direct
    def test_every_state_change_is_audited(self, _):
        b = self.make_batch()
        with patch('Capp.direct.payroll.log_action') as log:
            self.go(f'{BASE}{b.pk}/process/')
            self.go(f'{BASE}{b.pk}/reopen/')
            self.go(f'{BASE}{b.pk}/process/')
            self.go(f'{BASE}{b.pk}/finalize/')
            self.go(f'{BASE}{b.pk}/paid/')
        self.assertEqual([c[0][1] for c in log.call_args_list],
                         ['payroll.process', 'payroll.reopen', 'payroll.process',
                          'payroll.finalize', 'payroll.paid'])


@override_settings(ALLOWED_HOSTS=['*'])
class PayrollServiceTests(TestCase):
    """The extracted service must give the same numbers as calculate_employee_salary."""

    def setUp(self):
        self.c1 = make_company('JSK', 'AAAAA1111A')
        self.user = User.objects.create_user('owner', password='x')
        self.emps = add_staff(self.c1, self.user, n=3, basic='18000')

    def test_process_batch_matches_calculation(self):
        batch, created = svc.create_batch(self.c1, 11, 2026, 'owner')
        self.assertTrue(created)
        self.assertEqual(svc.create_batch(self.c1, 11, 2026, 'owner'), (batch, False))

        processed, skipped, errors = svc.process_batch(batch, self.c1, 'owner')
        self.assertEqual((processed, skipped, errors), (3, 0, []))

        batch.refresh_from_db()
        slips = salary_slip.objects.filter(processing_id=batch)
        self.assertEqual(batch.status, 'PROCESSED')
        self.assertEqual(slips.count(), 3)
        for emp in self.emps:
            calc = calculate_employee_salary(emp, emp.designationID, 11, 2026, company=self.c1)
            slip = slips.get(employee_id=emp)
            self.assertEqual(slip.gross_earnings, calc['gross_earnings'])
            self.assertEqual(slip.net_pay, calc['net_pay'])
        self.assertEqual(batch.total_net, sum(s.net_pay for s in slips).quantize(D('0.01')))
        self.assertEqual(batch.total_gross, sum(s.gross_earnings for s in slips).quantize(D('0.01')))

    def test_reprocess_replaces_slips(self):
        batch, _ = svc.create_batch(self.c1, 11, 2026, 'owner')
        svc.process_batch(batch, self.c1, 'owner')
        svc.process_batch(batch, self.c1, 'owner')
        self.assertEqual(salary_slip.objects.filter(processing_id=batch).count(), 3)

    def test_left_employee_is_not_processed(self):
        self.emps[0].is_working = False
        self.emps[0].save()
        batch, _ = svc.create_batch(self.c1, 11, 2026, 'owner')
        self.assertEqual(svc.process_batch(batch, self.c1, 'owner').processed, 2)

    def test_approve_and_delete(self):
        batch, _ = svc.create_batch(self.c1, 11, 2026, 'owner')
        svc.process_batch(batch, self.c1, 'owner')
        svc.approve_batch(batch, 'owner')
        batch.refresh_from_db()
        self.assertEqual(batch.status, 'APPROVED')
        self.assertIsNotNone(batch.approved_at)
        svc.delete_batch(batch)
        self.assertFalse(salary_processing.objects.filter(pk=batch.pk).exists())
