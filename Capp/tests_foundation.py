"""AI-1 (Foundation) acceptance tests: matrix, licence limit, mode guard, operators, menu, audit."""
import io
from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.forms import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from Aapp.app.branch_department import branch, department
from Aapp.app.designation import designation
from Aapp.app.employee import employee
from Aapp.app.salary_processing import salary_processing
from Capp import access
from Capp.audit import log_action
from Capp.foundation.models import CappAuditLog, CompanyOperator
from Capp.models import CompanyOwnerProfile
from Capp.tests_bank_export import ZERO
from Capp.tests_import import good, workbook
from Capp.tests_masters import make_company
from revolution.app import plan_limits as pl
from Sapp.app.company import create_company_form_superadmin
from Sapp.app.license import License

HOST = {'HTTP_HOST': 'capp.localhost'}
ALL_FLAGS = ['can_view_employees', 'can_view_attendance', 'can_view_wages', 'can_view_compliance',
             'can_view_reports', 'can_view_statutory', 'can_download_pdf', 'can_add_employees',
             'can_edit_attendance', 'can_edit_loans', 'can_download_payroll',
             'can_download_challans', 'can_manage_masters', 'can_manage_billing']

# Independent copy of master plan section 4: (DIRECT-O, DIRECT-Op, ASSOC-O, ASSOC-Op)
#   Y = allowed, N = never, F = operator flag decides
EXPECT = {
    'employees.view': 'YFYF', 'employees.add': 'YFYF', 'employees.edit': 'YFYF',
    'employees.relieve': 'YNNN', 'attendance.view': 'YFYF', 'attendance.edit': 'YFYF',
    'loans.view': 'YFYF', 'loans.edit': 'YFYF', 'payroll.process': 'YNNN',
    'payroll.finalize': 'YNNN', 'payroll.download': 'YFYF', 'statutory.edit': 'YNNN',
    'challan.download': 'YFNN', 'bank.edit': 'YNNN', 'masters.edit': 'YFYN',
    'billing.manage': 'YFYN', 'operators.manage': 'YNYN', 'wages.view': 'YFYF',
    'statutory.view': 'YFYF', 'compliance.view': 'YFYF', 'reports.view': 'YFYF',
}


def profile(flag_value, role):
    p = SimpleNamespace(can_access_system=lambda: True)
    for f in ALL_FLAGS:
        setattr(p, f, flag_value)
    return p


class MatrixTests(SimpleTestCase):
    def test_every_permission_has_an_expectation(self):
        self.assertEqual(set(EXPECT), set(access.PERMISSIONS))

    def test_matrix_cells(self):
        cols = [('DIRECT', 'OWNER'), ('DIRECT', 'OPERATOR'), ('ASSOCIATE', 'OWNER'),
                ('ASSOCIATE', 'OPERATOR')]
        for perm, row in EXPECT.items():
            for (mode, role), cell in zip(cols, row):
                on = access.compute_perms(mode, role, profile(True, role))
                off = access.compute_perms(mode, role, profile(False, role))
                if cell == 'Y':
                    self.assertIn(perm, on, (perm, mode, role, 'flags on'))
                elif cell == 'F':
                    self.assertIn(perm, on, (perm, mode, role, 'flags on'))
                    self.assertNotIn(perm, off, (perm, mode, role, 'flags off'))
                else:
                    self.assertNotIn(perm, on, (perm, mode, role, 'never'))

    def test_inactive_profile_holds_nothing(self):
        dead = SimpleNamespace(can_access_system=lambda: False, **{f: True for f in ALL_FLAGS})
        self.assertEqual(access.compute_perms('DIRECT', 'OWNER', dead), set())
        self.assertEqual(access.compute_perms('DIRECT', None, profile(True, 'OWNER')), set())


