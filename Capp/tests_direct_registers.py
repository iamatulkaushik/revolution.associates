"""D5b-1 tests - fines, deductions and overtime registers for DIRECT companies."""
from datetime import date
from decimal import Decimal as D
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.attandance import MinimumWagesOvertimeRegister, attendance
from Aapp.app.services import registers as rg
from Aapp.app.services.statutory_files import NothingToGenerate
from Aapp.app.wages import wages_deduction, wages_fine
from Capp.models import CompanyOwnerProfile
from Capp.tests_direct_payroll import add_staff
from Capp.tests_masters import HOST, make_company
from Sapp.app.company import company_statury

M, Y = 11, 2026
BASE = '/direct/registers/'


def direct(fn):
    return patch('Capp.direct.guards.get_mode', return_value='DIRECT')(fn)


@override_settings(ALLOWED_HOSTS=['*'])
class RegisterTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK', 'AAAAA1111A')
        self.c2 = make_company('Other', 'BBBBB2222B')
        self.user = User.objects.create_user('owner', password='x')
        CompanyOwnerProfile.objects.create(user=self.user, company=self.c1)
        self.client.login(username='owner', password='x')
        self.emps = add_staff(self.c1, self.user)
        self.other_emps = add_staff(self.c2, self.user, n=1)
        self.stat = company_statury.objects.create(company=self.c1, shop_act='SA/1')

    def post(self, path, data):
        return self.client.post(path, data, **HOST)

    def get(self, path):
        return self.client.get(path, **HOST)

    def attend(self, emp, company):
        return attendance.objects.create(
            employee_id=emp, emp_code=emp.employeecode, companyid=company,
            salary_month=M, salary_year=Y, working_days=D('26'))

    def fine_data(self, emp, **kw):
        return {'employee': emp.pk, 'fine_date': '2026-11-05', 'fine_amount': '100',
                'fine_reason': 'Late', 'salary_month': M, 'salary_year': Y, **kw}

    # -- access ------------------------------------------------------------------
    def test_associate_mode_blocked(self):
        for path in (BASE, f'{BASE}fines/', f'{BASE}fines/add/', f'{BASE}fines/{Y}/{M}/pdf/'):
            self.assertEqual(self.get(path).status_code, 302, path)
        self.assertEqual(self.post(f'{BASE}fines/add/', self.fine_data(self.emps[0])).status_code, 302)
        self.assertEqual(wages_fine.objects.count(), 0)

    @direct
    def test_permission_denied(self, _):
        with patch('Capp.access.has_perm', return_value=False):
            self.assertEqual(self.post(f'{BASE}fines/add/', self.fine_data(self.emps[0])).status_code, 302)
        self.assertEqual(wages_fine.objects.count(), 0)

    @direct
    def test_pages_load_and_unknown_key_404(self, _):
        for path in (BASE, f'{BASE}fines/', f'{BASE}deductions/', f'{BASE}overtime/',
                     f'{BASE}fines/add/', f'{BASE}deductions/add/', f'{BASE}overtime/add/'):
            self.assertEqual(self.get(path).status_code, 200, path)
        self.assertEqual(self.get(f'{BASE}nothing/').status_code, 404)

    # -- fines -------------------------------------------------------------------
    @direct
    def test_fine_add_list_download_delete(self, _):
        r = self.post(f'{BASE}fines/add/', self.fine_data(self.emps[0]))
        self.assertEqual(r.status_code, 302, r.content[:300])
        fine = wages_fine.objects.get()
        self.assertEqual((fine.company, fine.created_by), (self.c1, self.user))
        self.assertEqual(len(self.get(f'{BASE}fines/?month={M}&year={Y}').context['rows']), 1)
        r = self.get(f'{BASE}fines/{Y}/{M}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))
        self.post(f'{BASE}fines/{fine.pk}/delete/', {})
        self.assertEqual(wages_fine.objects.count(), 0)

    @direct
    def test_fines_off_without_shop_act(self, _):
        self.stat.shop_act = None
        self.stat.save()
        self.post(f'{BASE}fines/add/', self.fine_data(self.emps[0]))
        self.assertEqual(wages_fine.objects.count(), 0)
        self.assertEqual(self.get(f'{BASE}fines/{Y}/{M}/pdf/').status_code, 302)

    @direct
    def test_fine_validation(self, _):
        bad = [self.fine_data(self.emps[0], fine_amount='0'),
               self.fine_data(self.emps[0], fine_amount='-5'),
               self.fine_data(self.other_emps[0])]            # other company's employee
        for data in bad:
            self.assertEqual(self.post(f'{BASE}fines/add/', data).status_code, 200)
        self.assertEqual(wages_fine.objects.count(), 0)

    @direct
    def test_empty_month_download_redirects_with_message(self, _):
        r = self.get(f'{BASE}fines/{Y}/{M}/pdf/')
        self.assertEqual(r.status_code, 302)

    # -- deductions (no registration gate, as in Aapp) ------------------------------
    @direct
    def test_deduction_flow_without_shop_act(self, _):
        self.stat.shop_act = None
        self.stat.save()
        data = {'employee': self.emps[0].pk, 'deduction_type': 'other', 'deduction_amount': '250',
                'reason': 'Damage', 'salary_month': M, 'salary_year': Y}
        types = [c[0] for c in wages_deduction._meta.get_field('deduction_type').choices]
        data['deduction_type'] = types[0]
        r = self.post(f'{BASE}deductions/add/', data)
        self.assertEqual(r.status_code, 302, r.content[:300])
        self.assertEqual(wages_deduction.objects.get().company, self.c1)
        r = self.get(f'{BASE}deductions/{Y}/{M}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

    # -- overtime ----------------------------------------------------------------
    @direct
    def test_overtime_defaults_and_download(self, _):
        att = self.attend(self.emps[0], self.c1)
        r = self.post(f'{BASE}overtime/add/', {
            'attendance': att.pk, 'ot_date': '2026-11-09', 'overtime_hours': '2',
            'ordinary_rate': '100', 'ot_rate': '', 'ot_wages_paid': '', 'ot_reason': 'Rush'})
        self.assertEqual(r.status_code, 302, r.content[:300])
        ot = MinimumWagesOvertimeRegister.objects.get()
        self.assertEqual((ot.ot_rate, ot.ot_wages_paid), (D('200.00'), D('400.00')))
        r = self.get(f'{BASE}overtime/{Y}/{M}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

    @direct
    def test_overtime_other_company_attendance_rejected(self, _):
        att = self.attend(self.other_emps[0], self.c2)
        r = self.post(f'{BASE}overtime/add/', {
            'attendance': att.pk, 'ot_date': '2026-11-09', 'overtime_hours': '2',
            'ordinary_rate': '100', 'ot_reason': ''})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(MinimumWagesOvertimeRegister.objects.count(), 0)

    @direct
    def test_overtime_hours_must_be_positive(self, _):
        att = self.attend(self.emps[0], self.c1)
        r = self.post(f'{BASE}overtime/add/', {
            'attendance': att.pk, 'ot_date': '2026-11-09', 'overtime_hours': '0',
            'ordinary_rate': '100', 'ot_reason': ''})
        self.assertEqual(r.status_code, 200)

    # -- tenant isolation ------------------------------------------------------------
    @direct
    def test_other_company_entries_not_visible_or_deletable(self, _):
        other = wages_fine.objects.create(
            company=self.c2, employee=self.other_emps[0], fine_date=date(2026, 11, 5),
            fine_amount=D('50'), fine_reason='x', salary_month=M, salary_year=Y)
        self.assertEqual(len(self.get(f'{BASE}fines/?month={M}&year={Y}').context['rows']), 0)
        self.assertEqual(self.post(f'{BASE}fines/{other.pk}/delete/', {}).status_code, 404)
        self.assertTrue(wages_fine.objects.filter(pk=other.pk).exists())
        self.assertEqual(self.get(f'{BASE}fines/{Y}/{M}/pdf/').status_code, 302)   # nothing of ours

    @direct
    def test_delete_needs_post(self, _):
        fine = wages_fine.objects.create(
            company=self.c1, employee=self.emps[0], fine_date=date(2026, 11, 5),
            fine_amount=D('50'), fine_reason='x', salary_month=M, salary_year=Y)
        self.assertEqual(self.get(f'{BASE}fines/{fine.pk}/delete/').status_code, 405)

    # -- audit -------------------------------------------------------------------
    @direct
    def test_add_and_delete_audited(self, _):
        with patch('Capp.direct.registers.log_action') as log:
            self.post(f'{BASE}fines/add/', self.fine_data(self.emps[0]))
            fine = wages_fine.objects.get()
            self.post(f'{BASE}fines/{fine.pk}/delete/', {})
        self.assertEqual([c[0][1] for c in log.call_args_list], ['register.fines.add', 'register.fines.delete'])


@override_settings(ALLOWED_HOSTS=['*'])
class RegisterServiceTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK', 'AAAAA1111A')
        self.user = User.objects.create_user('owner', password='x')
        self.emps = add_staff(self.c1, self.user, n=1)

    def test_empty_periods_raise(self):
        for build in (rg.build_fines_register_pdf, rg.build_deductions_register_pdf, rg.build_ot_register_pdf):
            with self.assertRaises(NothingToGenerate):
                build(self.c1, M, Y)

    def test_fines_pdf(self):
        wages_fine.objects.create(company=self.c1, employee=self.emps[0], fine_date=date(2026, 11, 5),
                                  fine_amount=D('50'), fine_reason='x', salary_month=M, salary_year=Y)
        pdf, fname = rg.build_fines_register_pdf(self.c1, M, Y)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertTrue(fname.startswith('Fines_Register_'))
