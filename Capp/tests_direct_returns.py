"""D5b-3a tests - Minimum Wages Form V and Payment of Wages Form IV annual returns."""
from datetime import date, timedelta
from decimal import Decimal as D
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.services import payroll_batch as pb
from Aapp.app.services import wage_returns as wr
from Aapp.app.wage_compliance import MinimumWagesAnnualReturn, PaymentOfWagesAnnualReturn
from Aapp.app.wages import wages_deduction, wages_fine
from Capp.models import CompanyOwnerProfile
from Capp.tests_direct_payroll import add_staff
from Capp.tests_masters import HOST, make_company

Y = 2026
BASE = '/direct/returns/'
MW, POW = 'minimum-wages', 'payment-of-wages'


def direct(fn):
    return patch('Capp.direct.guards.get_mode', return_value='DIRECT')(fn)


@override_settings(ALLOWED_HOSTS=['*'])
class ReturnTests(TestCase):
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

    def batch(self, month, status='APPROVED', company=None):
        company = company or self.c1
        b, _ = pb.create_batch(company, month, Y, 'owner')
        pb.process_batch(b, company, 'owner')
        if status == 'APPROVED':
            pb.approve_batch(b, 'owner')
        return b

    def gen(self, key=MW, year=Y):
        data = {'year': year}
        if key == MW:
            data['category_of_work'] = 'Shops'
        return self.post(f'{BASE}{key}/generate/', data)

    def mw(self, **kw):
        return MinimumWagesAnnualReturn.objects.create(company=self.c1, year=Y, category_of_work='Shops', **kw)

    def pow(self, **kw):
        return PaymentOfWagesAnnualReturn.objects.create(company=self.c1, year=Y, **kw)

    def edit_data(self, **kw):
        return {'category_of_work': 'Shops', 'min_wage_rate_unskilled': '10000',
                'min_wage_rate_semiskilled': '11000', 'min_wage_rate_skilled': '12000',
                'filing_status': 'pending', 'filed_date': '', 'acknowledgement_no': '', **kw}

    # -- access ------------------------------------------------------------------
    def test_associate_mode_blocked(self):
        rec = self.mw()
        for path in (BASE, f'{BASE}{MW}/', f'{BASE}{MW}/generate/', f'{BASE}{MW}/{rec.pk}/edit/',
                     f'{BASE}{MW}/{rec.pk}/download/'):
            self.assertEqual(self.get(path).status_code, 302, path)
        for suffix in ('recompute/', 'delete/'):
            self.assertEqual(self.post(f'{BASE}{MW}/{rec.pk}/{suffix}').status_code, 302, suffix)
        self.assertEqual(self.gen().status_code, 302)
        self.assertEqual(MinimumWagesAnnualReturn.objects.count(), 1)

    @direct
    def test_permission_denied(self, _):
        self.batch(11)
        with patch('Capp.access.has_perm', return_value=False):
            self.assertEqual(self.gen().status_code, 302)
        self.assertEqual(MinimumWagesAnnualReturn.objects.count(), 0)

    @direct
    def test_pages_load_and_unknown_key_404(self, _):
        for path in (BASE, f'{BASE}{MW}/', f'{BASE}{POW}/', f'{BASE}{MW}/generate/', f'{BASE}{POW}/generate/'):
            self.assertEqual(self.get(path).status_code, 200, path)
        self.assertEqual(self.get(f'{BASE}nothing/').status_code, 404)

    # -- generate: only finalized payroll counts -------------------------------------
    @direct
    def test_no_finalized_payroll_no_return(self, _):
        self.assertEqual(self.gen().status_code, 302)
        self.batch(11, status='PROCESSED')                        # processed is not finalized
        self.gen()
        self.gen(POW)
        self.assertEqual((MinimumWagesAnnualReturn.objects.count(), PaymentOfWagesAnnualReturn.objects.count()), (0, 0))

    @direct
    def test_generate_minwages_from_approved_batch(self, _):
        self.batch(11)
        r = self.gen()
        self.assertEqual(r.status_code, 302, r.content[:300])
        rec = MinimumWagesAnnualReturn.objects.get()
        self.assertEqual((rec.company, rec.created_by, rec.category_of_work), (self.c1, self.user, 'Shops'))
        self.assertEqual((rec.total_employees_male, rec.total_employees_female), (2, 0))
        self.assertGreater(rec.total_wages_paid, 0)
        self.assertTrue(r['Location'].endswith(f'{rec.pk}/edit/'))

    @direct
    def test_generate_pow_from_paid_batch(self, _):
        b = self.batch(11)
        b.status = 'PAID'
        b.save()
        self.gen(POW)
        rec = PaymentOfWagesAnnualReturn.objects.get()
        self.assertEqual(rec.total_employed, 2)
        self.assertEqual(rec.total_fines_realised, rec.total_fines_imposed)

    @direct
    def test_draft_months_and_their_fines_are_excluded(self, _):
        self.batch(11)
        self.batch(12, status='PROCESSED')
        for month, amt in ((11, '100'), (12, '700')):
            wages_fine.objects.create(company=self.c1, employee=self.emps[0], fine_date=date(Y, month, 5),
                                      fine_amount=D(amt), fine_reason='x', salary_month=month, salary_year=Y)
            wages_deduction.objects.create(company=self.c1, employee=self.emps[0], deduction_type=
                                           wages_deduction._meta.get_field('deduction_type').choices[0][0],
                                           deduction_amount=D(amt), reason='x', salary_month=month, salary_year=Y)
        self.gen()
        rec = MinimumWagesAnnualReturn.objects.get()
        self.assertEqual((rec.total_fines_imposed, rec.total_deductions), (D('100'), D('100')))
        # Aapp's own behaviour (statuses=None) still counts every batch
        loose = wr.compute_minwages_totals(self.c1, Y)
        strict = wr.compute_minwages_totals(self.c1, Y, wr.FINAL)
        self.assertGreater(loose['total_wages_paid'], strict['total_wages_paid'])
        self.assertEqual(loose['total_fines_imposed'], D('800'))

    @direct
    def test_other_company_payroll_not_counted(self, _):
        self.batch(11, company=self.c2)
        self.gen()
        self.assertEqual(MinimumWagesAnnualReturn.objects.count(), 0)

    @direct
    def test_generate_validation_and_duplicate(self, _):
        self.batch(11)
        for data in ({'year': 2022, 'category_of_work': 'Shops'},
                     {'year': date.today().year + 1, 'category_of_work': 'Shops'},
                     {'year': Y, 'category_of_work': ''}):
            self.assertEqual(self.post(f'{BASE}{MW}/generate/', data).status_code, 200, data)
        self.assertEqual(MinimumWagesAnnualReturn.objects.count(), 0)
        self.gen()
        self.gen()                                                # duplicate year refused
        self.assertEqual(MinimumWagesAnnualReturn.objects.count(), 1)

    # -- edit / filing ---------------------------------------------------------------
    @direct
    def test_minwages_edit_and_file(self, _):
        rec = self.mw()
        self.assertEqual(self.post(f'{BASE}{MW}/{rec.pk}/edit/', self.edit_data()).status_code, 302)
        rec.refresh_from_db()
        self.assertEqual(rec.min_wage_rate_skilled, D('12000'))
        r = self.post(f'{BASE}{MW}/{rec.pk}/edit/', self.edit_data(
            filing_status='filed', filed_date=date.today().isoformat(), acknowledgement_no='ACK1'))
        self.assertEqual(r.status_code, 302, r.content[:300])
        rec.refresh_from_db()
        self.assertEqual((rec.filing_status, rec.acknowledgement_no), ('filed', 'ACK1'))

    @direct
    def test_minwages_edit_validation(self, _):
        rec = self.mw()
        today = date.today().isoformat()
        bad = [self.edit_data(filing_status='filed'),                                   # no date
               self.edit_data(filing_status='filed', filed_date=today, min_wage_rate_skilled='0'),
               self.edit_data(filing_status='filed', filed_date=(date.today() + timedelta(days=3)).isoformat()),
               self.edit_data(min_wage_rate_unskilled='-1'),
               self.edit_data(category_of_work='   ')]
        for data in bad:
            self.assertEqual(self.post(f'{BASE}{MW}/{rec.pk}/edit/', data).status_code, 200, data)
        rec.refresh_from_db()
        self.assertEqual(rec.filing_status, 'pending')

    @direct
    def test_pow_edit_and_file(self, _):
        rec = self.pow()
        data = {'wage_period': 'weekly', 'payment_mode': 'cash', 'filing_status': 'filed',
                'filed_date': '', 'acknowledgement_no': ''}
        self.assertEqual(self.post(f'{BASE}{POW}/{rec.pk}/edit/', data).status_code, 200)      # needs date
        data['filed_date'] = date.today().isoformat()
        self.assertEqual(self.post(f'{BASE}{POW}/{rec.pk}/edit/', data).status_code, 302)
        rec.refresh_from_db()
        self.assertEqual((rec.wage_period, rec.filing_status), ('weekly', 'filed'))

    # -- recompute / delete / lock ---------------------------------------------------
    @direct
    def test_recompute_picks_up_new_finalized_month(self, _):
        self.batch(11)
        self.gen()
        rec = MinimumWagesAnnualReturn.objects.get()
        before = rec.total_wages_paid
        self.batch(12)
        self.assertEqual(self.post(f'{BASE}{MW}/{rec.pk}/recompute/').status_code, 302)
        rec.refresh_from_db()
        self.assertGreater(rec.total_wages_paid, before)
        self.assertEqual(rec.category_of_work, 'Shops')                                 # hand-entered data kept

    @direct
    def test_recompute_without_payroll_leaves_totals(self, _):
        rec = self.mw(total_wages_paid=D('999'))
        self.post(f'{BASE}{MW}/{rec.pk}/recompute/')
        rec.refresh_from_db()
        self.assertEqual(rec.total_wages_paid, D('999'))

    @direct
    def test_filed_return_cannot_be_recomputed_or_deleted(self, _):
        self.batch(11)
        rec = self.mw(filing_status='filed', filed_date=date.today(), total_wages_paid=D('5'))
        self.post(f'{BASE}{MW}/{rec.pk}/recompute/')
        self.post(f'{BASE}{MW}/{rec.pk}/delete/')
        rec.refresh_from_db()
        self.assertEqual(rec.total_wages_paid, D('5'))

    @direct
    def test_delete_pending_return_audited(self, _):
        rec = self.pow()
        self.assertEqual(self.get(f'{BASE}{POW}/{rec.pk}/delete/').status_code, 405)
        with patch('Capp.direct.returns.log_action') as log:
            self.post(f'{BASE}{POW}/{rec.pk}/delete/')
        self.assertEqual(PaymentOfWagesAnnualReturn.objects.count(), 0)
        self.assertEqual(log.call_args_list[0][0][1], 'return.payment-of-wages.delete')

    @direct
    def test_generate_and_edit_audited(self, _):
        self.batch(11)
        with patch('Capp.direct.returns.log_action') as log:
            self.gen()
            rec = MinimumWagesAnnualReturn.objects.get()
            self.post(f'{BASE}{MW}/{rec.pk}/edit/', self.edit_data())
        self.assertEqual([c[0][1] for c in log.call_args_list],
                         ['return.minimum-wages.generate', 'return.minimum-wages.edit'])

    # -- tenant isolation ------------------------------------------------------------
    @direct
    def test_other_company_returns_hidden_and_untouchable(self, _):
        other = MinimumWagesAnnualReturn.objects.create(company=self.c2, year=Y, category_of_work='x')
        other_pow = PaymentOfWagesAnnualReturn.objects.create(company=self.c2, year=Y)
        for key, rec in ((MW, other), (POW, other_pow)):
            self.assertEqual(self.get(f'{BASE}{key}/{rec.pk}/edit/').status_code, 404, key)
            self.assertEqual(self.get(f'{BASE}{key}/{rec.pk}/download/').status_code, 404, key)
            self.assertEqual(self.post(f'{BASE}{key}/{rec.pk}/recompute/').status_code, 404, key)
            self.assertEqual(self.post(f'{BASE}{key}/{rec.pk}/delete/').status_code, 404, key)
            self.assertEqual(self.get(f'{BASE}{key}/').context['rows'], [], key)
        self.assertTrue(MinimumWagesAnnualReturn.objects.filter(pk=other.pk).exists())

    # -- downloads -------------------------------------------------------------------
    @direct
    def test_downloads_give_pdf(self, _):
        a, b = self.mw(), self.pow()
        for key, rec in ((MW, a), (POW, b)):
            r = self.get(f'{BASE}{key}/{rec.pk}/download/')
            self.assertEqual(r.status_code, 200, key)
            self.assertTrue(r.content.startswith(b'%PDF'), key)