def make_employee(co, code, working=True, n=0):
    br = branch.objects.filter(companyid=co).first() or branch.objects.create(
        branch_name='B', companyid=co, created_by=User.objects.first())
    dp = department.objects.filter(companyid=co).first() or department.objects.create(
        department_name='D', branch=br, companyid=co, created_by=User.objects.first())
    ds = designation.objects.filter(company=co).first() or designation.objects.create(
        designationname='H', company=co, created_by='t', updated_by='t', **ZERO)
    return employee.objects.create(
        employeecode=code, name=f'E{code}', fathername='F', gender='Male', dateofbirth=date(1990, 1, 1),
        temporaryaddress='X', mobile=f'9{int(code):09d}', email='e@x.com',
        aadhar_number=f'{int(code):012d}', aadhar_name='x', bank_name='B',
        bank_account=f'{int(code):012d}', bank_ifsc='BARB0SIKAND', dateofjoining=date(2020, 1, 1),
        designationID=ds, departmentID=dp, branchID=br, CompanyID=co, is_working=working)


@override_settings(ALLOWED_HOSTS=['*'])
class FoundationBase(TestCase):
    def setUp(self):
        self.co = make_company('JSK', 'AAAAA1111A')
        self.other = make_company('Other', 'BBBBB2222B')
        self.owner = User.objects.create_user('owner', password='pw-Strong-1')
        self.profile = CompanyOwnerProfile.objects.create(user=self.owner, company=self.co)

    def operator(self, name='op1', company=None, **flags):
        u = User.objects.create_user(name, password='pw-Strong-1')
        return CompanyOperator.objects.create(user=u, company=company or self.co, **flags)

    def login(self, name):
        self.client.logout()
        self.assertTrue(self.client.login(username=name, password='pw-Strong-1'))


class LimitTests(FoundationBase):
    def lic(self, co, **kw):
        return License.objects.create(company=co, license_type='basic', license_key=f'K{co.pk}',
                                      issue_date=date.today(), **kw)

    def test_licence_limit_beats_plan_default(self):
        self.lic(self.co, max_employees=3)
        self.assertEqual(pl.employee_limit(self.co), 3)

    def test_no_licence_copper_150_other_unlimited(self):
        self.assertEqual(pl.employee_limit(self.co), 150)
        self.other.plan = 'gold'
        self.assertIsNone(pl.employee_limit(self.other))

    def test_licence_null_means_unlimited(self):
        self.lic(self.co, max_employees=None)
        self.assertIsNone(pl.employee_limit(self.co))

    def test_expired_or_suspended_licence_ignored(self):
        l = self.lic(self.co, max_employees=2)
        l.suspend('test')
        self.assertEqual(pl.employee_limit(self.co), 150)

    def test_only_adding_is_blocked_and_relieving_frees_room(self):
        self.lic(self.co, max_employees=3)
        for i in (1, 2, 3):
            make_employee(self.co, str(i))
        with self.assertRaises(pl.PlanLimitExceeded):
            pl.check_can_add(self.co)
        employee.objects.filter(employeecode='3').update(is_working=False)
        pl.check_can_add(self.co)                      # room again
        with self.assertRaises(pl.PlanLimitExceeded):
            pl.check_can_add(self.co, 2)
        # existing employees are untouched even when over the limit
        License.objects.filter(company=self.co).update(max_employees=1)
        self.assertEqual(pl.active_employee_count(self.co), 2)
        self.assertEqual(pl.remaining(self.co), 0)

    def test_aapp_create_and_enable_paths_use_the_limit(self):
        from Aapp.app.employee import _limit_error
        self.lic(self.co, max_employees=1)
        make_employee(self.co, '1')
        msg = _limit_error(self.co)
        self.assertIn('Upgrade the plan', msg)
        self.assertIn('1 active', msg)

    def test_import_preview_flags_rows_beyond_room(self):
        self.lic(self.co, max_employees=3)
        br = branch.objects.create(branch_name='M', companyid=self.co, created_by=self.owner)
        make_employee(self.co, '900')                       # 1 used, 2 left
        rows = []
        for i in range(5):
            r = good(code=11001 + i, acc=f'1428810002059{i}', aad=f'99031639725{i}',
                     mob=9936100160 + i)
            rows.append(r)
        wb = workbook(rows, bank_rows=False)
        for r in rows:
            pass
        # add IFSC through a bank sheet so rows are otherwise valid
        import openpyxl
        w = openpyxl.load_workbook(io.BytesIO(wb.getvalue()))
        bk = w.create_sheet('bank')
        bk.append(['x', 'ID No.', 'IFSC'])
        for i in range(5):
            bk.append([None, 11001 + i, 'BARB0SIKAND'])
        buf = io.BytesIO(); w.save(buf)
        self.login('owner')
        r = self.client.post('/masters/import/employees/', {
            'file': SimpleUploadedFile('d.xlsx', buf.getvalue()), 'branch': br.pk, 'gender': 'Male'},
            **HOST)
        self.assertEqual(r.status_code, 200)
        rows = r.context['rows']
        self.assertEqual(sum(1 for x in rows if not x['issues']), 2)
        self.assertEqual(sum(1 for x in rows if any('Plan limit' in i for i in x['issues'])), 3)

    def test_backfill_command(self):
        l1 = self.lic(self.co)                               # copper -> 150
        self.other.plan = 'gold'; self.other.save()
        l2 = License.objects.create(company=self.other, license_type='basic', license_key='K9',
                                    issue_date=date.today())
        out = io.StringIO()
        call_command('backfill_license_max_employees', stdout=out)   # dry run
        l1.refresh_from_db(); self.assertIsNone(l1.max_employees)
        call_command('backfill_license_max_employees', '--apply', stdout=out)
        l1.refresh_from_db(); l2.refresh_from_db()
        self.assertEqual(l1.max_employees, 150)
        self.assertIsNone(l2.max_employees)                  # gold: unlimited stays blank


