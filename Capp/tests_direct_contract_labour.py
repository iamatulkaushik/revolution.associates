"""D5b-3d tests - Contract Labour Act records for DIRECT companies."""
from datetime import date, timedelta
from decimal import Decimal as D
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.contract_labour import (
    ContractEmploymentCard, ContractLabourHalfYearlyReturn, ContractLabourRegistration,
    ContractServiceCertificate)
from Aapp.app.contractor import contractor, contractor_payment, contractor_worker
from Aapp.app.services import contract_labour_registers as cl
from Aapp.app.services import payroll_batch as pb
from Aapp.app.services.statutory_files import NothingToGenerate
from Capp.models import CompanyOwnerProfile
from Capp.tests_direct_payroll import add_staff
from Capp.tests_masters import HOST, make_company
from Sapp.app.company import company_statury

BASE = '/direct/contract-labour/'
TODAY = date.today()
YEAR = 2026


def direct(fn):
    return patch('Capp.direct.guards.get_mode', return_value='DIRECT')(fn)


@override_settings(ALLOWED_HOSTS=['*'])
class ContractLabourTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK', 'AAAAA1111A')
        self.c2 = make_company('Other', 'BBBBB2222B')
        self.user = User.objects.create_user('owner', password='x')
        CompanyOwnerProfile.objects.create(user=self.user, company=self.c1)
        self.client.login(username='owner', password='x')
        self.emps = add_staff(self.c1, self.user)
        self.other_emps = add_staff(self.c2, self.user, n=1)
        self.stat = company_statury.objects.create(company=self.c1, labour='LAB/1')
        self.con = self.mk(self.c1, 'Acme Works', 'LIC-1')
        self.ocon = self.mk(self.c2, 'Rival', 'LIC-9')

    def get(self, path):
        return self.client.get(path, **HOST)

    def post(self, path, data=None):
        return self.client.post(path, data or {}, **HOST)

    def mk(self, company, name, lic):
        return contractor.objects.create(
            company=company, principal_employer=company.company_name, contractor_name=name,
            contractor_license_no=lic, work_description='Housekeeping', contract_start_date=date(2026, 1, 1),
            contract_end_date=date(2027, 12, 31), contract_amount=D('100000'), payment_schedule='monthly',
            max_contract_workers=20)

    def deploy(self, emp=None, con=None, start=date(2026, 1, 1), end=None):
        return contractor_worker.objects.create(
            contractor=con or self.con, company=self.c1, employee=emp or self.emps[0],
            deployment_start=start, deployment_end=end)

    def batch(self, month, status='APPROVED'):
        b, _ = pb.create_batch(self.c1, month, YEAR, 'owner')
        pb.process_batch(b, self.c1, 'owner')
        if status == 'APPROVED':
            pb.approve_batch(b, 'owner')

    def cdata(self, **kw):
        return {'contractor_name': 'New Co', 'contractor_license_no': 'lic-5', 'contractor_address': 'Addr',
                'contractor_mobile': '9876543210', 'contractor_email': '', 'contractor_pan': 'abcde1234f',
                'contractor_gstin': '', 'work_description': 'Security', 'contract_start_date': '2026-01-01',
                'contract_end_date': '2026-12-31', 'contract_amount': '5000', 'payment_schedule': 'monthly',
                'max_contract_workers': '5', 'worksite_address': '', 'status': 'active', **kw}

    # -- access ------------------------------------------------------------------
    def test_associate_mode_blocked(self):
        cid = self.con.pk
        for path in (BASE, f'{BASE}registration/add/', f'{BASE}contractors/add/', f'{BASE}contractors/{cid}/workers/',
                     f'{BASE}contractors/{cid}/returns/'):
            self.assertEqual(self.get(path).status_code, 302, path)
        self.post(f'{BASE}contractors/add/', self.cdata())
        self.assertEqual(contractor.objects.filter(company=self.c1).count(), 1)

    @direct
    def test_permission_denied(self, _):
        with patch('Capp.access.has_perm', return_value=False):
            self.assertEqual(self.post(f'{BASE}contractors/add/', self.cdata()).status_code, 302)
        self.assertEqual(contractor.objects.filter(company=self.c1).count(), 1)

    @direct
    def test_pages_load(self, _):
        cid = self.con.pk
        for path in (BASE, f'{BASE}registration/add/', f'{BASE}contractors/add/', f'{BASE}contractors/{cid}/edit/',
                     f'{BASE}contractors/{cid}/workers/', f'{BASE}contractors/{cid}/payments/',
                     f'{BASE}contractors/{cid}/cards/', f'{BASE}contractors/{cid}/certificates/',
                     f'{BASE}contractors/{cid}/workers/add/', f'{BASE}contractors/{cid}/payments/add/',
                     f'{BASE}contractors/{cid}/returns/', f'{BASE}contractors/{cid}/returns/add/'):
            self.assertEqual(self.get(path).status_code, 200, path)
        self.assertEqual(self.get(f'{BASE}contractors/{cid}/nothing/').status_code, 404)

    # -- gate (fail-closed) ------------------------------------------------------------
    @direct
    def test_off_without_licence_but_registration_open(self, _):
        self.stat.labour = ''
        self.stat.save()
        self.assertFalse(self.get(BASE).context['on'])
        cid = self.con.pk
        for path in (f'{BASE}contractors/add/', f'{BASE}contractors/{cid}/workers/', f'{BASE}contractors/{cid}/returns/'):
            self.assertEqual(self.get(path).status_code, 302, path)
        self.post(f'{BASE}contractors/add/', self.cdata())
        self.assertEqual(contractor.objects.filter(company=self.c1).count(), 1)
        self.assertEqual(self.get(f'{BASE}registration/add/').status_code, 200)
        r = self.post(f'{BASE}registration/add/', {
            'registration_cert_no': 'reg-1', 'registration_date': '2026-01-05', 'establishment_name': 'JSK',
            'nature_of_work': 'Cleaning', 'max_contract_workers': '30', 'is_active': 'on'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.get(BASE).context['on'])        # an active certificate turns it on

    # -- registration ------------------------------------------------------------------
    @direct
    def test_registration_uppercase_duplicate_and_pdf(self, _):
        data = {'registration_cert_no': 'reg-1', 'registration_date': '2026-01-05', 'establishment_name': 'JSK',
                'nature_of_work': 'Cleaning', 'max_contract_workers': '30', 'is_active': 'on'}
        with patch('Capp.direct.contract_labour.log_action') as log:
            self.assertEqual(self.post(f'{BASE}registration/add/', data).status_code, 302)
        reg = ContractLabourRegistration.objects.get(registration_cert_no='REG-1')
        self.assertEqual(reg.company, self.c1)
        self.assertEqual(log.call_args[0][1], 'contract.registration.add')
        self.assertEqual(self.post(f'{BASE}registration/add/', data).status_code, 200)    # duplicate
        r = self.get(f'{BASE}registration/{reg.pk}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('CL_Registration_JSK', r['Content-Disposition'])
        self.assertEqual(self.post(f'{BASE}registration/{reg.pk}/delete/').status_code, 302)
        self.assertFalse(ContractLabourRegistration.objects.exists())

    @direct
    def test_registration_other_company_404(self, _):
        o = ContractLabourRegistration.objects.create(company=self.c2, registration_cert_no='X', establishment_name='O',
                                                      nature_of_work='n', max_contract_workers=5)
        self.assertEqual(self.get(f'{BASE}registration/{o.pk}/edit/').status_code, 404)
        self.assertEqual(self.post(f'{BASE}registration/{o.pk}/delete/').status_code, 404)
        self.assertEqual(self.get(f'{BASE}registration/{o.pk}/pdf/').status_code, 404)

    # -- contractors -------------------------------------------------------------------
    @direct
    def test_add_contractor_sets_company_and_principal(self, _):
        with patch('Capp.direct.contract_labour.log_action') as log:
            r = self.post(f'{BASE}contractors/add/', self.cdata())
        self.assertEqual(r.status_code, 302, r.content[:400])
        c = contractor.objects.get(contractor_license_no='LIC-5')
        self.assertEqual((c.company, c.principal_employer, c.contractor_pan), (self.c1, 'JSK', 'ABCDE1234F'))
        self.assertEqual(log.call_args[0][1], 'contract.contractor.add')

    @direct
    def test_contractor_validation(self, _):
        bad = [self.cdata(contractor_license_no='LIC-1'), self.cdata(contractor_pan='bad'),
               self.cdata(contractor_gstin='123'), self.cdata(contractor_mobile='12345'),
               self.cdata(contract_end_date='2025-01-01'), self.cdata(contract_amount='-1'),
               self.cdata(max_contract_workers='0'), self.cdata(contractor_license_no='')]
        for d in bad:
            self.assertEqual(self.post(f'{BASE}contractors/add/', d).status_code, 200, d)
        self.assertEqual(contractor.objects.filter(company=self.c1).count(), 1)

    @direct
    def test_contractor_capped_by_registration(self, _):
        ContractLabourRegistration.objects.create(company=self.c1, registration_cert_no='R', establishment_name='J',
                                                  nature_of_work='n', max_contract_workers=10)
        self.assertEqual(self.post(f'{BASE}contractors/add/', self.cdata(max_contract_workers='11')).status_code, 200)
        self.assertEqual(self.post(f'{BASE}contractors/add/', self.cdata(max_contract_workers='10')).status_code, 302)

    @direct
    def test_contractor_tenancy_and_delete_rules(self, _):
        oid = self.ocon.pk
        self.assertEqual(self.get(f'{BASE}contractors/{oid}/edit/').status_code, 404)
        self.assertEqual(self.get(f'{BASE}contractors/{oid}/workers/').status_code, 404)
        self.assertEqual(self.post(f'{BASE}contractors/{oid}/delete/').status_code, 404)
        self.deploy()
        self.post(f'{BASE}contractors/{self.con.pk}/delete/')
        self.assertTrue(contractor.objects.filter(pk=self.con.pk).exists())        # has a worker
        empty = self.mk(self.c1, 'Empty', 'LIC-7')
        self.post(f'{BASE}contractors/{empty.pk}/delete/')
        self.assertFalse(contractor.objects.filter(pk=empty.pk).exists())

    # -- workers -----------------------------------------------------------------------
    @direct
    def test_worker_add_overlap_and_other_company_employee(self, _):
        url = f'{BASE}contractors/{self.con.pk}/workers/add/'
        d = {'employee': self.emps[0].pk, 'deployment_start': '2026-02-01', 'deployment_end': '', 'work_description': 'x'}
        self.assertEqual(self.post(url, d).status_code, 302)
        w = contractor_worker.objects.get()
        self.assertEqual((w.company, w.contractor), (self.c1, self.con))
        self.assertEqual(self.post(url, d).status_code, 200)                         # overlaps itself
        other = self.mk(self.c1, 'Second', 'LIC-2')
        self.assertEqual(self.post(f'{BASE}contractors/{other.pk}/workers/add/', d).status_code, 200)
        self.assertEqual(self.post(url, {**d, 'employee': self.other_emps[0].pk}).status_code, 200)   # POST tenancy
        self.assertEqual(contractor_worker.objects.count(), 1)

    @direct
    def test_worker_end_and_delete_rules(self, _):
        w = self.deploy()
        self.post(f'{BASE}contractors/{self.con.pk}/workers/{w.pk}/end/')
        w.refresh_from_db()
        self.assertEqual(w.deployment_end, TODAY)
        ContractEmploymentCard.objects.create(
            company=self.c1, contractor=self.con, employee=self.emps[0], work_description='w', work_site='s',
            issue_date=date(2026, 1, 2))
        self.post(f'{BASE}contractors/{self.con.pk}/workers/{w.pk}/delete/')
        self.assertTrue(contractor_worker.objects.filter(pk=w.pk).exists())         # has a card

    # -- payments ----------------------------------------------------------------------
    @direct
    def test_payments_add_validate_and_register_pdf(self, _):
        cid = self.con.pk
        url = f'{BASE}contractors/{cid}/payments/add/'
        r = self.get(f'{BASE}contractors/{cid}/payments/pdf/')
        self.assertEqual(r.status_code, 302)                                         # nothing yet
        good = {'salary_month': '3', 'salary_year': '2026', 'payment_amount': '1500',
                'payment_date': '2026-04-02', 'payment_reference': 'UTR1', 'remarks': ''}
        for bad in ({**good, 'salary_month': '13'}, {**good, 'payment_amount': '0'},
                    {**good, 'payment_date': (TODAY + timedelta(days=2)).isoformat()}):
            self.assertEqual(self.post(url, bad).status_code, 200)
        self.assertEqual(self.post(url, good).status_code, 302)
        p = contractor_payment.objects.get()
        self.assertEqual((p.company, p.contractor, p.created_by), (self.c1, self.con, self.user))
        r = self.get(f'{BASE}contractors/{cid}/payments/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Contractor_Payment_Register_Acme_Works', r['Content-Disposition'])
        self.post(f'{BASE}contractors/{cid}/payments/{p.pk}/delete/')
        self.assertFalse(contractor_payment.objects.exists())

    # -- cards and certificates -----------------------------------------------------------
    @direct
    def test_card_needs_deployed_employee_and_unique_number(self, _):
        self.deploy()
        url = f'{BASE}contractors/{self.con.pk}/cards/add/'
        d = {'employee': self.emps[0].pk, 'card_number': 'C-1', 'token_number': 'T1', 'work_description': 'w',
             'work_site': 'Plant', 'wage_rate': '500', 'issue_date': '2026-02-01', 'validity_date': ''}
        self.assertEqual(self.post(url, {**d, 'employee': self.emps[1].pk}).status_code, 200)   # not deployed
        self.assertEqual(self.post(url, {**d, 'issue_date': '2026-02-01', 'validity_date': '2026-01-01'}).status_code, 200)
        self.assertEqual(self.post(url, d).status_code, 302)
        self.assertEqual(self.post(url, d).status_code, 200)                         # duplicate number
        card = ContractEmploymentCard.objects.get()
        self.assertEqual(card.company, self.c1)
        r = self.get(f'{BASE}contractors/{self.con.pk}/cards/{card.pk}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Employment_Card_', r['Content-Disposition'])

    @direct
    def test_certificate_dates_and_pdf(self, _):
        self.deploy()
        url = f'{BASE}contractors/{self.con.pk}/certificates/add/'
        d = {'employee': self.emps[0].pk, 'work_description': 'w', 'work_site': 'Plant',
             'date_of_employment': '2026-01-01', 'date_of_termination': '2026-03-31',
             'reason_for_termination': 'End of contract', 'last_wage_paid': '9000', 'certificate_date': '2026-03-31'}
        self.assertEqual(self.post(url, {**d, 'date_of_termination': '2025-12-01'}).status_code, 200)
        self.assertEqual(self.post(url, {**d, 'certificate_date': '2026-03-30'}).status_code, 200)
        self.assertEqual(self.post(url, {**d, 'certificate_date': (TODAY + timedelta(days=1)).isoformat()}).status_code, 200)
        self.assertEqual(self.post(url, {**d, 'employee': self.other_emps[0].pk}).status_code, 200)
        self.assertEqual(self.post(url, d).status_code, 302)
        cert = ContractServiceCertificate.objects.get()
        r = self.get(f'{BASE}contractors/{self.con.pk}/certificates/{cert.pk}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.get(f'{BASE}contractors/{self.ocon.pk}/certificates/{cert.pk}/pdf/').status_code, 404)

    # -- Form 20(CL) -------------------------------------------------------------------
    @direct
    def test_return_prefill_uses_finalized_payroll_only(self, _):
        self.deploy()
        self.batch(3)
        self.batch(4, status='PROCESSED')
        final = cl.compute_cl_half_year_totals(self.c1, self.con, YEAR, 'jan_jun')
        everything = cl.compute_cl_half_year_totals(self.c1, self.con, YEAR, 'jan_jun', statuses=None)
        self.assertEqual(final['total_workers_employed'], 1)
        self.assertGreater(final['total_wages_paid'], 0)
        self.assertLess(final['total_man_days'], everything['total_man_days'])
        r = self.get(f'{BASE}contractors/{self.con.pk}/returns/add/?year={YEAR}&half_year=jan_jun')
        self.assertEqual(r.context['form'].initial['total_wages_paid'], final['total_wages_paid'])

    @direct
    def test_return_excludes_workers_of_other_contractors(self, _):
        self.deploy(self.emps[0])
        self.batch(3)
        other = self.mk(self.c1, 'Second', 'LIC-2')
        self.assertEqual(cl.compute_cl_half_year_totals(self.c1, other, YEAR, 'jan_jun')['total_workers_employed'], 0)

    def rdata(self, **kw):
        return {'year': '2026', 'half_year': 'jan_jun', 'total_workers_employed': '1', 'total_man_days': '26',
                'total_wages_paid': '9000', 'total_overtime_hours': '0', 'total_overtime_wages': '0',
                'filing_status': 'pending', 'filed_date': '', 'acknowledgement_no': '', **kw}

    @direct
    def test_return_create_validation_and_lock(self, _):
        cid = self.con.pk
        url = f'{BASE}contractors/{cid}/returns/add/'
        for bad in (self.rdata(half_year='jul_dec', year=str(TODAY.year)),      # not closed yet
                    self.rdata(year='2019'), self.rdata(filing_status='filed'),   # filed needs a date
                    self.rdata(filed_date='2026-07-10'),                        # date without Filed
                    self.rdata(total_wages_paid='-1')):
            self.assertEqual(self.post(url, bad).status_code, 200, bad)
        with patch('Capp.direct.contract_labour.log_action') as log:
            self.assertEqual(self.post(url, self.rdata()).status_code, 302)
        self.assertEqual(log.call_args[0][1], 'contract.return.add')
        rec = ContractLabourHalfYearlyReturn.objects.get()
        self.assertEqual((rec.company, rec.contractor), (self.c1, self.con))
        self.assertEqual(self.post(url, self.rdata()).status_code, 200)         # duplicate
        r = self.post(f'{BASE}contractors/{cid}/returns/{rec.pk}/edit/',
                      self.rdata(filing_status='filed', filed_date='2026-07-10', acknowledgement_no='ACK1'))
        self.assertEqual(r.status_code, 302, r.content[:300])
        self.post(f'{BASE}contractors/{cid}/returns/{rec.pk}/recompute/')
        self.post(f'{BASE}contractors/{cid}/returns/{rec.pk}/delete/')
        rec.refresh_from_db()
        self.assertEqual(rec.total_wages_paid, D('9000'))                       # not recomputed or deleted
        r = self.get(f'{BASE}contractors/{cid}/returns/{rec.pk}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.get(f'{BASE}contractors/{self.ocon.pk}/returns/{rec.pk}/pdf/').status_code, 404)

    @direct
    def test_return_recompute_and_delete_when_pending(self, _):
        self.deploy()
        self.batch(3)
        rec = ContractLabourHalfYearlyReturn.objects.create(
            company=self.c1, contractor=self.con, year=YEAR, half_year='jan_jun')
        cid = self.con.pk
        self.post(f'{BASE}contractors/{cid}/returns/{rec.pk}/recompute/')
        rec.refresh_from_db()
        self.assertEqual(rec.total_workers_employed, 1)
        self.assertGreater(rec.total_wages_paid, 0)
        self.post(f'{BASE}contractors/{cid}/returns/{rec.pk}/delete/')
        self.assertFalse(ContractLabourHalfYearlyReturn.objects.exists())

    # -- service module ----------------------------------------------------------------
    def test_payment_register_empty_raises(self):
        with self.assertRaisesMessage(NothingToGenerate, 'No payment records found for this contractor.'):
            cl.build_contractor_payment_register_pdf(self.c1, self.con)

    def test_service_filenames_and_pdf_magic(self):
        rec = ContractLabourHalfYearlyReturn.objects.create(
            company=self.c1, contractor=self.con, year=YEAR, half_year='jul_dec')
        pdf, fname = cl.build_cl_return_pdf(self.c1, rec)
        self.assertEqual(fname, 'CL_Return_Acme_Works_2026_jul_dec.pdf')
        self.assertTrue(pdf.startswith(b'%PDF'))
