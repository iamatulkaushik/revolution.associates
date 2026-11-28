"""E4 downloads: one gate for both modes (batch must be APPROVED)."""
from datetime import date
from decimal import Decimal as D
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.batch_job import BatchJob
from Aapp.app.salary_processing import salary_processing, salary_slip
from Capp.foundation.models import CappAuditLog, CompanyOperator
from Capp.models import CompanyOwnerProfile
from Capp.tests_foundation import ALL_FLAGS, make_employee
from Capp.tests_masters import make_company

HOST = {'HTTP_HOST': 'capp.localhost'}


@override_settings(ALLOWED_HOSTS=['*'])
class DownloadGateTests(TestCase):
    def setUp(self):
        self.co = make_company('JSK', 'AAAAA1111A')
        self.other = make_company('Other', 'BBBBB2222B')
        self.owner = User.objects.create_user('owner', password='pw-Strong-1')
        self.profile = CompanyOwnerProfile.objects.create(user=self.owner, company=self.co)
        self.client.login(username='owner', password='pw-Strong-1')
        self.emp = make_employee(self.co, '1')
        self.batch = self.make_batch(self.co, self.emp, 11, 2026, 'APPROVED')

    def make_batch(self, co, emp, month, year, status):
        b = salary_processing.objects.create(company_id=co, month=month, year=year, status=status)
        salary_slip.objects.create(
            processing_id=b, employee_id=emp, company_id=co, paid_days=D('30'),
            basic_earned=D('15221'), hra_earned=D('2779'), gross_earnings=D('18000'),
            net_pay=D('16000'))
        return b

    def slip(self, batch=None):
        return salary_slip.objects.get(processing_id=batch or self.batch)

    def urls(self, slip):
        return {
            'sheet': '/downloads/sheet/11/2026/', 'abstract': '/downloads/abstract/11/2026/',
            'slip': f'/downloads/slip/{slip.pk}/', 'all': '/downloads/slips/11/2026/'}

    def test_approved_batch_gives_pdfs(self):
        for name, url in self.urls(self.slip()).items():
            r = self.client.get(url, **HOST)
            self.assertEqual(r.status_code, 200, name)
            self.assertTrue(r.content.startswith(b'%PDF'), name)

    def test_open_batch_is_blocked_with_reason(self):
        for status in ('DRAFT', 'PROCESSED'):
            salary_processing.objects.filter(pk=self.batch.pk).update(status=status)
            for name, url in self.urls(self.slip()).items():
                r = self.client.get(url, **HOST)
                self.assertEqual(r.status_code, 302, (status, name))
                self.assertIn('/downloads/', r.url)
            page = self.client.get('/downloads/?month=11&year=2026', **HOST)
            self.assertContains(page, 'Ask your associate to approve it')
            self.assertNotContains(page, 'Salary Sheet (PDF)')

    def test_paid_is_accepted_for_the_future(self):
        salary_processing.objects.filter(pk=self.batch.pk).update(status='PAID')
        self.assertEqual(self.client.get('/downloads/sheet/11/2026/', **HOST).status_code, 200)

    def test_no_batch_blocked(self):
        r = self.client.get('/downloads/sheet/10/2026/', **HOST)
        self.assertEqual(r.status_code, 302)

    def test_other_tenant_slip_is_404(self):
        emp2 = make_employee(self.other, '2')
        b2 = self.make_batch(self.other, emp2, 11, 2026, 'APPROVED')
        self.assertEqual(self.client.get(f'/downloads/slip/{self.slip(b2).pk}/', **HOST).status_code, 404)

    def test_bad_period_is_404(self):
        self.assertEqual(self.client.get('/downloads/sheet/13/2026/', **HOST).status_code, 404)
        self.assertEqual(self.client.get('/downloads/?month=x', **HOST).status_code, 404)

    def test_owner_without_pdf_flag_denied(self):
        self.profile.can_download_pdf = False
        self.profile.save()
        self.assertEqual(self.client.get('/downloads/sheet/11/2026/', **HOST).status_code, 302)
        self.assertEqual(self.client.get('/downloads/', **HOST).status_code, 302)

    def test_operator_needs_both_flags(self):
        u = User.objects.create_user('op', password='pw-Strong-1')
        op = CompanyOperator.objects.create(user=u, company=self.co, can_view_wages=True)
        self.client.login(username='op', password='pw-Strong-1')
        self.assertEqual(self.client.get('/downloads/sheet/11/2026/', **HOST).status_code, 302)
        op.can_download_payroll = True
        op.save()
        self.assertEqual(self.client.get('/downloads/sheet/11/2026/', **HOST).status_code, 200)

    def test_downloads_are_audited(self):
        self.client.get('/downloads/sheet/11/2026/', **HOST)
        self.client.get(f'/downloads/slip/{self.slip().pk}/', **HOST)
        actions = set(CappAuditLog.objects.filter(company=self.co).values_list('action', flat=True))
        self.assertTrue({'download_salary_sheet', 'download_salary_slip'} <= actions)

    def test_old_urls_use_the_same_gate(self):
        salary_processing.objects.filter(pk=self.batch.pk).update(status='PROCESSED')
        r = self.client.get('/wages/sheet/?month=11&year=2026', **HOST)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/downloads/sheet/11/2026/', r.url)
        r = self.client.get(r.url, **HOST)
        self.assertEqual(r.status_code, 302)                      # gate refuses
        r = self.client.get(f'/wages/slip/{self.slip().pk}/download/', **HOST)
        self.assertEqual(r.status_code, 302)

    def test_background_wages_job_gated_and_scoped(self):
        salary_processing.objects.filter(pk=self.batch.pk).update(status='PROCESSED')
        with mock.patch('Aapp.app.tasks.async_task') as q:
            self.assertEqual(self.client.post('/downloads/wages-slips/11/2026/start/', **HOST).status_code, 302)
            q.assert_not_called()                                  # open batch: refused
            salary_processing.objects.filter(pk=self.batch.pk).update(status='APPROVED')
            self.assertEqual(self.client.get('/downloads/wages-slips/11/2026/start/', **HOST).status_code, 302)
            q.assert_not_called()                                  # GET never queues
            self.client.post('/downloads/wages-slips/11/2026/start/', **HOST)
            q.assert_called_once()
        job = BatchJob.objects.get()
        self.assertEqual((job.company_id, job.requested_by), (self.co, self.owner))
        self.assertEqual(self.client.get(f'/downloads/job/{job.pk}/', **HOST).status_code, 200)
        self.assertEqual(self.client.get(f'/downloads/job/{job.pk}/status.json', **HOST).json()['status'], 'queued')
        self.assertEqual(self.client.get(f'/downloads/job/{job.pk}/file/', **HOST).status_code, 404)
        o = User.objects.create_user('o2', password='pw-Strong-1')
        CompanyOwnerProfile.objects.create(user=o, company=self.other)
        self.client.login(username='o2', password='pw-Strong-1')
        self.assertEqual(self.client.get(f'/downloads/job/{job.pk}/', **HOST).status_code, 404)

    def test_menu_has_downloads_entry(self):
        r = self.client.get('/dashboard/', **HOST)
        labels = {g['label'] for g in r.context['capp_nav']}
        self.assertIn('Downloads', labels)
