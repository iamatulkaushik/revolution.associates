"""D5a tests - wages reports and Form 24Q for DIRECT companies."""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.services import payroll_batch as pb
from Aapp.app.services import reports as rp
from Aapp.app.services.statutory_files import NothingToGenerate
from Capp.models import CompanyOwnerProfile
from Capp.tests_direct_payroll import add_staff
from Capp.tests_masters import HOST, make_company

M, Y = 11, 2026
BASE = '/direct/reports/'
KINDS = ('grand-total', 'wages-register', 'form-x', 'wages-slips')


def direct(fn):
    return patch('Capp.direct.guards.get_mode', return_value='DIRECT')(fn)


@override_settings(ALLOWED_HOSTS=['*'])
class ReportTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK', 'AAAAA1111A')
        self.c2 = make_company('Other', 'BBBBB2222B')
        self.user = User.objects.create_user('owner', password='x')
        CompanyOwnerProfile.objects.create(user=self.user, company=self.c1)
        self.client.login(username='owner', password='x')
        add_staff(self.c1, self.user)
        add_staff(self.c2, self.user, n=1)

    def finalize(self, company):
        batch, _c = pb.create_batch(company, M, Y, 'owner')
        pb.process_batch(batch, company, 'owner')
        pb.approve_batch(batch, 'owner')

    def get(self, path):
        return self.client.get(path, **HOST)

    def test_associate_mode_blocked(self):
        self.finalize(self.c1)
        for k in KINDS:
            self.assertEqual(self.get(f'{BASE}{Y}/{M}/{k}/').status_code, 302, k)
        self.assertEqual(self.get(BASE).status_code, 302)
        self.assertEqual(self.get(f'{BASE}form24q/2026-27/').status_code, 302)

    @direct
    def test_permission_denied(self, _):
        self.finalize(self.c1)
        with patch('Capp.access.has_perm', return_value=False):
            r = self.get(f'{BASE}{Y}/{M}/grand-total/')
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('pdf', r.get('Content-Type', ''))

    @direct
    def test_page_loads(self, _):
        self.assertEqual(self.get(f'{BASE}?month={M}&year={Y}').status_code, 200)

    @direct
    def test_needs_finalized_month(self, _):
        batch, _c = pb.create_batch(self.c1, M, Y, 'owner')
        pb.process_batch(batch, self.c1, 'owner')              # PROCESSED only
        self.finalize(self.c2)                                   # other company's month is final
        for k in KINDS:
            r = self.get(f'{BASE}{Y}/{M}/{k}/')
            self.assertEqual(r.status_code, 302, k)
            self.assertIn('/direct/reports/', r['Location'])

    @direct
    def test_reports_download_when_final(self, _):
        self.finalize(self.c1)
        for k in KINDS:
            r = self.get(f'{BASE}{Y}/{M}/{k}/')
            self.assertEqual(r.status_code, 200, k)
            self.assertTrue(r.content.startswith(b'%PDF'), k)

    @direct
    def test_unknown_kind_and_month_404(self, _):
        self.finalize(self.c1)
        self.assertEqual(self.get(f'{BASE}{Y}/{M}/nothing/').status_code, 404)
        self.assertEqual(self.get(f'{BASE}{Y}/13/grand-total/').status_code, 404)

    @direct
    def test_download_audited(self, _):
        self.finalize(self.c1)
        with patch('Capp.direct.reports.log_action') as log:
            self.get(f'{BASE}{Y}/{M}/grand-total/')
        self.assertEqual(log.call_args[0][1], 'report.download')

    @direct
    def test_form24q_needs_tan(self, _):
        self.c1.tan = ''
        self.c1.save()
        r = self.get(f'{BASE}form24q/2026-27/')
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('spreadsheet', r.get('Content-Type', ''))

    @direct
    def test_form24q_unknown_year_404(self, _):
        self.assertEqual(self.get(f'{BASE}form24q/1999-00/').status_code, 404)

    def test_form24q_service_empty(self):
        with self.assertRaises(NothingToGenerate):
            rp.build_form24q_xlsx(self.c1, '2026-27')
