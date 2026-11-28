"""D4 tests - month-end checklist (read-only) and its place on the Finalize page."""
from decimal import Decimal as D
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.attandance import attendance
from Aapp.app.loans_advances import Loan
from Aapp.app.salary_processing import salary_processing
from Aapp.app.services import payroll_batch as pb
from Capp.direct.checklist import build_checklist
from Capp.models import CompanyOwnerProfile
from Capp.tests_direct_payroll import add_staff
from Capp.tests_masters import HOST, make_company
from Sapp.app.company import company_statury

M, Y = 11, 2026


def direct(fn):
    return patch('Capp.direct.guards.get_mode', return_value='DIRECT')(fn)


def item(items, key):
    return next(i for i in items if i['key'] == key)


@override_settings(ALLOWED_HOSTS=['*'])
class ChecklistTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK', 'AAAAA1111A')
        self.c2 = make_company('Other', 'BBBBB2222B')
        self.user = User.objects.create_user('owner', password='x')
        CompanyOwnerProfile.objects.create(user=self.user, company=self.c1)
        self.client.login(username='owner', password='x')
        self.emps = add_staff(self.c1, self.user)
        self.other_emps = add_staff(self.c2, self.user, n=1)

    def attend(self, emp, company=None):
        return attendance.objects.create(
            employee_id=emp, emp_code=emp.employeecode, companyid=company or self.c1,
            salary_month=M, salary_year=Y, working_days=D('26'))

    # -- access ----------------------------------------------------------------
    def test_associate_mode_blocked(self):
        self.assertEqual(self.client.get('/direct/checklist/', **HOST).status_code, 302)

    @direct
    def test_page_loads(self, _):
        self.assertEqual(self.client.get(f'/direct/checklist/?month={M}&year={Y}', **HOST).status_code, 200)

    @direct
    def test_permission_denied(self, _):
        with patch('Capp.access.has_perm', return_value=False):
            self.assertEqual(self.client.get('/direct/checklist/', **HOST).status_code, 302)

    # -- items ------------------------------------------------------------------
    def test_attendance_missing_then_complete(self):
        it = item(build_checklist(self.c1, M, Y), 'attendance')
        self.assertEqual((it['status'], len(it['names'])), ('warn', 2))
        for e in self.emps:
            self.attend(e)
        self.assertEqual(item(build_checklist(self.c1, M, Y), 'attendance')['status'], 'ok')

    def test_other_company_attendance_does_not_count(self):
        self.attend(self.other_emps[0], company=self.c2)
        self.assertEqual(item(build_checklist(self.c1, M, Y), 'attendance')['status'], 'warn')

    def test_batch_states(self):
        self.assertEqual(item(build_checklist(self.c1, M, Y), 'batch')['status'], 'warn')
        batch, _c = pb.create_batch(self.c1, M, Y, 'owner')
        pb.process_batch(batch, self.c1, 'owner')
        self.assertEqual(item(build_checklist(self.c1, M, Y), 'batch')['status'], 'ok')

    def test_loan_added_after_processing_is_flagged_until_reprocessed(self):
        batch, _c = pb.create_batch(self.c1, M, Y, 'owner')
        pb.process_batch(batch, self.c1, 'owner')
        Loan.objects.create(employee=self.emps[0], company=self.c1, principal_amount=D('3000'),
                            deduction_mode='instalments', number_of_instalments=3,
                            deduction_start_month=M, deduction_start_year=Y, status='active')
        self.assertEqual(item(build_checklist(self.c1, M, Y), 'loans')['status'], 'warn')
        pb.process_batch(batch, self.c1, 'owner')
        self.assertEqual(item(build_checklist(self.c1, M, Y), 'loans')['status'], 'ok')

    def test_no_loans_is_ok(self):
        self.assertEqual(item(build_checklist(self.c1, M, Y), 'loans')['status'], 'ok')

    def test_uan_without_company_epf_number_is_flagged(self):
        self.emps[0].uan_number = '100000000000'
        self.emps[0].save()
        self.assertEqual(item(build_checklist(self.c1, M, Y), 'gates')['status'], 'warn')
        company_statury.objects.create(company=self.c1, epfo='HRGGN0012345000')
        self.assertEqual(item(build_checklist(self.c1, M, Y), 'gates')['status'], 'ok')

    def test_challans_pending_after_finalize(self):
        company_statury.objects.create(company=self.c1, epfo='HRGGN0012345000')
        batch, _c = pb.create_batch(self.c1, M, Y, 'owner')
        pb.process_batch(batch, self.c1, 'owner')
        self.assertEqual(item(build_checklist(self.c1, M, Y), 'challans')['status'], 'info')
        pb.approve_batch(batch, 'owner')
        it = item(build_checklist(self.c1, M, Y), 'challans')
        self.assertEqual((it['status'], len(it['names'])), ('warn', 1))

    def test_due_dates_follow_registrations(self):
        self.assertEqual(item(build_checklist(self.c1, M, Y), 'due')['names'], [])
        company_statury.objects.create(company=self.c1, epfo='HRGGN0012345000', esic='12345678901234567')
        names = item(build_checklist(self.c1, M, Y), 'due')['names']
        self.assertEqual(len(names), 2)
        self.assertIn('15 Dec 2026', names[0])
        self.assertIn('15 Jan 2027', ''.join(build_due(self.c1, 12, 2026)))

    def test_read_only(self):
        before = (salary_processing.objects.count(), attendance.objects.count())
        build_checklist(self.c1, M, Y)
        self.assertEqual((salary_processing.objects.count(), attendance.objects.count()), before)

    # -- finalize page -------------------------------------------------------------
    @direct
    def test_finalize_page_shows_checklist(self, _):
        batch, _c = pb.create_batch(self.c1, M, Y, 'owner')
        pb.process_batch(batch, self.c1, 'owner')
        r = self.client.get(f'/direct/payroll/{batch.pk}/finalize/', **HOST)
        self.assertEqual(r.status_code, 200)
        self.assertEqual({i['key'] for i in r.context['items']},
                         {'attendance', 'batch', 'loans', 'gates', 'challans', 'bank', 'due'})
        self.assertGreaterEqual(r.context['warnings'], 1)          # attendance missing
        self.assertContains(r, 'Last check before you finalize')

    @direct
    def test_warnings_do_not_block_finalize(self, _):
        batch, _c = pb.create_batch(self.c1, M, Y, 'owner')
        pb.process_batch(batch, self.c1, 'owner')
        self.client.post(f'/direct/payroll/{batch.pk}/finalize/', {}, **HOST)
        batch.refresh_from_db()
        self.assertEqual(batch.status, 'APPROVED')


def build_due(company, month, year):
    return item(build_checklist(company, month, year), 'due')['names']
