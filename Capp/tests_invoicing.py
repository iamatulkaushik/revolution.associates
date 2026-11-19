from datetime import date
from decimal import Decimal as D

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.branch_department import branch, department
from Aapp.app.designation import designation
from Aapp.app.employee import employee
from Aapp.app.salary_processing import salary_processing, salary_slip
from Capp.billing_models import BillingClient, ClientEmployee, Invoice
from Capp.invoicing import InvoiceError, financial_year, generate_invoice
from Capp.models import CompanyOwnerProfile
from Capp.tests_bank_export import ZERO
from Capp.tests_masters import make_company
from Sapp.app.company import company_statury

HOST = {'HTTP_HOST': 'capp.localhost'}


@override_settings(ALLOWED_HOSTS=['*'])
class InvoiceTests(TestCase):
    """Owner's sample employee: basic 15221, HRA 2779, bonus 2000, OT 40h = 6000."""

    def setUp(self):
        self.co = make_company('JSK', 'AAAAA1111A')
        company_statury.objects.create(company=self.co, epfo='HR/X/1', esic='1234567890', labour='L1')
        self.user = User.objects.create_user('owner', password='x')
        CompanyOwnerProfile.objects.create(user=self.user, company=self.co)
        self.client.login(username='owner', password='x')
        br = branch.objects.create(branch_name='M', companyid=self.co, created_by=self.user)
        dp = department.objects.create(department_name='S.P', branch=br, companyid=self.co,
                                       created_by=self.user)
        ds = designation.objects.create(designationname='Helper', company=self.co,
                                        created_by='t', updated_by='t', **ZERO)
        self.emp = employee.objects.create(
            employeecode='11001', name='MOHD OSAMA', fathername='F', gender='Male',
            dateofbirth=date(1990, 1, 1), temporaryaddress='X', mobile='9936100163',
            email='e@x.com', aadhar_number='111122223333', aadhar_name='x', bank_name='B',
            bank_account='14288100020591', bank_ifsc='BARB0SIKAND', dateofjoining=date(2020, 1, 1),
            designationID=ds, departmentID=dp, branchID=br, CompanyID=self.co)
        batch = salary_processing.objects.create(company_id=self.co, month=11, year=2026)
        salary_slip.objects.create(
            processing_id=batch, employee_id=self.emp, company_id=self.co, designation_id=ds,
            paid_days=D('30'), overtime_hours=D('40'), basic_earned=D('15221'), hra_earned=D('2779'),
            overtime_amount=D('6000'), bonus_amount=D('2000'), gross_earnings=D('26000'),
            net_pay=D('24023.8425'))
        self.cl = BillingClient.objects.create(company=self.co, name='TOYO', esi_base='BASIC',
                                               service_charge_pct=D('5'), gst_pct=D('18'))
        ClientEmployee.objects.create(company=self.co, client=self.cl, employee=self.emp)

    def test_salary_and_ot_match_owner_sheet(self):
        s = generate_invoice(self.co, self.cl, 'SALARY', 2026, 11)
        self.assertEqual(s.total, D('27663.55'))
        self.assertEqual(s.lines.count(), 1)
        o = generate_invoice(self.co, self.cl, 'OT', 2026, 11)
        self.assertEqual(o.total, D('7434.00'))
        self.assertEqual((s.number, o.number), (f'INV/2026-27/0001'.replace('2026-27', s.fy),
                                                f'INV/{o.fy}/0002'))

    def test_gates_fail_closed(self):
        company_statury.objects.filter(company=self.co).update(esic=None)
        inv = generate_invoice(self.co, self.cl, 'SALARY', 2026, 11)
        self.assertEqual(inv.esi_employer, 0)

    def test_duplicate_and_empty(self):
        generate_invoice(self.co, self.cl, 'SALARY', 2026, 11)
        with self.assertRaises(InvoiceError):
            generate_invoice(self.co, self.cl, 'SALARY', 2026, 11)
        with self.assertRaises(InvoiceError):
            generate_invoice(self.co, self.cl, 'SALARY', 2026, 10)      # no slips

    def test_extra_charge_conveyance(self):
        inv = generate_invoice(self.co, self.cl, 'OT', 2026, 11, extra_label='Conveyance',
                               extra_charges=D('5360'))
        self.assertEqual(inv.total, D('12794.00'))

    def test_fy(self):
        self.assertEqual(financial_year(date(2027, 3, 31)), '2026-27')
        self.assertEqual(financial_year(date(2027, 4, 1)), '2027-28')

    def test_screens_pdf_xlsx_and_payment(self):
        r = self.client.post('/billing/invoices/generate/', {
            'client': self.cl.pk, 'kind': 'SALARY', 'month': '2026-11'}, **HOST)
        self.assertEqual(r.status_code, 302, r.content[:400])
        inv = Invoice.objects.get()
        self.assertEqual(self.client.get('/billing/invoices/', **HOST).status_code, 200)
        self.assertEqual(self.client.get(f'/billing/invoices/{inv.pk}/', **HOST).status_code, 200)
        pdf = self.client.get(f'/billing/invoices/{inv.pk}/download/pdf/', **HOST)
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        x = self.client.get(f'/billing/invoices/{inv.pk}/download/xlsx/', **HOST)
        self.assertEqual(x.content[:2], b'PK')
        self.client.post(f'/billing/invoices/{inv.pk}/do/issue/', **HOST)
        inv.refresh_from_db(); self.assertEqual(inv.status, 'ISSUED')
        self.client.post(f'/billing/invoices/{inv.pk}/do/payment/', {
            'received_amount': '25000', 'tds_amount': '400', 'received_on': '2026-12-05',
            'payment_ref': 'UTR1'}, **HOST)
        inv.refresh_from_db()
        self.assertEqual(inv.outstanding, D('2263.55'))
        self.client.post(f'/billing/invoices/{inv.pk}/do/payment/', {
            'received_amount': '99999', 'tds_amount': '0'}, **HOST)
        inv.refresh_from_db(); self.assertEqual(inv.received_amount, D('25000'))   # over-payment rejected
        self.client.post(f'/billing/invoices/{inv.pk}/do/cancel/', **HOST)
        inv.refresh_from_db(); self.assertEqual(inv.status, 'ISSUED')               # has payment: no cancel

    def test_client_employee_mapping_moves(self):
        other = BillingClient.objects.create(company=self.co, name='OTHER')
        r = self.client.post(f'/billing/clients/{other.pk}/edit/', {
            'name': 'OTHER', 'service_charge_pct': '5', 'gst_pct': '18', 'esi_base': 'GROSS',
            'is_active': 'on', 'employees': [self.emp.pk]}, **HOST)
        self.assertEqual(r.status_code, 302, r.content[:300])
        self.assertEqual(ClientEmployee.objects.get(employee=self.emp).client, other)