@override_settings(ALLOWED_HOSTS=['*'])
class WageReturnServiceTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK Foods', 'AAAAA1111A')
        self.user = User.objects.create_user('owner', password='x')
        self.emps = add_staff(self.c1, self.user, n=1)

    def test_pdf_builders_and_filenames(self):
        mw = MinimumWagesAnnualReturn.objects.create(company=self.c1, year=2026, category_of_work='Shops')
        pw = PaymentOfWagesAnnualReturn.objects.create(company=self.c1, year=2026)
        pdf, name = wr.build_minwages_return_pdf(self.c1, mw)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(name, 'MinWages_Form_V_JSK_Foods_2026.pdf')
        pdf, name = wr.build_pow_return_pdf(self.c1, pw)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(name, 'POW_Form_IV_JSK_Foods_2026.pdf')

    def test_aapp_helpers_delegate_to_service(self):
        from Aapp.app import wage_compliance as wc
        b, _ = pb.create_batch(self.c1, 11, 2026, 'owner')
        pb.process_batch(b, self.c1, 'owner')
        self.assertEqual(wc._compute_minwages_totals(self.c1, 2026), wr.compute_minwages_totals(self.c1, 2026))
        self.assertEqual(wc._compute_pow_totals(self.c1, 2026), wr.compute_pow_totals(self.c1, 2026))
