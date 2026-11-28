"""D5b-3b tests - bonus records, Form C/B registers and the Form D annual return."""
from datetime import date, timedelta
from decimal import Decimal as D
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.bonus import bonus_annual_return, bonus_record, bonus_set_on_set_off
from Aapp.app.services import bonus_returns as brs
from Aapp.app.services import payroll_batch as pb
from Aapp.app.services.statutory_files import NothingToGenerate
from Capp.models import CompanyOwnerProfile
from Capp.tests_direct_payroll import add_staff
from Capp.tests_masters import HOST, make_company

Y = 2026
BASE = '/direct/bonus/'
SO = f'{BASE}set-on-set-off/'
RET = '/direct/returns/bonus/'


def direct(fn):
    return patch('Capp.direct.guards.get_mode', return_value='DIRECT')(fn)


@override_settings(ALLOWED_HOSTS=['*'])
class BonusTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK', 'AAAAA1111A')
        self.c2 = make_company('Other', 'BBBBB2222B')
        self.user = User.objects.create_user('owner', password='x')
        CompanyOwnerProfile.objects.create(user=self.user, company=self.c1)
        self.client.login(username='owner', password='x')
        self.emps = add_staff(self.c1, self.user)
        self.other_emps = add_staff(self.c2, self.user, n=1)

    def get(self, path):
        return self.client.get(path, **HOST)

    def post(self, path, data=None):
        return self.client.post(path, data or {}, **HOST)

    def rec(self, emp=None, month=3, year=Y, company=None, paid=False, basic='1000'):
        return bonus_record.objects.create(
            company=company or self.c1, employee=emp or self.emps[0], salary_month=month, salary_year=year,
            basic_bonus=D(basic), bonus_percentage=D('8.33'), is_paid=paid,
            payment_date=date.today() if paid else None)

    def so(self, year=Y, company=None, **kw):
        return bonus_set_on_set_off.objects.create(company=company or self.c1, year=year, **kw)

    def data(self, emp=None, **kw):
        return {'employee': (emp or self.emps[0]).pk, 'salary_month': 3, 'salary_year': Y,
                'bonus_percentage': '8.33', 'basic_bonus': '1000', 'performance_bonus': '0',
                'festival_bonus': '0', 'other_bonus': '0', 'reason': '', **kw}

    def so_data(self, **kw):
        return {'year': Y, 'allocable_surplus': '500000', 'total_wages_for_bonus': '100000',
                'min_bonus_amount': '', 'max_bonus_amount': '', 'bonus_paid': '9000',
                'set_on_amount': '1000', 'set_off_amount': '0', 'cumulative_set_on': '1000', **kw}

    def batch(self, month, company=None):
        company = company or self.c1
        b, _ = pb.create_batch(company, month, Y, 'owner')
        pb.process_batch(b, company, 'owner')
        pb.approve_batch(b, 'owner')

    # -- access ------------------------------------------------------------------
    def test_associate_mode_blocked(self):
        r, s = self.rec(), self.so()
        for path in (BASE, f'{BASE}add/', f'{BASE}{r.pk}/edit/', f'{BASE}{r.pk}/pay/',
                     f'{BASE}register/{Y}/3/pdf/', SO, f'{SO}add/', f'{SO}{s.pk}/edit/', f'{SO}{s.pk}/pdf/'):
            self.assertEqual(self.get(path).status_code, 302, path)
        for path in (f'{BASE}{r.pk}/delete/', f'{SO}{s.pk}/delete/'):
            self.assertEqual(self.post(path).status_code, 302, path)
        self.assertEqual(self.post(f'{BASE}add/', self.data(self.emps[1])).status_code, 302)
        self.assertEqual((bonus_record.objects.count(), bonus_set_on_set_off.objects.count()), (1, 1))

    @direct
    def test_permission_denied(self, _):
        with patch('Capp.access.has_perm', return_value=False):
            self.assertEqual(self.post(f'{BASE}add/', self.data()).status_code, 302)
            self.assertEqual(self.post(f'{SO}add/', self.so_data()).status_code, 302)
        self.assertEqual((bonus_record.objects.count(), bonus_set_on_set_off.objects.count()), (0, 0))

    @direct
    def test_pages_load(self, _):
        for path in (BASE, f'{BASE}add/', SO, f'{SO}add/', '/direct/returns/'):
            self.assertEqual(self.get(path).status_code, 200, path)

    # -- bonus records ---------------------------------------------------------------
    @direct
    def test_add_computes_total_and_audits(self, _):
        with patch('Capp.direct.bonus.log_action') as log:
            r = self.post(f'{BASE}add/', self.data(performance_bonus='250.50', other_bonus='49.50'))
        self.assertEqual(r.status_code, 302, r.content[:400])
        b = bonus_record.objects.get()
        self.assertEqual((b.company, b.created_by, b.total_bonus), (self.c1, self.user, D('1300.00')))
        self.assertEqual(log.call_args_list[0][0][1], 'bonus.add')

    @direct
    def test_add_validation(self, _):
        self.rec()                                                  # employee 0, March, 2026 exists
        bad = [self.data(),                                         # duplicate employee-month-year
               self.data(self.emps[1], bonus_percentage='21'),
               self.data(self.emps[1], basic_bonus='-5'),
               self.data(self.emps[1], basic_bonus='0'),            # nothing to pay
               self.data(self.emps[1], salary_year='1999'),
               self.data(self.other_emps[0])]                       # other tenant
        for d in bad:
            self.assertEqual(self.post(f'{BASE}add/', d).status_code, 200, d)
        self.assertEqual(bonus_record.objects.count(), 1)

    @direct
    def test_edit_unpaid_then_pay_locks(self, _):
        b = self.rec()
        r = self.post(f'{BASE}{b.pk}/edit/', self.data(basic_bonus='2000'))
        self.assertEqual(r.status_code, 302, r.content[:400])
        b.refresh_from_db()
        self.assertEqual((b.total_bonus, b.updated_by), (D('2000.00'), self.user))
        future = (date.today() + timedelta(days=2)).isoformat()
        self.assertEqual(self.post(f'{BASE}{b.pk}/pay/', {'payment_date': future}).status_code, 200)
        self.assertEqual(self.get(f'{BASE}{b.pk}/pay/').status_code, 200)
        self.assertEqual(self.post(f'{BASE}{b.pk}/pay/', {'payment_date': date.today().isoformat()}).status_code, 302)
        b.refresh_from_db()
        self.assertTrue(b.is_paid)
        # paid = locked
        self.post(f'{BASE}{b.pk}/edit/', self.data(basic_bonus='9'))
        self.post(f'{BASE}{b.pk}/delete/')
        self.post(f'{BASE}{b.pk}/pay/', {'payment_date': date.today().isoformat()})
        b.refresh_from_db()
        self.assertEqual(b.total_bonus, D('2000.00'))
        self.assertTrue(bonus_record.objects.filter(pk=b.pk).exists())

    @direct
    def test_delete_unpaid_needs_post(self, _):
        b = self.rec()
        self.assertEqual(self.get(f'{BASE}{b.pk}/delete/').status_code, 405)
        self.post(f'{BASE}{b.pk}/delete/')
        self.assertEqual(bonus_record.objects.count(), 0)

    @direct
    def test_list_filters_year_and_total(self, _):
        self.rec(month=1)
        self.rec(month=2, basic='500')
        self.rec(month=1, year=2025)
        r = self.get(f'{BASE}?year={Y}')
        self.assertEqual((len(r.context['rows']), r.context['total']), (2, D('1500.00')))

    @direct
    def test_form_c_pdf_and_empty(self, _):
        self.assertEqual(self.get(f'{BASE}register/{Y}/3/pdf/').status_code, 302)
        self.rec()
        r = self.get(f'{BASE}register/{Y}/3/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))
        self.assertEqual(self.get(f'{BASE}register/{Y}/13/pdf/').status_code, 404)

    @direct
    def test_other_company_records_hidden_and_untouchable(self, _):
        o = self.rec(self.other_emps[0], company=self.c2)
        self.assertEqual(self.get(f'{BASE}{o.pk}/edit/').status_code, 404)
        self.assertEqual(self.get(f'{BASE}{o.pk}/pay/').status_code, 404)
        self.assertEqual(self.post(f'{BASE}{o.pk}/delete/').status_code, 404)
        self.assertEqual(self.get(f'{BASE}?year={Y}').context['rows'], [])
        self.assertEqual(self.get(f'{BASE}register/{Y}/3/pdf/').status_code, 302)   # nothing of ours

    # -- set-on / set-off (Form B) ----------------------------------------------------
    @direct
    def test_so_add_autofills_min_max(self, _):
        r = self.post(f'{SO}add/', self.so_data())
        self.assertEqual(r.status_code, 302, r.content[:400])
        s = bonus_set_on_set_off.objects.get()
        self.assertEqual((s.min_bonus_amount, s.max_bonus_amount), (D('8330.00'), D('20000.00')))
        self.assertEqual((s.company, s.created_by), (self.c1, self.user))

    @direct
    def test_so_explicit_min_max_kept(self, _):
        self.post(f'{SO}add/', self.so_data(min_bonus_amount='8000', max_bonus_amount='19000'))
        s = bonus_set_on_set_off.objects.get()
        self.assertEqual((s.min_bonus_amount, s.max_bonus_amount), (D('8000'), D('19000')))

    @direct
    def test_so_validation(self, _):
        self.so()
        bad = [self.so_data(),                                                  # duplicate year
               self.so_data(year=Y - 1, set_off_amount='500'),                  # set-on and set-off both
               self.so_data(year=Y - 1, min_bonus_amount='30000', max_bonus_amount='20000'),
               self.so_data(year=Y - 1, bonus_paid='-1'),
               self.so_data(year=1999)]
        for d in bad:
            self.assertEqual(self.post(f'{SO}add/', d).status_code, 200, d)
        self.assertEqual(bonus_set_on_set_off.objects.count(), 1)

    @direct
    def test_so_same_year_allowed_in_other_company(self, _):
        self.so(company=self.c2)
        self.assertEqual(self.post(f'{SO}add/', self.so_data()).status_code, 302)

    @direct
    def test_so_edit_keeps_own_year(self, _):
        s = self.so(total_wages_for_bonus=D('100000'))
        r = self.post(f'{SO}{s.pk}/edit/', self.so_data(bonus_paid='9500'))
        self.assertEqual(r.status_code, 302, r.content[:400])
        s.refresh_from_db()
        self.assertEqual(s.bonus_paid, D('9500'))

    @direct
    def test_so_delete_pdf_and_tenancy(self, _):
        s, o = self.so(), self.so(company=self.c2)
        r = self.get(f'{SO}{s.pk}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))
        for path in (f'{SO}{o.pk}/edit/', f'{SO}{o.pk}/pdf/'):
            self.assertEqual(self.get(path).status_code, 404, path)
        self.assertEqual(self.post(f'{SO}{o.pk}/delete/').status_code, 404)
        self.assertEqual(self.get(f'{SO}{s.pk}/delete/').status_code, 405)
        self.post(f'{SO}{s.pk}/delete/')
        self.assertEqual(list(bonus_set_on_set_off.objects.values_list('pk', flat=True)), [o.pk])

    # -- Form D annual return (Capp/direct/returns.py) ----------------------------------
    @direct
    def test_form_d_needs_finalized_payroll(self, _):
        self.rec(paid=True)
        self.assertEqual(self.post(f'{RET}generate/', {'year': Y}).status_code, 302)
        self.assertEqual(bonus_annual_return.objects.count(), 0)

    @direct
    def test_form_d_counts_only_paid_bonus(self, _):
        self.batch(11)
        self.rec(self.emps[0], month=1, paid=True, basic='1000')
        self.rec(self.emps[1], month=1, paid=False, basic='5000')
        self.rec(self.emps[0], month=2, year=Y - 1, paid=True, basic='7000')      # other year
        self.assertEqual(self.post(f'{RET}generate/', {'year': Y}).status_code, 302)
        ret = bonus_annual_return.objects.get()
        self.assertEqual((ret.company, ret.total_employees, ret.total_bonus_paid), (self.c1, 2, D('1000.00')))
        self.assertGreater(ret.total_wages, 0)
        # Aapp's own behaviour (every record) is unchanged
        self.assertEqual(brs.compute_bonus_return_totals(self.c1, Y)['total_bonus_paid'], D('6000.00'))

    @direct
    def test_form_d_edit_file_and_band_note(self, _):
        self.batch(11)
        self.rec(paid=True)
        self.post(f'{RET}generate/', {'year': Y})
        ret = bonus_annual_return.objects.get()
        page = self.get(f'{RET}{ret.pk}/edit/')
        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.context['notes'])                   # tiny bonus vs wages: outside 8.33-20%
        base = {'allocable_surplus': '500000', 'payment_date': '', 'filing_status': 'pending',
                'filed_date': '', 'acknowledgement_no': ''}
        self.assertEqual(self.post(f'{RET}{ret.pk}/edit/', {**base, 'allocable_surplus': '-1'}).status_code, 200)
        filed = {**base, 'filing_status': 'filed', 'filed_date': date.today().isoformat()}
        self.assertEqual(self.post(f'{RET}{ret.pk}/edit/', filed).status_code, 200)      # needs payment date
        filed['payment_date'] = date.today().isoformat()
        self.assertEqual(self.post(f'{RET}{ret.pk}/edit/', filed).status_code, 302)
        ret.refresh_from_db()
        self.assertEqual((ret.filing_status, ret.allocable_surplus), ('filed', D('500000')))
        self.post(f'{RET}{ret.pk}/recompute/')                   # filed: locked
        self.post(f'{RET}{ret.pk}/delete/')
        self.assertTrue(bonus_annual_return.objects.filter(pk=ret.pk).exists())

    @direct
    def test_form_d_pdf_and_tenancy(self, _):
        mine = bonus_annual_return.objects.create(company=self.c1, year=Y)
        other = bonus_annual_return.objects.create(company=self.c2, year=Y)
        r = self.get(f'{RET}{mine.pk}/download/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))
        self.assertEqual(self.get(f'{RET}{other.pk}/download/').status_code, 404)
        self.assertEqual(self.get(f'{RET}{other.pk}/edit/').status_code, 404)


@override_settings(ALLOWED_HOSTS=['*'])
class BonusServiceTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK Foods', 'AAAAA1111A')
        self.user = User.objects.create_user('owner', password='x')
        self.emps = add_staff(self.c1, self.user, n=1)

    def test_empty_register_message_matches_aapp(self):
        with self.assertRaises(NothingToGenerate) as cm:
            brs.build_bonus_register_pdf(self.c1, 3, 2026)
        self.assertEqual(str(cm.exception), 'No bonus records found for March 2026.')

    def test_pdf_builders_and_filenames(self):
        bonus_record.objects.create(company=self.c1, employee=self.emps[0], salary_month=3,
                                    salary_year=2026, basic_bonus=D('100'))
        pdf, name = brs.build_bonus_register_pdf(self.c1, 3, 2026)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(name, 'Bonus_Register_JSK_Foods_3_2026.pdf')
        ret = bonus_annual_return.objects.create(company=self.c1, year=2026)
        so = bonus_set_on_set_off.objects.create(company=self.c1, year=2026)
        self.assertEqual(brs.build_bonus_return_pdf(self.c1, ret)[1], 'Bonus_Form_D_JSK_Foods_2026.pdf')
        self.assertEqual(brs.build_set_on_set_off_pdf(self.c1, so)[1], 'Bonus_FormB_SetOnOff_JSK_Foods_2026.pdf')

    def test_aapp_helper_delegates(self):
        from Aapp.app import bonus as ab
        self.assertEqual(ab._compute_bonus_return_totals(self.c1, 2026),
                         brs.compute_bonus_return_totals(self.c1, 2026))
