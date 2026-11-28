"""E2 monthly attendance entry, lock rule D7, E6 attendance import."""
import io
from decimal import Decimal as D

import openpyxl
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from Aapp.app.attandance import attendance
from Aapp.app.employee import employee
from Aapp.app.salary_processing import salary_processing
from Capp.foundation.models import CappAuditLog, CompanyOperator
from Capp.models import CompanyOwnerProfile
from Capp.entry.attendance import clean_row
from Capp.tests_foundation import make_employee
from Capp.tests_masters import make_company

HOST = {'HTTP_HOST': 'capp.localhost'}


class CleanRowTests(TestCase):
    def test_blank_row_means_no_record(self):
        self.assertEqual(clean_row({}, 11, 2026), (None, []))
        self.assertEqual(clean_row({'working_days': ' '}, 11, 2026), (None, []))

    def test_rules(self):
        ok = clean_row({'working_days': '26', 'holidays': '4', 'overtime_hours': '10'}, 11, 2026)
        self.assertEqual(ok[1], [])
        self.assertEqual(ok[0]['work_pay'], D('0'))
        bad = {
            'days over month': {'working_days': '31'},
            'paid days over month': {'working_days': '28', 'work_pay': '3'},
            'leave over worked': {'working_days': '5', 'sick_leaves': '6'},
            'negative': {'working_days': '-1'},
            'text': {'working_days': 'abc'},
            'three decimals': {'working_days': '1.234'},
            'ot cap': {'working_days': '1', 'overtime_hours': '301'},
        }
        for name, raw in bad.items():
            self.assertTrue(clean_row(raw, 11, 2026)[1], name)
        self.assertEqual(clean_row({'working_days': '31'}, 12, 2026)[1], [])      # December has 31 days


