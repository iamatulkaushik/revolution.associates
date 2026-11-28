import io
from datetime import date
from decimal import Decimal as D

import openpyxl
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.branch_department import branch, department
from Aapp.app.designation import designation
from Aapp.app.employee import employee
from Aapp.app.salary_processing import salary_processing, salary_slip
from Capp.bank_export import apply_month, build_rows, group_by_bank, render_file, seed_canara
from Capp.billing_models import BankFormat, EmployeeDeduction
from Capp.models import CompanyOwnerProfile
from Capp.tests_masters import make_company

HOST = {'HTTP_HOST': 'capp.localhost'}
ZERO = {f: D('0') for f in (
    'dailywage', 'basicpay', 'hra', 'da', 'medicalallowance', 'conveyance', 'lunchallowance', 'cca',
    'specialallowance', 'travelallowance', 'washingallowance', 'cycleallowance', 'other1', 'other2',
    'ed_epf_per', 'ed_esi_per', 'ed_labourwelfare_per', 'ed_epf_amount', 'ed_esi_amount',
    'ed_labourwelfare_amount', 'ed_professionaltax', 'ed_income_tax', 'er_epf_per', 'er_esi_per',
    'er_labourwelfare_per', 'er_epf_amount', 'er_esi_amount', 'er_labourwelfare_amount')}


