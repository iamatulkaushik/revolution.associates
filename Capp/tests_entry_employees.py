"""E1: employee add / edit / reactivate in Capp."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.branch_department import branch, department
from Aapp.app.designation import designation
from Aapp.app.employee import employee
from Capp.foundation.models import CappAuditLog, CompanyOperator
from Capp.models import CompanyOwnerProfile
from Capp.tests_foundation import make_employee
from Capp.tests_masters import make_company
from Sapp.app.license import License
from Sapp.app.state_district import District, State

HOST = {'HTTP_HOST': 'capp.localhost'}


@override_settings(ALLOWED_HOSTS=['*'])
class EmployeeEntryTests(TestCase):
    def setUp(self):
        self.co = make_company('JSK', 'AAAAA1111A')
        self.other = make_company('Other', 'BBBBB2222B')
        self.owner = User.objects.create_user('owner', password='pw-Strong-1')
        CompanyOwnerProfile.objects.create(user=self.owner, company=self.co)
        self.client.login(username='owner', password='pw-Strong-1')
        seed = make_employee(self.co, '900')                       # gives us branch, dept, designation
        self.br, self.dp, self.ds = seed.branchID, seed.departmentID, seed.designationID
        seed.delete()

    def data(self, **kw):
        d = {
            'employeecode': '11001', 'name': 'mohd osama', 'gender': 'Male',
            'dateofbirth': '2000-01-01', 'mobile': '9936100163', 'temporaryaddress': 'SONIPAT',
            'aadhar_number': '990316397256', 'aadhar_name': 'MOHD OSAMA', 'bank_name': 'BOB',
            'bank_account': '14288100020591', 'bank_ifsc': 'barb0sikand',
            'dateofjoining': '2026-04-09', 'employment_type': 'Permanent',
            'designationID': self.ds.pk, 'departmentID': self.dp.pk, 'branchID': self.br.pk,
        }
        d.update(kw)
        return d

    def add(self, **kw):
        return self.client.post('/entry/employees/add/', self.data(**kw), **HOST)

    def test_add_creates_in_own_company_and_audits(self):
        r = self.add()
        self.assertEqual(r.status_code, 302, getattr(r, 'context', None) and r.context['form'].errors)
        e = employee.objects.get(employeecode='11001')
        self.assertEqual((e.CompanyID, e.name, e.bank_ifsc, e.is_working),
                         (self.co, 'MOHD OSAMA', 'BARB0SIKAND', True))
        self.assertIsNone(e.pan_number)
        self.assertTrue(CappAuditLog.objects.filter(action='create', model='employee').exists())

    def test_two_employees_without_pan_are_fine(self):
        self.add()
        r = self.add(employeecode='11002', mobile='9936100164', aadhar_number='990316397257',
                     bank_account='14288100020592')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(employee.objects.filter(pan_number__isnull=True).count(), 2)

    def test_validation_errors(self):
        for field, value in (('aadhar_number', '12345'), ('mobile', '99'), ('bank_ifsc', 'BAD'),
                             ('bank_account', '12'), ('pan_number', 'ZZZ'),
                             ('dateofjoining', '1990-01-01'), ('employeecode', '')):
            r = self.add(**{field: value})
            self.assertEqual(r.status_code, 200, field)
            self.assertIn(field, r.context['form'].errors, field)
        self.assertEqual(employee.objects.count(), 0)

    def test_duplicates_rejected(self):
        self.add()
        for field in ('employeecode', 'aadhar_number', 'mobile', 'bank_account'):
            r = self.add(**{field: self.data()[field]})
            self.assertEqual(r.status_code, 200, field)
        self.assertEqual(employee.objects.count(), 1)

    def test_department_must_belong_to_branch(self):
        b2 = branch.objects.create(branch_name='Other branch', companyid=self.co, created_by=self.owner)
        r = self.add(branchID=b2.pk)
        self.assertEqual(r.status_code, 200)
        self.assertIn('departmentID', r.context['form'].errors)

    def test_contract_needs_dates(self):
        r = self.add(employment_type='Contract')
        self.assertIn('contract_end_date', r.context['form'].errors)
        r = self.add(employment_type='Contract', contract_start_date='2026-04-01',
                     contract_end_date='2027-03-31')
        self.assertEqual(r.status_code, 302)

    def test_other_company_masters_not_selectable(self):
        ob = branch.objects.create(branch_name='Theirs', companyid=self.other, created_by=self.owner)
        r = self.add(branchID=ob.pk)
        self.assertEqual(r.status_code, 200)
        self.assertIn('branchID', r.context['form'].errors)

    def test_plan_limit_blocks_add_with_message(self):
        License.objects.create(company=self.co, license_type='basic', license_key='K1',
                               issue_date=date.today(), max_employees=1)
        self.assertEqual(self.add().status_code, 302)
        r = self.add(employeecode='11002', mobile='9936100164', aadhar_number='990316397257',
                     bank_account='14288100020592')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Upgrade the plan')
        self.assertEqual(employee.objects.count(), 1)

    def test_edit_keeps_code_and_saves_changes(self):
        self.add()
        e = employee.objects.get()
        r = self.client.post(f'/entry/employees/{e.pk}/edit/', self.data(
            employeecode='HACK', name='new name', mobile='9936100199'), **HOST)
        self.assertEqual(r.status_code, 302)
        e.refresh_from_db()
        self.assertEqual((e.employeecode, e.name, e.mobile), ('11001', 'NEW NAME', '9936100199'))

    def test_edit_other_tenant_is_404(self):
        theirs = make_employee(self.other, '55')
        self.assertEqual(self.client.get(f'/entry/employees/{theirs.pk}/edit/', **HOST).status_code, 404)
        self.assertEqual(self.client.post(f'/entry/employees/{theirs.pk}/edit/', self.data(), **HOST).status_code, 404)
        self.assertEqual(self.client.post(f'/entry/employees/{theirs.pk}/reactivate/', **HOST).status_code, 404)

    def test_operator_permissions(self):
        u = User.objects.create_user('op', password='pw-Strong-1')
        op = CompanyOperator.objects.create(user=u, company=self.co, can_view_employees=True)
        self.client.login(username='op', password='pw-Strong-1')
        self.assertEqual(self.client.get('/entry/employees/add/', **HOST).status_code, 302)
        self.assertEqual(self.client.post('/entry/employees/add/', self.data(), **HOST).status_code, 403)
        op.can_add_employees = True
        op.save()
        self.assertEqual(self.client.post('/entry/employees/add/', self.data(), **HOST).status_code, 302)
        self.assertTrue(CappAuditLog.objects.filter(role='OPERATOR', action='create').exists())

    def test_operator_can_update_esi_epf_uan_numbers(self):
        self.add()
        emp = employee.objects.get()
        u = User.objects.create_user('op2', password='pw-Strong-1')
        CompanyOperator.objects.create(user=u, company=self.co, can_view_employees=True,
                                       can_add_employees=True)
        self.client.login(username='op2', password='pw-Strong-1')
        r = self.client.post(f'/entry/employees/{emp.pk}/edit/', self.data(
            uan_number='102160135945', epf_memberID='HRGGN0012345000000123', esic_number='1328512881'), **HOST)
        self.assertEqual(r.status_code, 302)
        emp.refresh_from_db()
        self.assertEqual((emp.uan_number, emp.esic_number, emp.epf_memberID),
                         ('102160135945', '1328512881', 'HRGGN0012345000000123'))
        bad = self.client.post(f'/entry/employees/{emp.pk}/edit/', self.data(esic_number='12345'), **HOST)
        self.assertIn('esic_number', bad.context['form'].errors)

    def test_reactivate_counts_toward_limit(self):
        e = make_employee(self.co, '77', working=False)
        License.objects.create(company=self.co, license_type='basic', license_key='K2',
                               issue_date=date.today(), max_employees=1)
        make_employee(self.co, '78')                              # fills the only seat
        self.assertEqual(self.client.get(f'/entry/employees/{e.pk}/reactivate/', **HOST).status_code, 302)
        e.refresh_from_db(); self.assertFalse(e.is_working)       # GET never changes data
        self.client.post(f'/entry/employees/{e.pk}/reactivate/', **HOST)
        e.refresh_from_db(); self.assertFalse(e.is_working)       # blocked by the limit
        employee.objects.filter(employeecode='78').update(is_working=False)
        self.client.post(f'/entry/employees/{e.pk}/reactivate/', **HOST)
        e.refresh_from_db(); self.assertTrue(e.is_working)
        self.assertTrue(CappAuditLog.objects.filter(action='reactivate').exists())

    def test_relieved_page_and_districts_json(self):
        make_employee(self.co, '90', working=False)
        self.assertContains(self.client.get('/entry/employees/relieved/', **HOST), 'E90')
        st = State.objects.get(name='Haryana')
        dist = District.objects.filter(state=st).first()
        j = self.client.get(f'/entry/districts/?state={st.pk}', **HOST).json()
        self.assertIn(dist.name, [d['name'] for d in j['districts']])
        self.assertEqual(self.client.get('/entry/districts/?state=x', **HOST).json(), {'districts': []})

    def test_list_page_links_follow_permissions_and_shows_real_columns(self):
        make_employee(self.co, '20')
        r = self.client.get('/employees/', **HOST)
        self.assertContains(r, 'Add employee')
        self.assertContains(r, '/edit/')
        self.assertContains(r, 'H</td>')                           # designation name now shown
        self.assertContains(r, '01-01-2020')                       # joining date now shown
        u = User.objects.create_user('ro', password='pw-Strong-1')
        CompanyOperator.objects.create(user=u, company=self.co, can_view_employees=True)
        self.client.login(username='ro', password='pw-Strong-1')
        r = self.client.get('/employees/', **HOST)
        self.assertNotContains(r, 'Add employee')
        self.assertContains(r, 'Read-only view')