class ModeGuardTests(FoundationBase):
    def form(self, mode):
        f = create_company_form_superadmin(instance=self.co)
        f.cleaned_data = {'management_mode': mode}
        return f

    def test_default_is_associate(self):
        self.assertEqual(self.co.management_mode, 'ASSOCIATE')

    def test_change_allowed_without_open_batch(self):
        self.assertEqual(self.form('DIRECT').clean_management_mode(), 'DIRECT')

    def test_change_blocked_while_batch_open(self):
        for status in ('DRAFT', 'PROCESSED'):
            b = salary_processing.objects.create(company_id=self.co, month=11, year=2026, status=status)
            with self.assertRaises(ValidationError):
                self.form('DIRECT').clean_management_mode()
            b.delete()

    def test_approved_batches_are_closed_history(self):
        # Aapp never sets PAID, so APPROVED must not block a mode change forever.
        for status in ('APPROVED', 'PAID'):
            salary_processing.objects.create(company_id=self.co, month=10, year=2026, status=status)
            self.assertEqual(self.form('DIRECT').clean_management_mode(), 'DIRECT')
            salary_processing.objects.all().delete()


class OperatorTests(FoundationBase):
    def test_operator_login_and_suspension(self):
        op = self.operator()
        r = self.client.post('/login/', {'username': 'op1', 'password': 'pw-Strong-1'}, **HOST)
        self.assertEqual(r.status_code, 302)
        self.client.logout()
        op.is_active = False; op.save()
        r = self.client.post('/login/', {'username': 'op1', 'password': 'pw-Strong-1'}, **HOST)
        self.assertEqual(r.status_code, 200)                  # stays on the login page
        self.login('op1')                                     # session exists but account is suspended
        self.assertEqual(self.client.get('/employees/', **HOST).status_code, 302)

    def test_owner_can_reenable(self):
        op = self.operator(is_active=False)
        self.login('owner')
        self.client.post(f'/admin-tools/operators/{op.pk}/toggle/', **HOST)
        op.refresh_from_db(); self.assertTrue(op.is_active)

    def test_owner_creates_operator_with_password_rules(self):
        self.login('owner')
        r = self.client.post('/admin-tools/operators/add/', {
            'username': 'newop', 'password': '123', 'can_view_employees': 'on'}, **HOST)
        self.assertEqual(r.status_code, 200)                  # weak password rejected
        r = self.client.post('/admin-tools/operators/add/', {
            'username': 'newop', 'password': 'Tr1cky-pass-77', 'full_name': 'New Op',
            'can_view_employees': 'on', 'can_edit_attendance': 'on'}, **HOST)
        self.assertEqual(r.status_code, 302)
        op = CompanyOperator.objects.get(user__username='newop')
        self.assertEqual((op.company, op.created_by, op.can_edit_attendance), (self.co, self.owner, True))
        self.assertTrue(CappAuditLog.objects.filter(action='operator_create', username='owner').exists())

    def test_masters_billing_flags_ignored_in_associate_mode(self):
        self.login('owner')
        self.client.post('/admin-tools/operators/add/', {
            'username': 'm', 'password': 'Tr1cky-pass-77', 'can_manage_masters': 'on',
            'can_manage_billing': 'on'}, **HOST)
        op = CompanyOperator.objects.get(user__username='m')
        self.assertFalse(op.can_manage_masters or op.can_manage_billing)

    def test_operators_cannot_manage_operators_or_see_audit(self):
        self.operator(**{f: True for f in ALL_FLAGS})
        self.login('op1')
        self.assertEqual(self.client.get('/admin-tools/operators/', **HOST).status_code, 302)
        self.assertEqual(self.client.get('/admin-tools/audit/', **HOST).status_code, 302)
        self.assertEqual(self.client.post('/admin-tools/operators/1/toggle/', **HOST).status_code, 403)

    def test_other_company_operator_is_404(self):
        theirs = self.operator('theirs', company=self.other)
        self.login('owner')
        self.assertEqual(self.client.get(f'/admin-tools/operators/{theirs.pk}/edit/', **HOST).status_code, 404)
        self.assertEqual(self.client.post(f'/admin-tools/operators/{theirs.pk}/toggle/', **HOST).status_code, 404)
        theirs.refresh_from_db(); self.assertTrue(theirs.is_active)

    def test_import_needs_employees_add(self):
        self.operator(can_view_employees=True, can_add_employees=False)
        self.login('op1')
        self.assertEqual(self.client.get('/masters/import/employees/', **HOST).status_code, 302)
        self.assertEqual(self.client.post('/masters/import/employees/', {}, **HOST).status_code, 403)
        CompanyOperator.objects.filter(user__username='op1').update(can_add_employees=True)
        self.assertEqual(self.client.get('/masters/import/employees/', **HOST).status_code, 200)