@override_settings(ALLOWED_HOSTS=['*'])
class BankExportTests(TestCase):
    def setUp(self):
        self.co = make_company('JSK', 'AAAAA1111A')
        self.co.plan = 'gold'; self.co.save()                      # bank_file is a Gold feature
        self.user = User.objects.create_user('owner', password='x')
        CompanyOwnerProfile.objects.create(user=self.user, company=self.co)
        self.client.login(username='owner', password='x')
        br = branch.objects.create(branch_name='Murthal', companyid=self.co, created_by=self.user)
        dp = department.objects.create(department_name='S.P', branch=br, companyid=self.co,
                                       created_by=self.user)
        ds = designation.objects.create(designationname='Helper', company=self.co,
                                        created_by='t', updated_by='t', **ZERO)
        self.batch = salary_processing.objects.create(company_id=self.co, month=11, year=2026)
        self.emps = []
        for i, (ifsc, net) in enumerate([('CNRB0018281', '18375.8425'), ('BARB0SIKAND', '19423.8425')]):
            e = employee.objects.create(
                employeecode=f'110{i}', name=f'EMP{i}', fathername='F', gender='Male',
                dateofbirth=date(1990, 1, 1), temporaryaddress='SNP HR', mobile=f'900000000{i}',
                email=f'e{i}@x.com', aadhar_number=f'11112222333{i}', aadhar_name='x',
                bank_name='B', bank_account=f'12345678901{i}', bank_ifsc=ifsc,
                dateofjoining=date(2020, 1, 1), designationID=ds, departmentID=dp, branchID=br,
                CompanyID=self.co, temp_state=None)
            salary_slip.objects.create(processing_id=self.batch, employee_id=e, company_id=self.co,
                                       net_pay=D(net))
            self.emps.append(e)

    def slips(self):
        return salary_slip.objects.filter(company_id=self.co).select_related(
            'employee_id', 'employee_id__departmentID')

    def test_rows_round_up_and_group(self):
        rows = build_rows(self.slips(), self.co, 2026, 11)
        g = group_by_bank(rows)
        self.assertEqual(list(g), ['BARB', 'CNRB'])
        self.assertEqual(g['CNRB'][0]['net_pay'], D('18376'))
        self.assertEqual(g['BARB'][0]['net_pay'], D('19424'))

    def test_deductions_once_and_recurring(self):
        e = self.emps[1]
        mk = lambda **k: EmployeeDeduction.objects.create(
            company=self.co, employee=e, start_month=date(2026, 11, 1), **k)
        mk(title='Advance', kind='RECURRING', total_amount=D('9000'), emi_amount=D('4600'), balance=D('9000'))
        mk(title='Shoes', kind='ONCE', total_amount=D('500'), balance=D('500'))
        rows = build_rows(self.slips(), self.co, 2026, 11)
        # 19423.8425 - 4600 - 500 = 14323.8425 -> 14324
        self.assertEqual([r for r in rows if r['ifsc'].startswith('BARB')][0]['net_pay'], D('14324'))
        # December: only the recurring EMI applies
        rows = build_rows(self.slips(), self.co, 2026, 12)
        self.assertEqual([r for r in rows if r['ifsc'].startswith('BARB')][0]['net_pay'], D('14824'))

    def test_canara_xlsx_layout(self):
        fmt = seed_canara(self.co)
        rows = group_by_bank(build_rows(self.slips(), self.co, 2026, 11))['CNRB']
        data, name, _ = render_file(fmt, rows, {})
        ws = openpyxl.load_workbook(io.BytesIO(data)).active
        first = [c.value for c in ws[1]]
        self.assertEqual(first[1:3], ['1100', 'EMP0'])
        self.assertEqual(first[5], 'CNRB0018281')
        self.assertEqual(first[9], 18376)          # whole rupee, int
        self.assertEqual(first[10], 'B.T')
        self.assertEqual(ws.cell(row=2, column=10).value, 18376)   # total row

    def test_fallback_csv_and_txt(self):
        rows = group_by_bank(build_rows(self.slips(), self.co, 2026, 11))['BARB']
        data, name, _ = render_file(None, rows)
        self.assertTrue(name.endswith('.csv'))
        self.assertIn('19424', data.decode())
        fmt = BankFormat.objects.create(company=self.co, bank_name='X', ifsc_prefix='BARB',
                                        file_type='TXT', delimiter='|', has_header=False)
        fmt.columns.create(position=1, source='account', width=16)
        fmt.columns.create(position=2, source='net_pay')
        data, name, _ = render_file(fmt, rows)
        self.assertEqual(data.decode().split('|')[1], '19424')
        self.assertEqual(len(data.decode().split('|')[0]), 16)

    def test_views(self):
        self.assertEqual(self.client.post('/masters/bank-formats/', {'seed_canara': '1'}, **HOST).status_code, 302)
        self.assertEqual(self.client.get('/masters/bank-formats/', **HOST).status_code, 200)
        r = self.client.get('/wages/bank-file/?month=11&year=2026', **HOST)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'CNRB')
        d = self.client.get('/wages/bank-file/?month=11&year=2026&bank=CNRB', **HOST)
        self.assertIn('spreadsheetml', d['Content-Type'])
        d = self.client.get('/wages/bank-file/?month=11&year=2026&bank=BARB', **HOST)
        self.assertIn('text/csv', d['Content-Type'])

    def test_apply_month_idempotent_and_closes(self):
        e = self.emps[1]
        d = EmployeeDeduction.objects.create(company=self.co, employee=e, title='Advance',
            kind='RECURRING', total_amount=D('9000'), emi_amount=D('4600'), balance=D('9000'),
            start_month=date(2026, 11, 1))
        self.assertEqual(apply_month(self.co, 2026, 11), 1)
        self.assertEqual(apply_month(self.co, 2026, 11), 0)       # same month: no double cut
        d.refresh_from_db(); self.assertEqual(d.balance, D('4400'))
        self.assertEqual(apply_month(self.co, 2026, 12), 1)       # last EMI capped at balance
        d.refresh_from_db(); self.assertEqual(d.balance, D('0')); self.assertTrue(d.is_closed)

    def test_deduction_and_client_screens(self):
        e = self.emps[0]
        r = self.client.post('/billing/deductions/add/', {
            'employee': e.pk, 'title': 'Shoes', 'kind': 'ONCE', 'total_amount': '500',
            'start_month': '2026-11'}, **HOST)
        self.assertEqual(r.status_code, 302, r.content[:400])
        d = EmployeeDeduction.objects.get(title='Shoes')
        self.assertEqual((d.balance, d.start_month, d.company), (D('500'), date(2026, 11, 1), self.co))
        bad = self.client.post('/billing/deductions/add/', {
            'employee': e.pk, 'title': 'Loan', 'kind': 'RECURRING', 'total_amount': '100',
            'emi_amount': '500', 'start_month': '2026-11'}, **HOST)
        self.assertEqual(bad.status_code, 200)
        r = self.client.post('/billing/clients/add/', {
            'name': 'TOYO', 'gstin': '06AAAAA0000A1Z5', 'service_charge_pct': '5', 'gst_pct': '18',
            'esi_base': 'GROSS', 'is_active': 'on'}, **HOST)
        self.assertEqual(r.status_code, 302, r.content[:400])
        for u in ('/billing/deductions/', '/billing/clients/'):
            self.assertEqual(self.client.get(u, **HOST).status_code, 200)
        d.last_applied = date(2026, 11, 1); d.save()
        self.client.post(f'/billing/deductions/{d.pk}/delete/', **HOST)
        self.assertTrue(EmployeeDeduction.objects.filter(pk=d.pk).exists())


@override_settings(ALLOWED_HOSTS=['*'])
class BankPlanGateTests(TestCase):
    def test_copper_and_silver_are_refused_gold_is_allowed(self):
        co = make_company('JSK', 'AAAAA1111A')
        u = User.objects.create_user('owner', password='pw-Strong-1')
        CompanyOwnerProfile.objects.create(user=u, company=co)
        self.client.login(username='owner', password='pw-Strong-1')
        urls = ('/masters/bank-formats/', '/masters/bank-formats/add/', '/wages/bank-file/')
        for plan in ('copper', 'silver'):
            type(co).objects.filter(pk=co.pk).update(plan=plan)
            for url in urls:
                r = self.client.get(url, **HOST)
                self.assertEqual(r.status_code, 302, (plan, url))
                self.assertEqual(r.url, '/dashboard/')
            labels = {i['label'] for g in self.client.get('/dashboard/', **HOST).context['capp_nav']
                      for i in g.get('items', [])}
            self.assertNotIn('Bank Payment Files', labels)
        type(co).objects.filter(pk=co.pk).update(plan='gold')
        for url in urls:
            self.assertEqual(self.client.get(url, **HOST).status_code, 200, url)
