"""D3 tests - challans and returns for DIRECT companies, and the extracted file builders."""
import io
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.ecr_generator import _member_lines
from Aapp.app.epf_esi import EpfMonthlyEcr
from Aapp.app.labour_welfare import LabourWelfareFundContribution
from Aapp.app.services import payroll_batch as pb
from Aapp.app.services import statutory_files as sf
from Capp.models import CompanyOwnerProfile
from Capp.tests_direct_payroll import add_staff
from Capp.tests_masters import HOST, make_company
from Sapp.app.company import company_statury

M, Y = 11, 2026
BASE = '/direct/challans/'
FULL = dict(epfo='HRGGN0012345000', esic='12345678901234567', shop_act='SA/1', labour='L1', pt_number='PT1')


def direct(fn):
    return patch('Capp.direct.guards.get_mode', return_value='DIRECT')(fn)


def url(name):
    return f'{BASE}{Y}/{M}/{name}/'


@override_settings(ALLOWED_HOSTS=['*'])
class ChallanTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK', 'AAAAA1111A')
        self.c2 = make_company('Other', 'BBBBB2222B')
        self.user = User.objects.create_user('owner', password='x')
        CompanyOwnerProfile.objects.create(user=self.user, company=self.c1)
        self.client.login(username='owner', password='x')
        self.emps = add_staff(self.c1, self.user)
        for i, e in enumerate(self.emps):
            e.uan_number = f'10000000000{i}'
            e.esic_number = f'123456789{i}'
            e.save()
        self.stat = company_statury.objects.create(company=self.c1, **FULL)

    def finalize(self, company=None):
        company = company or self.c1
        batch, _ = pb.create_batch(company, M, Y, 'owner')
        pb.process_batch(batch, company, 'owner')
        pb.approve_batch(batch, 'owner')
        return batch

    def get(self, path):
        return self.client.get(path, **HOST)

    # -- access ------------------------------------------------------------------
    def test_associate_mode_blocked(self):
        self.finalize()
        for path in (BASE, url('ecr'), url('epf-challan'), url('esi-challan'), url('esi-upload'), url('pt')):
            self.assertEqual(self.get(path).status_code, 302, path)
        self.assertEqual(self.client.post(BASE + 'ecr/create/', {'month': M, 'year': Y}, **HOST).status_code, 302)
        self.assertEqual(EpfMonthlyEcr.objects.count(), 0)

    @direct
    def test_permission_denied(self, _):
        self.finalize()
        with patch('Capp.access.has_perm', return_value=False):
            r = self.get(url('esi-challan'))
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('pdf', r.get('Content-Type', ''))

    # -- needs a finalized month -----------------------------------------------------
    @direct
    def test_nothing_before_finalize(self, _):
        batch, _c = pb.create_batch(self.c1, M, Y, 'owner')
        pb.process_batch(batch, self.c1, 'owner')              # PROCESSED only
        for name in ('esi-challan', 'esi-upload', 'pt', 'ecr', 'epf-challan'):
            r = self.get(url(name))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn('/direct/challans/', r['Location'])
        self.client.post(BASE + 'ecr/create/', {'month': M, 'year': Y}, **HOST)
        self.assertEqual(EpfMonthlyEcr.objects.count(), 0)

    # -- happy path ----------------------------------------------------------------
    @direct
    def test_page_loads(self, _):
        self.finalize()
        self.assertEqual(self.get(f'{BASE}?month={M}&year={Y}').status_code, 200)

    @direct
    def test_epf_files(self, _):
        self.finalize()
        self.client.post(BASE + 'ecr/create/', {'month': M, 'year': Y}, **HOST)
        ecr = EpfMonthlyEcr.objects.get(company=self.c1, salary_month=M, salary_year=Y)
        self.assertEqual(ecr.total_members, 2)
        r = self.get(url('ecr'))
        self.assertEqual((r.status_code, r['Content-Type']), (200, 'text/plain'))
        self.assertIn(b'100000000000', r.content)
        r = self.get(url('epf-challan'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

    @direct
    def test_ecr_create_twice_makes_one_record(self, _):
        self.finalize()
        for _i in range(2):
            self.client.post(BASE + 'ecr/create/', {'month': M, 'year': Y}, **HOST)
        self.assertEqual(EpfMonthlyEcr.objects.filter(company=self.c1).count(), 1)

    @direct
    def test_esi_pt_files(self, _):
        self.finalize()
        r = self.get(url('esi-challan'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))
        r = self.get(url('esi-upload'))
        self.assertEqual(r.status_code, 200)
        import openpyxl
        ws = openpyxl.load_workbook(io.BytesIO(r.content)).active
        self.assertEqual([c.value for c in ws[2]][0], '1234567890')
        r = self.get(url('pt'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

    @direct
    def test_lwf_create_and_challan(self, _):
        self.finalize()
        self.client.post(BASE + 'lwf/create/', {'month': M, 'year': Y}, **HOST)
        self.client.post(BASE + 'lwf/create/', {'month': M, 'year': Y}, **HOST)
        recs = LabourWelfareFundContribution.objects.filter(company=self.c1)
        self.assertEqual(recs.count(), 1)
        rec = recs[0]
        self.assertEqual((rec.contribution_period, rec.total_employees), ('jul_dec', 2))
        self.assertEqual((rec.due_date.year, rec.due_date.month, rec.due_date.day), (2027, 1, 31))
        r = self.get(f'{BASE}lwf/{rec.pk}/challan/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

    # -- fail-closed by registration -------------------------------------------------
    @direct
    def test_unregistered_schemes_offer_nothing(self, _):
        self.finalize()
        self.stat.epfo = self.stat.esic = self.stat.labour = self.stat.pt_number = None
        self.stat.save()
        for name in ('ecr', 'epf-challan', 'esi-challan', 'esi-upload', 'pt'):
            self.assertEqual(self.get(url(name)).status_code, 302, name)
        self.client.post(BASE + 'ecr/create/', {'month': M, 'year': Y}, **HOST)
        self.client.post(BASE + 'lwf/create/', {'month': M, 'year': Y}, **HOST)
        self.assertEqual(EpfMonthlyEcr.objects.count(), 0)
        self.assertEqual(LabourWelfareFundContribution.objects.count(), 0)

    @direct
    def test_lwf_needs_shop_act_too(self, _):
        self.finalize()
        self.stat.shop_act = None
        self.stat.save()
        self.client.post(BASE + 'lwf/create/', {'month': M, 'year': Y}, **HOST)
        self.assertEqual(LabourWelfareFundContribution.objects.count(), 0)

    # -- tenant isolation ------------------------------------------------------------
    @direct
    def test_other_company_data_not_reachable(self, _):
        self.finalize()                                           # c1 finalized, no ECR yet
        EpfMonthlyEcr.objects.create(company=self.c2, salary_month=M, salary_year=Y, total_members=1)
        self.assertEqual(self.get(url('ecr')).status_code, 404)
        self.assertEqual(self.get(url('epf-challan')).status_code, 404)
        other = LabourWelfareFundContribution.objects.create(
            company=self.c2, year=Y, contribution_period='jul_dec', total_employees=1)
        self.assertEqual(self.get(f'{BASE}lwf/{other.pk}/challan/').status_code, 404)

    @direct
    def test_invalid_month_is_404(self, _):
        self.assertEqual(self.get(f'{BASE}{Y}/13/esi-challan/').status_code, 404)

    # -- audit ---------------------------------------------------------------------
    @direct
    def test_download_is_audited(self, _):
        self.finalize()
        with patch('Capp.direct.challans.log_action') as log:
            self.get(url('esi-challan'))
        self.assertEqual(log.call_args[0][1], 'challan.download')


@override_settings(ALLOWED_HOSTS=['*'])
class StatutoryFilesServiceTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK', 'AAAAA1111A')
        self.user = User.objects.create_user('owner', password='x')
        self.emps = add_staff(self.c1, self.user)
        for i, e in enumerate(self.emps):
            e.uan_number = f'20000000000{i}'
            e.esic_number = f'223456789{i}'
            e.save()
        batch, _ = pb.create_batch(self.c1, M, Y, 'owner')
        pb.process_batch(batch, self.c1, 'owner')

    def test_ecr_text_equals_member_lines(self):
        ecr = sf.create_epf_ecr(self.c1, M, Y, self.user)
        content, fname, skipped = sf.build_ecr_text(self.c1, ecr)
        lines, skipped2 = _member_lines(self.c1, M, Y)
        self.assertEqual(content, '\n'.join(lines) + '\n')
        self.assertEqual((skipped, fname.endswith('.txt')), (skipped2, True))

    def test_ecr_header_matches_lines(self):
        ecr = sf.create_epf_ecr(self.c1, M, Y, self.user)
        lines, _ = _member_lines(self.c1, M, Y)
        self.assertEqual(ecr.total_members, len(lines))

    def test_duplicate_and_empty_period(self):
        sf.create_epf_ecr(self.c1, M, Y, self.user)
        with self.assertRaises(sf.AlreadyExists):
            sf.create_epf_ecr(self.c1, M, Y, self.user)
        with self.assertRaises(sf.NothingToGenerate):
            sf.create_epf_ecr(self.c1, 5, Y, self.user)

    def test_esi_nothing_without_esic_numbers(self):
        for e in self.emps:
            e.esic_number = ''
            e.save()
        with self.assertRaises(sf.NothingToGenerate):
            sf.build_esi_challan_pdf(self.c1, M, Y)
        with self.assertRaises(sf.NothingToGenerate):
            sf.build_esi_upload_xlsx(self.c1, M, Y)
