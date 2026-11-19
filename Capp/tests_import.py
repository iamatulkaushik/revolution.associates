import io
from datetime import date, datetime

import openpyxl
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from Aapp.app.branch_department import branch
from Aapp.app.employee import employee
from Capp import importer
from Capp.billing_models import BillingClient, ClientEmployee
from Capp.models import CompanyOwnerProfile
from Capp.tests_masters import make_company

HOST = {'HTTP_HOST': 'capp.localhost'}
DATA_HEAD = ['S.NO.', 'ID No.', 'Name', "Father's Name", 'DAT OF BIRTH', 'Department', 'Designation',
             'Ac no', 'AADHAAR NO', 'D.O.B.', 'D.O.J.', 'M NO', 'ESI', 'QULIFICATION', 'UAN', '',
             'Com. Gross Salary', 'Govt. Minimum Salary', '', 'BASIC', 'HRA', 'Other',
             'TEMPARORY ADDRESS', 'PERMANENT ADDRESS']


def workbook(rows, bank_rows=True):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'DATA'
    ws.append(['DATA!A1'] + [None] * 10)           # junk first row, header is row 2
    ws.append(DATA_HEAD)
    for r in rows:
        ws.append(r)
    if bank_rows:
        bk = wb.create_sheet('bank')
        bk.append(['DATA!A1', 'ID No.', 'Name', "Father's Name", 'Department', 'IFSC', 'Ac no',
                   'Adress', 'M NO', 'NET PAY'])
        bk.append([1, 11001, 'MOHD OSAMA', 'MOHD SHAMIM', 'S.P', 'BARB0SIKAND', '14288100020591',
                   'SIKANDARPUR UP', 9936100163, 100])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def good(code=11001, acc='14288100020591', aad='990316397256', mob=9936100163):
    return [1, code, 'MOHD OSAMA', 'MOHD SHAMIM', '01.01.2007', 'S.P', 'DRIVER', acc, aad,
            None, '09.04.2026', mob, 1328512881, 10, 102160135945, None, 18000, 18000, None, 15221,
            2779, 0, 'BAHALGARH SONIPAT HR', 'SAHNEMAU UP']


class ParseTests(TestCase):
    def setUp(self):
        self.co = make_company('JSK', 'AAAAA1111A')

    def test_parse_clean_row_with_ifsc_from_bank_sheet(self):
        sheets = importer.read_sheets(workbook([good()]), 'x.xlsx')
        rows, notes = importer.parse(sheets, self.co)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r['issues'], [], r['issues'])
        d = r['data']
        self.assertEqual((d['code'], d['ifsc'], d['mobile']), ('11001', 'BARB0SIKAND', '9936100163'))
        self.assertEqual(d['doj'], date(2026, 4, 9))
        self.assertEqual(d['basic'], 15221)

    def test_bad_rows_flagged(self):
        bad = good(code=11002, acc='123', aad='12', mob=99)
        bad[10] = 'not a date'
        sheets = importer.read_sheets(workbook([bad], bank_rows=False), 'x.xlsx')
        r = importer.parse(sheets, self.co)[0][0]
        text = ' '.join(r['issues'])
        for word in ('Aadhaar', 'Mobile', 'Account', 'IFSC', 'joining'):
            self.assertIn(word, text)

    def test_duplicate_id_and_blank_rows_skipped(self):
        sheets = importer.read_sheets(workbook([good(), good(), [None] * 24]), 'x.xlsx')
        rows = importer.parse(sheets, self.co)[0]
        self.assertEqual(len(rows), 2)
        self.assertIn('Duplicate', ' '.join(rows[1]['issues']))

    def test_real_xls_style_floats(self):
        row = good()
        row[1], row[8], row[11] = 11001.0, 990316397256.0, 9936100163.0
        row[7] = 14288100020591.0
        r = importer.parse(importer.read_sheets(workbook([row]), 'x.xlsx'), self.co)[0][0]
        self.assertEqual(r['issues'], [])
        self.assertEqual(r['data']['account'], '14288100020591')

    def test_long_float_account_rejected(self):
        row = good(acc=1234567890123456789.0)       # >15 digits: Excel already lost digits
        r = importer.parse(importer.read_sheets(workbook([row]), 'x.xlsx'), self.co)[0][0]
        self.assertIn('Text', ' '.join(r['issues']))


@override_settings(ALLOWED_HOSTS=['*'])
class ImportViewTests(TestCase):
    def setUp(self):
        self.co = make_company('JSK', 'AAAAA1111A')
        self.user = User.objects.create_user('owner', password='x')
        CompanyOwnerProfile.objects.create(user=self.user, company=self.co)
        self.client.login(username='owner', password='x')
        self.br = branch.objects.create(branch_name='M', companyid=self.co, created_by=self.user)
        self.cl = BillingClient.objects.create(company=self.co, name='TOYO')

    def upload(self, rows):
        f = SimpleUploadedFile('d.xlsx', workbook(rows).getvalue())
        return self.client.post('/masters/import/employees/', {
            'file': f, 'branch': self.br.pk, 'gender': 'Male', 'client': self.cl.pk}, **HOST)

    def test_preview_then_confirm_creates_and_maps(self):
        r = self.upload([good()])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Import 1 employee')
        self.assertEqual(employee.objects.count(), 0)               # preview writes nothing
        self.client.post('/masters/import/employees/', {'confirm': '1'}, **HOST)
        e = employee.objects.get(employeecode='11001')
        self.assertEqual((e.CompanyID, e.bank_ifsc, e.designationID.designationname),
                         (self.co, 'BARB0SIKAND', 'DRIVER'))
        self.assertEqual(e.designationID.basicpay, 15221)
        self.assertEqual(e.designationID.other1, 0)
        self.assertEqual(ClientEmployee.objects.get(employee=e).client, self.cl)

    def test_reimport_updates_not_duplicates(self):
        self.upload([good()]); self.client.post('/masters/import/employees/', {'confirm': '1'}, **HOST)
        changed = good(); changed[2] = 'MOHD OSAMA KHAN'
        self.upload([changed]); self.client.post('/masters/import/employees/', {'confirm': '1'}, **HOST)
        self.assertEqual(employee.objects.count(), 1)
        self.assertEqual(employee.objects.get().name, 'MOHD OSAMA KHAN')

    def test_bad_rows_not_imported(self):
        self.upload([good(aad='12')])
        self.client.post('/masters/import/employees/', {'confirm': '1'}, **HOST)
        self.assertEqual(employee.objects.count(), 0)

    def test_other_company_id_blocked(self):
        other = make_company('Other', 'BBBBB2222B')
        importer_row = importer.parse(importer.read_sheets(workbook([good()]), 'x.xlsx'), other)[0][0]
        importer.apply([importer_row], other, branch.objects.create(
            branch_name='O', companyid=other, created_by=self.user), self.user)
        r = self.upload([good(acc='99999999999999', aad='111122223333', mob=9000000000)])
        self.assertContains(r, 'another company')
