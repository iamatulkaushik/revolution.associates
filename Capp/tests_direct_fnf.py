"""D6 tests - relieving and Full and Final settlement for DIRECT companies."""
from datetime import date, timedelta
from decimal import Decimal as D
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.fnf_settlement import FnFSettlement
from Aapp.app.loans_advances import Loan
from Aapp.app.services import fnf as svc
from Aapp.app.services.statutory_files import StatutoryFileError
from Capp.models import CompanyOwnerProfile
from Capp.tests_direct_payroll import add_staff
from Capp.tests_masters import HOST, make_company

BASE = '/direct/fnf/'
LWD = date(2026, 3, 31)


def direct(fn):
    return patch('Capp.direct.guards.get_mode', return_value='DIRECT')(fn)


@override_settings(ALLOWED_HOSTS=['*'])
class FnfTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK', 'AAAAA1111A')
        self.c2 = make_company('Other', 'BBBBB2222B')
        self.user = User.objects.create_user('owner', password='x')
        CompanyOwnerProfile.objects.create(user=self.user, company=self.c1)
        self.client.login(username='owner', password='x')
        self.emps = add_staff(self.c1, self.user)
        self.other = add_staff(self.c2, self.user, n=1)

    def get(self, path):
        return self.client.get(path, **HOST)

    def post(self, path, data=None):
        return self.client.post(path, data or {}, **HOST)

    def left(self, emp=None, when=LWD):
        emp = emp or self.emps[0]
        svc.relieve_employee(emp, when, 'Resigned')
        return emp

    def sdata(self, emp, **kw):
        return {'employee': emp.pk, 'notice_period_days_required': '30', 'notice_period_days_served': '30',
                'pending_salary': '1000', 'other_deductions': '0', 'asset_recovery_amount': '0', 'remarks': '',
                **kw}

    def settle(self, emp=None):
        emp = self.left(emp)
        self.post(f'{BASE}add/', self.sdata(emp))
        return FnFSettlement.objects.get(employee=emp)

    # -- access ------------------------------------------------------------------
    def test_associate_mode_blocked(self):
        for path in (BASE, f'{BASE}relieve/', f'{BASE}add/'):
            self.assertEqual(self.get(path).status_code, 302, path)
        self.post(f'{BASE}relieve/', {'employee': self.emps[0].pk, 'dateofleaving': '2026-03-31',
                                      'leaving_reason': 'x'})
        self.emps[0].refresh_from_db()
        self.assertTrue(self.emps[0].is_working)

    @direct
    def test_permission_denied(self, _):
        with patch('Capp.access.has_perm', return_value=False):
            r = self.post(f'{BASE}relieve/', {'employee': self.emps[0].pk, 'dateofleaving': '2026-03-31',
                                              'leaving_reason': 'x'})
        self.assertEqual(r.status_code, 302)
        self.emps[0].refresh_from_db()
        self.assertTrue(self.emps[0].is_working)

    @direct
    def test_pages_load(self, _):
        s = self.settle()
        for path in (BASE, f'{BASE}relieve/', f'{BASE}add/', f'{BASE}{s.pk}/', f'{BASE}{s.pk}/edit/'):
            self.assertEqual(self.get(path).status_code, 200, path)

    # -- relieving ---------------------------------------------------------------------
    @direct
    def test_relieve_sets_fields_and_audits(self, _):
        e = self.emps[0]
        with patch('Capp.direct.fnf.log_action') as log:
            r = self.post(f'{BASE}relieve/', {'employee': e.pk, 'dateofleaving': '2026-03-31',
                                              'leaving_reason': 'Resigned'})
        self.assertEqual(r.status_code, 302)
        e.refresh_from_db()
        self.assertEqual((e.is_working, e.dateofleaving, e.leaving_reason), (False, LWD, 'Resigned'))
        self.assertEqual(log.call_args[0][1], 'employee.relieve')

    @direct
    def test_relieve_validation_and_tenancy(self, _):
        e = self.emps[0]
        good = {'employee': e.pk, 'dateofleaving': '2026-03-31', 'leaving_reason': 'x'}
        for bad in ({**good, 'dateofleaving': (date.today() + timedelta(days=1)).isoformat()},
                    {**good, 'dateofleaving': '2019-12-31'},         # before joining
                    {**good, 'leaving_reason': ''},
                    {**good, 'employee': self.other[0].pk}):
            self.assertEqual(self.post(f'{BASE}relieve/', bad).status_code, 200, bad)
        e.refresh_from_db()
        self.other[0].refresh_from_db()
        self.assertTrue(e.is_working and self.other[0].is_working)

    @direct
    def test_reinstate_blocked_after_settlement(self, _):
        e = self.left()
        self.post(f'{BASE}reinstate/{e.pk}/')
        e.refresh_from_db()
        self.assertTrue(e.is_working)
        self.assertIsNone(e.dateofleaving)
        e = self.left()
        self.post(f'{BASE}add/', self.sdata(e))
        self.post(f'{BASE}reinstate/{e.pk}/')
        e.refresh_from_db()
        self.assertFalse(e.is_working)
        o = self.left(self.other[0])
        self.assertEqual(self.post(f'{BASE}reinstate/{o.pk}/').status_code, 404)

    # -- settlement --------------------------------------------------------------------
    @direct
    def test_settlement_needs_relieved_employee_of_this_company(self, _):
        e = self.emps[0]
        self.assertEqual(self.post(f'{BASE}add/', self.sdata(e)).status_code, 200)        # still working
        o = self.left(self.other[0])
        self.assertEqual(self.post(f'{BASE}add/', self.sdata(o)).status_code, 200)        # other company
        self.assertFalse(FnFSettlement.objects.exists())

    @direct
    def test_create_computes_and_blocks_second(self, _):
        e = self.left()
        Loan.objects.create(employee=e, company=self.c1, principal_amount=D('10000'), deduction_mode='instalments',
                            number_of_instalments=10, deduction_start_month=1, deduction_start_year=2026)
        with patch('Capp.direct.fnf.log_action') as log:
            r = self.post(f'{BASE}add/', self.sdata(e, notice_period_days_served='20'))
        self.assertEqual(r.status_code, 302, r.content[:300])
        s = FnFSettlement.objects.get()
        self.assertEqual((s.company, s.last_working_day, s.status, s.created_by), (self.c1, LWD, 'draft', 'owner'))
        self.assertEqual(s.loan_outstanding_recovery, D('8000.00'))
        self.assertEqual(s.pending_salary, D('1000'))
        self.assertEqual(s.net_settlement_amount, s.total_earnings - s.total_recoveries)
        self.assertEqual(log.call_args[0][1], 'fnf.add')
        self.assertEqual(self.post(f'{BASE}add/', self.sdata(e)).status_code, 200)        # one per employee

    @direct
    def test_validation(self, _):
        e = self.left()
        for bad in (self.sdata(e, pending_salary='-1'), self.sdata(e, other_deductions='-5'),
                    self.sdata(e, asset_recovery_amount='-1'), self.sdata(e, notice_period_days_required='400')):
            self.assertEqual(self.post(f'{BASE}add/', bad).status_code, 200, bad)
        self.assertFalse(FnFSettlement.objects.exists())

    @direct
    def test_edit_recompute_does_not_double_count_assets(self, _):
        e = self.left()
        self.post(f'{BASE}add/', self.sdata(e, asset_recovery_amount='300'))
        s = FnFSettlement.objects.get()
        self.assertEqual(s.asset_recovery_amount, D('300'))
        self.post(f'{BASE}{s.pk}/recompute/')
        self.post(f'{BASE}{s.pk}/recompute/')
        s.refresh_from_db()
        self.assertEqual(s.asset_recovery_amount, D('300'))
        self.post(f'{BASE}{s.pk}/edit/', self.sdata(e, asset_recovery_amount='500', other_deductions='50'))
        s.refresh_from_db()
        self.assertEqual((s.asset_recovery_amount, s.other_deductions), (D('500'), D('50')))

    @direct
    def test_lifecycle_and_locks(self, _):
        s = self.settle()
        e = s.employee
        Loan.objects.create(employee=e, company=self.c1, principal_amount=D('10000'), deduction_mode='instalments',
                            number_of_instalments=10, deduction_start_month=1, deduction_start_year=2026)
        self.assertEqual(self.post(f'{BASE}{s.pk}/paid/').status_code, 302)               # draft cannot be paid
        s.refresh_from_db()
        self.assertEqual(s.status, 'draft')
        with patch('Capp.direct.fnf.log_action') as log:
            self.post(f'{BASE}{s.pk}/finalize/')
        s.refresh_from_db()
        self.assertEqual(s.status, 'finalized')
        self.assertIsNotNone(s.finalized_at)
        self.assertEqual(log.call_args[0][1], 'fnf.finalize')
        self.post(f'{BASE}{s.pk}/edit/', self.sdata(e, pending_salary='99999'))
        self.post(f'{BASE}{s.pk}/recompute/')
        self.post(f'{BASE}{s.pk}/delete/')
        s.refresh_from_db()
        self.assertEqual(s.pending_salary, D('1000'))                                     # locked
        self.post(f'{BASE}{s.pk}/paid/')
        s.refresh_from_db()
        self.assertEqual(s.status, 'paid')
        self.assertIsNotNone(s.paid_at)
        self.assertEqual(Loan.objects.get(employee=e).status, 'completed')

    @direct
    def test_draft_delete_and_other_company_404(self, _):
        s = self.settle()
        o = self.left(self.other[0])
        os_ = FnFSettlement.objects.create(employee=o, company=self.c2, last_working_day=LWD)
        for path in (f'{BASE}{os_.pk}/', f'{BASE}{os_.pk}/edit/', f'{BASE}{os_.pk}/pdf/'):
            self.assertEqual(self.get(path).status_code, 404, path)
        for path in ('recompute', 'finalize', 'paid', 'delete'):
            self.assertEqual(self.post(f'{BASE}{os_.pk}/{path}/').status_code, 404, path)
        self.post(f'{BASE}{s.pk}/delete/')
        self.assertFalse(FnFSettlement.objects.filter(pk=s.pk).exists())

    @direct
    def test_pdfs_and_certificate_gating(self, _):
        s = self.settle()
        r = self.get(f'{BASE}{s.pk}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'fnf_settlement_{s.pk}.pdf', r['Content-Disposition'])
        self.assertEqual(self.get(f'{BASE}{s.pk}/certificate/experience/').status_code, 302)   # draft
        self.assertEqual(self.get(f'{BASE}{s.pk}/certificate/bogus/').status_code, 404)
        self.post(f'{BASE}{s.pk}/finalize/')
        self.assertEqual(self.get(f'{BASE}{s.pk}/certificate/experience/').status_code, 200)
        self.assertEqual(self.get(f'{BASE}{s.pk}/certificate/character/').status_code, 200)
        self.assertEqual(self.get(f'{BASE}{s.pk}/certificate/last_pay/').status_code, 302)     # not paid
        self.post(f'{BASE}{s.pk}/paid/')
        r = self.get(f'{BASE}{s.pk}/certificate/last_pay/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'last_pay_certificate_{s.pk}.pdf', r['Content-Disposition'])

    # -- service -----------------------------------------------------------------------
    def test_gratuity_ceiling_applied(self):
        s = FnFSettlement(employee=self.emps[0], company=self.c1, last_working_day=LWD)

        def fake(self_):
            self_.gratuity_amount = D('3000000')
            self_.net_settlement_amount = self_.total_earnings - self_.total_recoveries
        with patch.object(FnFSettlement, 'compute', fake):
            svc.compute_settlement(s)
        self.assertEqual(s.gratuity_amount, svc.GRATUITY_CEILING)
        self.assertEqual(s.net_settlement_amount, svc.GRATUITY_CEILING)

    def test_unknown_certificate_type_raises(self):
        s = FnFSettlement(employee=self.emps[0], company=self.c1, last_working_day=LWD)
        with self.assertRaises(StatutoryFileError):
            svc.build_fnf_certificate_pdf(s, 'nope')