@override_settings(ALLOWED_HOSTS=['*'])
class AttendanceEntryTests(TestCase):
    def setUp(self):
        self.co = make_company('JSK', 'AAAAA1111A')
        self.other = make_company('Other', 'BBBBB2222B')
        self.owner = User.objects.create_user('owner', password='pw-Strong-1')
        self.profile = CompanyOwnerProfile.objects.create(user=self.owner, company=self.co)
        self.client.login(username='owner', password='pw-Strong-1')
        self.e1 = make_employee(self.co, '1')
        self.e2 = make_employee(self.co, '2')
        self.gone = make_employee(self.co, '3', working=False)
        self.e1.designationID.basicpay = D('7200')          # hourly 30, overtime 60 per hour
        self.e1.designationID.save()

    def post(self, **extra):
        d = {'month': '11', 'year': '2026'}
        d.update(extra)
        return self.client.post('/entry/attendance/', d, **HOST)

    def test_grid_lists_active_employees_and_missing_count(self):
        r = self.client.get('/entry/attendance/?month=11&year=2026', **HOST)
        self.assertContains(r, 'E1'); self.assertContains(r, 'E2'); self.assertNotContains(r, 'E3')
        self.assertEqual(r.context['missing'], 2)
        self.assertContains(r, 'assume a full month')

    def silver(self):
        type(self.co).objects.filter(pk=self.co.pk).update(plan='silver')    # OT is a silver feature

    def test_copper_plan_has_no_overtime_columns(self):
        r = self.client.get('/entry/attendance/?month=11&year=2026', **HOST)
        self.assertNotContains(r, 'OT hours')
        self.post(**{f'working_days_{self.e1.pk}': '26', f'overtime_hours_{self.e1.pk}': '40'})
        a = attendance.objects.get()
        self.assertEqual((a.working_days, a.overtime_hours, a.ot_wages_paid), (D('26'), D('0'), D('0')))
        self.silver()
        self.assertContains(self.client.get('/entry/attendance/?month=11&year=2026', **HOST), 'OT hours')

    def test_save_creates_summary_rows_and_ot_rule(self):
        self.silver()
        r = self.post(**{f'working_days_{self.e1.pk}': '26', f'holidays_{self.e1.pk}': '4',
                         f'overtime_hours_{self.e1.pk}': '40'})
        self.assertEqual(r.status_code, 302)
        a = attendance.objects.get(employee_id=self.e1, salary_month=11, salary_year=2026)
        self.assertEqual((a.working_days, a.holidays, a.companyid, a.emp_code, a.created_by),
                         (D('26'), D('4'), self.co, '1', self.owner))
        self.assertEqual((a.ordinary_rate, a.ot_rate, a.ot_wages_paid),
                         (D('30'), D('60'), D('2400')))        # double the hourly rate from basic
        self.assertFalse(attendance.objects.filter(employee_id=self.e2).exists())  # blank row: no record
        self.assertTrue(CappAuditLog.objects.filter(action='attendance_save').exists())

    def test_resave_updates_not_duplicates_and_recomputes_ot(self):
        self.silver()
        key = f'working_days_{self.e1.pk}'
        self.post(**{key: '20', f'overtime_hours_{self.e1.pk}': '10'})
        self.post(**{key: '25', f'overtime_hours_{self.e1.pk}': '20'})
        self.assertEqual(attendance.objects.filter(employee_id=self.e1).count(), 1)
        a = attendance.objects.get(employee_id=self.e1)
        self.assertEqual((a.working_days, a.ot_wages_paid), (D('25'), D('1200')))

    def test_register_rates_match_what_payroll_pays(self):
        from Aapp.app.salary_processing import _calculate_overtime
        self.silver()
        self.post(**{f'working_days_{self.e1.pk}': '26', f'overtime_hours_{self.e1.pk}': '12.5'})
        a = attendance.objects.get()
        self.assertEqual(a.ot_wages_paid, _calculate_overtime(D('7200'), D('12.5')))      # 750.00

    def test_grid_warns_when_no_shop_act_registration(self):
        self.silver()
        r = self.client.get('/entry/attendance/?month=11&year=2026', **HOST)
        self.assertContains(r, 'No Shop Act registration')
        self.assertContains(r, 'double the hourly rate')
        self.assertNotContains(self.client.get('/entry/attendance/?month=11&year=2026', **HOST), 'ordinary')

    def test_errors_block_the_whole_save(self):
        r = self.post(**{f'working_days_{self.e1.pk}': '20', f'working_days_{self.e2.pk}': '40'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(attendance.objects.count(), 0)                          # nothing partial
        self.assertContains(r, 'more than 30 days')
        self.assertContains(r, 'value="20"')                                     # typed values kept

    def test_associate_lock_after_processing(self):
        b = salary_processing.objects.create(company_id=self.co, month=11, year=2026, status='DRAFT')
        self.assertEqual(self.post(**{f'working_days_{self.e1.pk}': '20'}).status_code, 302)
        self.assertEqual(attendance.objects.count(), 1)
        for status in ('PROCESSED', 'APPROVED'):
            salary_processing.objects.filter(pk=b.pk).update(status=status)
            attendance.objects.all().delete()
            r = self.post(**{f'working_days_{self.e1.pk}': '20'})
            self.assertEqual(r.status_code, 302)
            self.assertEqual(attendance.objects.count(), 0, status)
            self.assertContains(self.client.get('/entry/attendance/?month=11&year=2026', **HOST),
                                'Entry is closed')

    def test_direct_mode_allows_processed_but_not_approved(self):
        type(self.co).objects.filter(pk=self.co.pk).update(management_mode='DIRECT')
        b = salary_processing.objects.create(company_id=self.co, month=11, year=2026, status='PROCESSED')
        self.assertEqual(self.post(**{f'working_days_{self.e1.pk}': '20'}).status_code, 302)
        self.assertEqual(attendance.objects.count(), 1)
        self.assertContains(self.client.get('/entry/attendance/?month=11&year=2026', **HOST), 'Reprocess the batch')
        salary_processing.objects.filter(pk=b.pk).update(status='APPROVED')
        self.post(**{f'working_days_{self.e1.pk}': '22'})
        self.assertEqual(attendance.objects.get().working_days, D('20'))

    def test_other_company_employee_never_written(self):
        theirs = make_employee(self.other, '9')
        self.post(**{f'working_days_{theirs.pk}': '20'})
        self.assertEqual(attendance.objects.count(), 0)

    def test_operator_needs_edit_flag(self):
        u = User.objects.create_user('op', password='pw-Strong-1')
        op = CompanyOperator.objects.create(user=u, company=self.co, can_view_attendance=True)
        self.client.login(username='op', password='pw-Strong-1')
        self.assertEqual(self.client.get('/entry/attendance/', **HOST).status_code, 302)
        self.assertEqual(self.post(**{f'working_days_{self.e1.pk}': '20'}).status_code, 403)
        op.can_edit_attendance = True; op.save()
        self.assertEqual(self.post(**{f'working_days_{self.e1.pk}': '20'}).status_code, 302)
        self.assertEqual(attendance.objects.get().created_by, u)

    def test_bad_period_404(self):
        self.assertEqual(self.client.get('/entry/attendance/?month=13', **HOST).status_code, 404)


def att_sheet(rows, header=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'ATT'
    ws.append(header or ['S No.', 'ID No.', 'Name', 'ATT', 'AB', 'H', 'TATT', 'OT'])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO(); wb.save(buf)
    return SimpleUploadedFile('att.xlsx', buf.getvalue())


@override_settings(ALLOWED_HOSTS=['*'])
class AttendanceImportTests(TestCase):
    def setUp(self):
        self.co = make_company('JSK', 'AAAAA1111A')
        self.owner = User.objects.create_user('owner', password='pw-Strong-1')
        CompanyOwnerProfile.objects.create(user=self.owner, company=self.co)
        self.client.login(username='owner', password='pw-Strong-1')
        make_employee(self.co, '11001')
        make_employee(self.co, '11002', working=False)

    def upload(self, rows, use_ot=False, **kw):
        d = {'file': att_sheet(rows, kw.get('header')), 'month': '11', 'year': '2026'}
        if use_ot:
            d['use_ot'] = 'on'
        return self.client.post('/entry/attendance/import/', d, **HOST)

    def test_preview_then_confirm_without_ot_by_default(self):
        r = self.upload([[1, 11001.0, 'X', 30.0, 0, 0, 30.0, 80.0]])
        self.assertContains(r, 'Import 1 row')
        self.assertNotContains(r, '4800')                                   # OT not requested here
        self.assertEqual(attendance.objects.count(), 0)                  # preview writes nothing
        self.client.post('/entry/attendance/import/', {'confirm': '1'}, **HOST)
        a = attendance.objects.get()
        self.assertEqual((a.working_days, a.overtime_hours), (D('30'), D('0')))   # OT column ignored
        self.assertTrue(CappAuditLog.objects.filter(action='attendance_import').exists())

    def test_preview_shows_the_overtime_amount_payroll_will_pay(self):
        type(self.co).objects.filter(pk=self.co.pk).update(plan='silver')
        e = employee.objects.get(employeecode='11001')
        e.designationID.basicpay = D('7200'); e.designationID.save()
        r = self.upload([[1, 11001, 'X', 30, 0, 0, 30, 80]], use_ot=True)        # sheet says 80 hours
        self.assertEqual(r.context['rows'][0]['ot_estimate'], D('4800.00'))       # 80 x 60
        self.assertContains(r, '₹4800.00')

    def test_ot_column_only_when_asked(self):
        type(self.co).objects.filter(pk=self.co.pk).update(plan='silver')
        self.upload([[1, 11001, 'X', 28, 2, 2, 28, 40]], use_ot=True)
        self.client.post('/entry/attendance/import/', {'confirm': '1'}, **HOST)
        a = attendance.objects.get()
        self.assertEqual((a.working_days, a.holidays, a.overtime_hours), (D('28'), D('2'), D('40')))

    def test_ot_column_is_ticked_by_default_and_ignored_on_copper(self):
        r = self.client.get('/entry/attendance/import/', **HOST)
        self.assertTrue(r.context['form'].fields['use_ot'].initial)
        r = self.upload([[1, 11001, 'X', 30, 0, 0, 30, 80]], use_ot=True)          # copper company
        self.assertContains(r, 'ignored: your plan has no overtime feature')
        self.client.post('/entry/attendance/import/', {'confirm': '1'}, **HOST)
        self.assertEqual(attendance.objects.get().overtime_hours, D('0'))

    def test_reimport_updates(self):
        for days in (20, 25):
            self.upload([[1, 11001, 'X', days, 0, 0, days, 0]])
            self.client.post('/entry/attendance/import/', {'confirm': '1'}, **HOST)
        self.assertEqual(attendance.objects.count(), 1)
        self.assertEqual(attendance.objects.get().working_days, D('25'))

    def test_bad_rows_skipped_with_reasons(self):
        r = self.upload([[1, 99999, 'NOBODY', 20, 0, 0, 20, 0], [2, 11002, 'GONE', 20, 0, 0, 20, 0],
                         [3, 11001, 'X', 45, 0, 0, 45, 0], [4, 11001, 'X', 20, 0, 0, 20, 0]])
        text = r.content.decode()
        for word in ('ID not found', 'relieved', 'more than 30 days', 'Duplicate ID'):
            self.assertIn(word, text)
        self.client.post('/entry/attendance/import/', {'confirm': '1'}, **HOST)
        self.assertEqual(attendance.objects.count(), 0)    # row 4 is a duplicate of the bad row 3's ID: skipped

    def test_locked_month_refuses_upload(self):
        salary_processing.objects.create(company_id=self.co, month=11, year=2026, status='PROCESSED')
        r = self.upload([[1, 11001, 'X', 20, 0, 0, 20, 0]])
        self.assertContains(r, 'Entry is closed')

    def test_wrong_file_and_missing_sheet(self):
        bad = SimpleUploadedFile('a.txt', b'x')
        r = self.client.post('/entry/attendance/import/', {'file': bad, 'month': '11', 'year': '2026'}, **HOST)
        self.assertEqual(r.status_code, 200)
        r = self.upload([[1, 11001, 'X']], header=['a', 'b', 'c'])
        self.assertContains(r, 'No attendance sheet found')