class MenuAndModeTests(FoundationBase):
    def labels(self, resp):
        out = set()
        for g in resp.context['capp_nav']:
            out.add(g['label'])
            out.update(i['label'] for i in g.get('items', []))
        return out

    def test_owner_menu_and_badge_associate(self):
        self.login('owner')
        r = self.client.get('/dashboard/', **HOST)
        self.assertContains(r, 'Under associate')
        self.assertContains(r, 'Employees 0 / 150')
        labels = self.labels(r)
        self.assertTrue({'Employees', 'Masters', 'Operators', 'Audit Log', 'Invoices'} <= labels)

    def test_badge_direct(self):
        Company_ = type(self.co)
        Company_.objects.filter(pk=self.co.pk).update(management_mode='DIRECT')
        self.login('owner')
        self.assertContains(self.client.get('/dashboard/', **HOST), 'Direct company')

    def test_operator_menu_follows_flags_and_mode(self):
        self.operator(can_view_employees=True, can_view_attendance=False, can_manage_masters=True,
                      can_manage_billing=True)
        self.login('op1')
        r = self.client.get('/dashboard/', **HOST)
        labels = self.labels(r)
        self.assertIn('All Employees', labels)
        self.assertNotIn('Attendance Register', labels)
        self.assertNotIn('Masters', labels)                   # ASSOCIATE operator: masters never
        self.assertNotIn('Operators', labels)
        self.assertContains(r, 'Operator')
        type(self.co).objects.filter(pk=self.co.pk).update(management_mode='DIRECT')
        labels = self.labels(self.client.get('/dashboard/', **HOST))
        self.assertIn('Masters', labels)                      # DIRECT operator with the flag
        self.assertIn('Invoices', labels)
        self.assertNotIn('Operators', labels)


class AuditTests(FoundationBase):
    def test_masters_write_is_logged_with_role(self):
        op = self.operator(can_manage_masters=True)
        type(self.co).objects.filter(pk=self.co.pk).update(management_mode='DIRECT')
        self.login('op1')
        self.client.post('/masters/branches/add/', {'branch_name': 'Murthal'}, **HOST)
        row = CappAuditLog.objects.get(action='create')
        self.assertEqual((row.username, row.role, row.model, row.company), ('op1', 'OPERATOR', 'branch', self.co))

    def test_owner_screen_filters_and_isolates(self):
        class R:  # minimal request double for another company
            user = self.owner; owned_company = self.other; capp_role = 'OWNER'; META = {}
        log_action(R, 'secret', None, 'other company row')
        self.login('owner')
        log_action(SimpleNamespace(user=self.owner, owned_company=self.co, capp_role='OWNER',
                                   META={'REMOTE_ADDR': '1.2.3.4'}), 'test_action', None, 'mine')
        r = self.client.get('/admin-tools/audit/?action=test', **HOST)
        self.assertContains(r, 'test_action')
        self.assertNotContains(self.client.get('/admin-tools/audit/', **HOST), 'other company row')
        self.assertEqual(self.client.get('/admin-tools/audit/?from=garbage', **HOST).status_code, 200)

    def test_log_action_never_raises(self):
        log_action(SimpleNamespace(user=None, owned_company=None, META={}), 'x')   # no company: ignored
        log_action(object(), 'x')                                                   # broken request: swallowed


@override_settings(ALLOWED_HOSTS=['*'])
class SappOperatorScreenTests(FoundationBase):
    def test_superadmin_lists_and_suspends(self):
        op = self.operator()
        admin = User.objects.create_superuser('root', 'r@x.com', 'pw-Strong-1')
        self.client.login(username='root', password='pw-Strong-1')
        h = {'HTTP_HOST': 'sapp.localhost'}
        self.assertContains(self.client.get('/operators/', **h), 'op1')
        self.client.post(f'/operators/{op.pk}/toggle/', **h)
        op.refresh_from_db(); self.assertFalse(op.is_active)

    def test_non_superuser_blocked(self):
        op = self.operator()
        self.client.login(username='owner', password='pw-Strong-1')
        h = {'HTTP_HOST': 'sapp.localhost'}
        self.assertNotEqual(self.client.get('/operators/', **h).status_code, 200)
        self.client.post(f'/operators/{op.pk}/toggle/', **h)
        op.refresh_from_db(); self.assertTrue(op.is_active)


@override_settings(ALLOWED_HOSTS=['*'])
class OperatorCapTests(FoundationBase):
    """Owner decision: at most 5 ACTIVE operators per company (separate from the employee limit)."""

    def add(self, name):
        return self.client.post('/admin-tools/operators/add/', {
            'username': name, 'password': 'Tr1cky-pass-77', 'can_view_employees': 'on'}, **HOST)

    def test_sixth_active_operator_is_refused(self):
        self.login('owner')
        for i in range(5):
            self.assertEqual(self.add(f'op{i}').status_code, 302, i)
        r = self.add('op5')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'maximum')
        self.assertEqual(CompanyOperator.objects.filter(company=self.co).count(), 5)
        self.assertContains(self.client.get('/admin-tools/operators/', **HOST), '5 / 5')

    def test_suspending_frees_a_seat_and_enabling_respects_the_cap(self):
        self.login('owner')
        for i in range(5):
            self.add(f'op{i}')
        first = CompanyOperator.objects.get(user__username='op0')
        self.client.post(f'/admin-tools/operators/{first.pk}/toggle/', **HOST)        # suspend
        self.assertEqual(self.add('op5').status_code, 302)                           # seat reused
        self.client.post(f'/admin-tools/operators/{first.pk}/toggle/', **HOST)        # enable: full again
        first.refresh_from_db(); self.assertFalse(first.is_active)

    def test_other_companies_do_not_share_the_cap(self):
        for i in range(5):
            self.operator(f'x{i}', company=self.other)
        self.login('owner')
        self.assertEqual(self.add('mine').status_code, 302)

    def test_new_operator_form_starts_with_data_entry_rights(self):
        self.login('owner')
        form = self.client.get('/admin-tools/operators/add/', **HOST).context['form']
        for f in ('can_add_employees', 'can_edit_attendance', 'can_edit_loans'):
            self.assertTrue(form.fields[f].initial, f)             # data entry ticked by default
        for f in ('can_download_payroll', 'can_download_challans', 'can_view_wages'):
            self.assertFalse(form.fields[f].initial, f)            # money and files are not
        r = self.client.get(f'/admin-tools/operators/{self.operator().pk}/edit/', **HOST)
        self.assertFalse(r.context['form'].fields['can_add_employees'].initial)   # edits show saved values


@override_settings(ALLOWED_HOSTS=['*'])
class AssociateOperatorScreenTests(FoundationBase):
    H = {'HTTP_HOST': 'aapp.localhost'}

    def associate(self, name, companies):
        from Sapp.app.user import associateuser
        u = User.objects.create_user(name, password='pw-Strong-1')
        associateuser.objects.create(user=u, associate_id=f'A-{name}').companyid.set(companies)
        return u

    def select(self, company):
        s = self.client.session
        s['selected_company_id'] = company.pk
        s.save()

    def test_associate_lists_and_suspends_and_login_dies(self):
        op = self.operator()
        self.associate('assoc', [self.co])
        self.login('assoc')
        self.select(self.co)
        self.assertContains(self.client.get('/company-operators/', **self.H), 'op1')
        self.client.post(f'/company-operators/{op.pk}/toggle/', **self.H)
        op.refresh_from_db(); self.assertFalse(op.is_active)
        self.assertIn('Suspended by associate', op.suspended_reason)
        self.client.logout()
        r = self.client.post('/login/', {'username': 'op1', 'password': 'pw-Strong-1'}, **HOST)
        self.assertEqual(r.status_code, 200)                          # cannot log in any more

    def test_associate_of_another_company_is_refused(self):
        op = self.operator()
        self.associate('stranger', [self.other])
        self.login('stranger')
        self.select(self.co)                                          # forged session value
        r = self.client.get('/company-operators/', **self.H)
        self.assertEqual(r.status_code, 302)
        self.client.post(f'/company-operators/{op.pk}/toggle/', **self.H)
        op.refresh_from_db(); self.assertTrue(op.is_active)

    def test_owner_and_operator_cannot_use_the_associate_screen(self):
        op = self.operator()
        for name in ('owner', 'op1'):
            self.login(name)
            self.select(self.co)
            self.assertEqual(self.client.get('/company-operators/', **self.H).status_code, 302)
            self.client.post(f'/company-operators/{op.pk}/toggle/', **self.H)
        op.refresh_from_db(); self.assertTrue(op.is_active)

    def test_enable_respects_the_cap(self):
        ops = [self.operator(f'o{i}') for i in range(5)]
        extra = self.operator('o9', is_active=False)
        self.associate('assoc', [self.co])
        self.login('assoc'); self.select(self.co)
        self.client.post(f'/company-operators/{extra.pk}/toggle/', **self.H)
        extra.refresh_from_db(); self.assertFalse(extra.is_active)

    def test_cannot_touch_operators_of_another_company(self):
        theirs = self.operator('theirs', company=self.other)
        self.associate('assoc', [self.co])
        self.login('assoc'); self.select(self.co)
        self.assertEqual(self.client.post(f'/company-operators/{theirs.pk}/toggle/', **self.H).status_code, 404)
