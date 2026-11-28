"""D5b-3c tests - Factories Act registers, certificate and Form 34 for DIRECT companies."""
from datetime import date, timedelta
from decimal import Decimal as D
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.factory_act import (
    FactoryAccidentRegister, FactoryAnnualReturn, FactoryRegistration, FactoryVesselExamination,
    FactoryWhitewashRegister)
from Aapp.app.services import factory_registers as fr
from Aapp.app.services import payroll_batch as pb
from Aapp.app.services.statutory_files import NothingToGenerate
from Capp.models import CompanyOwnerProfile
from Capp.tests_direct_payroll import add_staff
from Capp.tests_masters import HOST, make_company
from Sapp.app.company import company_statury

BASE = '/direct/factory/'
TODAY = date.today()
YEAR = 2026


def direct(fn):
    return patch('Capp.direct.guards.get_mode', return_value='DIRECT')(fn)


@override_settings(ALLOWED_HOSTS=['*'])
class FactoryTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK', 'AAAAA1111A')
        self.c2 = make_company('Other', 'BBBBB2222B')
        self.user = User.objects.create_user('owner', password='x')
        CompanyOwnerProfile.objects.create(user=self.user, company=self.c1)
        self.client.login(username='owner', password='x')
        self.emps = add_staff(self.c1, self.user)
        self.other_emps = add_staff(self.c2, self.user, n=1)
        self.stat = company_statury.objects.create(company=self.c1, factory='FAC/1')
        self.f = self.fac('FL-1', self.c1)
        self.of = self.fac('FL-2', self.c2)

    def get(self, path):
        return self.client.get(path, **HOST)

    def post(self, path, data=None):
        return self.client.post(path, data or {}, **HOST)

    def fac(self, lic, company):
        return FactoryRegistration.objects.create(
            company=company, factory_license_no=lic, occupier_name='Occ', manager_name='Mgr',
            factory_area_sqm=D('500'), total_hp_used=D('20'), max_workers_day=50, max_workers_night=10,
            license_expiry_date=TODAY + timedelta(days=200))

    def fdata(self, **kw):
        return {'factory_license_no': 'fl-9', 'occupier_name': 'Occ', 'manager_name': 'Mgr',
                'factory_area_sqm': '500', 'total_hp_used': '20', 'max_workers_day': '50',
                'max_workers_night': '10', 'license_expiry_date': (TODAY + timedelta(days=300)).isoformat(), **kw}

    def batch(self, month, status='APPROVED'):
        b, _ = pb.create_batch(self.c1, month, YEAR, 'owner')
        pb.process_batch(b, self.c1, 'owner')
        if status == 'APPROVED':
            pb.approve_batch(b, 'owner')

    def ww(self, f=None):
        return FactoryWhitewashRegister.objects.create(
            factory=f or self.f, area_description='Hall', type_of_work='Lime', date_done=TODAY,
            next_due_date=TODAY + timedelta(days=365))

    # -- access ------------------------------------------------------------------
    def test_associate_mode_blocked(self):
        paths = [BASE, f'{BASE}add/', f'{BASE}{self.f.pk}/edit/', f'{BASE}{self.f.pk}/certificate/',
                 f'{BASE}{self.f.pk}/whitewash/', f'{BASE}{self.f.pk}/whitewash/add/',
                 f'{BASE}{self.f.pk}/annual-return/', f'{BASE}{self.f.pk}/annual-return/add/']
        for path in paths:
            self.assertEqual(self.get(path).status_code, 302, path)
        self.assertEqual(self.post(f'{BASE}add/', self.fdata()).status_code, 302)
        self.assertEqual(FactoryRegistration.objects.filter(company=self.c1).count(), 1)

    @direct
    def test_permission_denied(self, _):
        with patch('Capp.access.has_perm', return_value=False):
            self.assertEqual(self.post(f'{BASE}add/', self.fdata()).status_code, 302)
        self.assertEqual(FactoryRegistration.objects.filter(company=self.c1).count(), 1)

    @direct
    def test_pages_load(self, _):
        fid = self.f.pk
        for path in (BASE, f'{BASE}add/', f'{BASE}{fid}/edit/', f'{BASE}{fid}/whitewash/', f'{BASE}{fid}/vessels/',
                     f'{BASE}{fid}/accidents/', f'{BASE}{fid}/whitewash/add/', f'{BASE}{fid}/vessels/add/',
                     f'{BASE}{fid}/accidents/add/', f'{BASE}{fid}/annual-return/', f'{BASE}{fid}/annual-return/add/'):
            self.assertEqual(self.get(path).status_code, 200, path)
        self.assertEqual(self.get(f'{BASE}{fid}/nothing/').status_code, 404)
        self.assertEqual(self.get(f'{BASE}{fid}/annual-return/download/').status_code, 404)

    # -- gate (fail-closed) ------------------------------------------------------------
    @direct
    def test_off_without_factory_licence(self, _):
        self.stat.factory = ''
        self.stat.save()
        self.assertFalse(self.get(BASE).context['on'])
        fid = self.f.pk
        for path in (f'{BASE}add/', f'{BASE}{fid}/edit/', f'{BASE}{fid}/certificate/', f'{BASE}{fid}/whitewash/',
                     f'{BASE}{fid}/whitewash/download/', f'{BASE}{fid}/annual-return/'):
            self.assertEqual(self.get(path).status_code, 302, path)
        self.post(f'{BASE}add/', self.fdata())
        self.post(f'{BASE}{fid}/whitewash/add/', {})
        self.assertEqual(FactoryRegistration.objects.filter(company=self.c1).count(), 1)

    @direct
    def test_off_without_statutory_row(self, _):
        self.stat.delete()
        self.assertFalse(self.get(BASE).context['on'])

    # -- registration -----------------------------------------------------------------
    @direct
    def test_register_factory_uppercases_and_audits(self, _):
        with patch('Capp.direct.factory.log_action') as log:
            r = self.post(f'{BASE}add/', self.fdata())
        self.assertEqual(r.status_code, 302, r.content[:400])
        f = FactoryRegistration.objects.get(factory_license_no='FL-9')
        self.assertEqual(f.company, self.c1)
        self.assertEqual(log.call_args_list[0][0][1], 'factory.add')

    @direct
    def test_register_validation(self, _):
        bad = [self.fdata(factory_license_no='FL-1'),                      # duplicate
               self.fdata(factory_license_no='FL-2'),                      # other company's licence
               self.fdata(factory_license_no='bad licence!'),
               self.fdata(factory_area_sqm='0'),
               self.fdata(max_workers_day='0', max_workers_night='0'),
               self.fdata(total_hp_used='-1')]
        for d in bad:
            self.assertEqual(self.post(f'{BASE}add/', d).status_code, 200, d)
        self.assertEqual(FactoryRegistration.objects.count(), 2)

    @direct
    def test_edit_keeps_own_licence(self, _):
        r = self.post(f'{BASE}{self.f.pk}/edit/', self.fdata(factory_license_no='fl-1', manager_name='New'))
        self.assertEqual(r.status_code, 302, r.content[:400])
        self.f.refresh_from_db()
        self.assertEqual(self.f.manager_name, 'New')

    @direct
    def test_certificate_pdf(self, _):
        r = self.get(f'{BASE}{self.f.pk}/certificate/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

    # -- whitewash / vessels / accidents ------------------------------------------------
    @direct
    def test_whitewash_add_list_pdf_delete(self, _):
        fid = self.f.pk
        self.assertEqual(self.get(f'{BASE}{fid}/whitewash/download/').status_code, 302)      # empty
        r = self.post(f'{BASE}{fid}/whitewash/add/', {
            'area_description': 'Hall', 'type_of_work': 'Lime', 'date_done': TODAY.isoformat(),
            'next_due_date': (TODAY + timedelta(days=365)).isoformat(), 'contractor_name': ''})
        self.assertEqual(r.status_code, 302, r.content[:400])
        w = FactoryWhitewashRegister.objects.get()
        self.assertEqual(len(self.get(f'{BASE}{fid}/whitewash/').context['rows']), 1)
        r = self.get(f'{BASE}{fid}/whitewash/download/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))
        self.assertEqual(self.get(f'{BASE}{fid}/whitewash/{w.pk}/delete/').status_code, 405)
        self.post(f'{BASE}{fid}/whitewash/{w.pk}/delete/')
        self.assertEqual(FactoryWhitewashRegister.objects.count(), 0)

    @direct
    def test_whitewash_validation(self, _):
        base = {'area_description': 'Hall', 'type_of_work': 'Lime', 'contractor_name': ''}
        for d in ({**base, 'date_done': TODAY.isoformat(), 'next_due_date': (TODAY - timedelta(days=1)).isoformat()},
                  {**base, 'date_done': (TODAY + timedelta(days=2)).isoformat(),
                   'next_due_date': (TODAY + timedelta(days=9)).isoformat()}):
            self.assertEqual(self.post(f'{BASE}{self.f.pk}/whitewash/add/', d).status_code, 200, d)
        self.assertEqual(FactoryWhitewashRegister.objects.count(), 0)

    @direct
    def test_vessel_add_validation_and_pdf(self, _):
        fid = self.f.pk
        data = {'vessel_description': 'Boiler', 'exam_date': TODAY.isoformat(), 'examiner_name': 'Inspector',
                'max_permissible_pressure': '10', 'is_fit_for_use': 'on'}
        self.assertEqual(self.post(f'{BASE}{fid}/vessels/add/', {**data, 'max_permissible_pressure': '-1'}).status_code, 200)
        self.assertEqual(self.post(f'{BASE}{fid}/vessels/add/', data).status_code, 302)
        self.assertTrue(FactoryVesselExamination.objects.get().is_fit_for_use)
        r = self.get(f'{BASE}{fid}/vessels/download/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

    @direct
    def test_accident_add_scoping_and_validation(self, _):
        fid = self.f.pk
        base = {'employee': self.emps[0].pk, 'accident_date': TODAY.isoformat(), 'nature_of_accident': 'Fall',
                'injury_description': 'Bruise', 'days_lost': '2'}
        bad = [{**base, 'employee': self.other_emps[0].pk},                       # other tenant's employee
               {**base, 'days_lost': '-1'},
               {**base, 'reported_to_dish': 'on'},                                 # no DISH reference
               {**base, 'accident_date': (TODAY + timedelta(days=1)).isoformat()}]
        for d in bad:
            self.assertEqual(self.post(f'{BASE}{fid}/accidents/add/', d).status_code, 200, d)
        self.assertEqual(self.post(f'{BASE}{fid}/accidents/add/',
                                   {**base, 'reported_to_dish': 'on', 'dish_reference_no': 'D1'}).status_code, 302)
        self.assertEqual(self.post(f'{BASE}{fid}/accidents/add/', {**base, 'employee': ''}).status_code, 302)
        self.assertEqual(FactoryAccidentRegister.objects.count(), 2)
        r = self.get(f'{BASE}{fid}/accidents/download/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

    # -- Form 34 -----------------------------------------------------------------------
    @direct
    def test_form34_prefills_from_finalized_payroll_and_accidents(self, _):
        self.batch(11)
        self.batch(12, status='PROCESSED')                                           # not finalized
        FactoryAccidentRegister.objects.create(factory=self.f, accident_date=date(YEAR, 5, 1),
                                               nature_of_accident='x', injury_description='y')
        FactoryAccidentRegister.objects.create(factory=self.f, accident_date=date(YEAR - 1, 5, 1),
                                               nature_of_accident='x', injury_description='y')
        ini = self.get(f'{BASE}{self.f.pk}/annual-return/add/?year={YEAR}').context['form'].initial
        self.assertEqual((ini['total_workers_male'], ini['total_workers_female'], ini['total_accidents']), (2, 0, 1))
        self.assertGreater(ini['total_wages_paid'], 0)
        strict = fr.compute_form34_defaults(self.c1, self.f, YEAR)
        loose = fr.compute_form34_defaults(self.c1, self.f, YEAR, statuses=None)
        self.assertGreater(loose['total_wages_paid'], strict['total_wages_paid'])

    def ar_data(self, **kw):
        return {'year': YEAR, 'total_workers_male': '2', 'total_workers_female': '0', 'total_man_days': '52',
                'total_overtime_hours': '0', 'total_accidents': '0', 'total_wages_paid': '30000',
                'filing_status': 'Draft', 'acknowledgement_no': '', **kw}

    @direct
    def test_form34_add_duplicate_status_rules(self, _):
        url = f'{BASE}{self.f.pk}/annual-return/add/'
        with patch('Capp.direct.factory.log_action') as log:
            self.assertEqual(self.post(url, self.ar_data()).status_code, 302)
        self.assertEqual(log.call_args_list[0][0][1], 'factory.annual-return.add')
        self.assertEqual(self.post(url, self.ar_data()).status_code, 200)                     # duplicate year
        self.assertEqual(self.post(url, self.ar_data(year=YEAR - 1, filing_status='Acknowledged')).status_code, 200)
        self.assertEqual(self.post(url, self.ar_data(year=YEAR - 1, total_man_days='-1')).status_code, 200)
        self.assertEqual(self.post(url, self.ar_data(year=1999)).status_code, 200)
        self.assertEqual(self.post(url, self.ar_data(year=TODAY.year + 1)).status_code, 200)
        self.assertEqual(FactoryAnnualReturn.objects.count(), 1)
        # same year is fine for another factory
        other_f = self.fac('FL-3', self.c1)
        self.assertEqual(self.post(f'{BASE}{other_f.pk}/annual-return/add/', self.ar_data()).status_code, 302)

    @direct
    def test_form34_edit_delete_lock_and_pdf(self, _):
        fid = self.f.pk
        self.post(f'{BASE}{fid}/annual-return/add/', self.ar_data())
        rec = FactoryAnnualReturn.objects.get()
        r = self.post(f'{BASE}{fid}/annual-return/{rec.pk}/edit/', self.ar_data(
            filing_status='Acknowledged', acknowledgement_no='ACK9'))
        self.assertEqual(r.status_code, 302, r.content[:400])
        rec.refresh_from_db()
        self.assertEqual(rec.filing_status, 'Acknowledged')
        r = self.get(f'{BASE}{fid}/annual-return/{rec.pk}/download/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))
        self.post(f'{BASE}{fid}/annual-return/{rec.pk}/delete/')                              # filed: locked
        self.assertTrue(FactoryAnnualReturn.objects.filter(pk=rec.pk).exists())
        rec.filing_status = 'Draft'
        rec.save()
        self.assertEqual(self.get(f'{BASE}{fid}/annual-return/{rec.pk}/delete/').status_code, 405)
        self.post(f'{BASE}{fid}/annual-return/{rec.pk}/delete/')
        self.assertEqual(FactoryAnnualReturn.objects.count(), 0)

    # -- tenant isolation ----------------------------------------------------------------
    @direct
    def test_other_company_factory_is_404_everywhere(self, _):
        of = self.of.pk
        w = self.ww(self.of)
        ar = FactoryAnnualReturn.objects.create(factory=self.of, year=YEAR)
        for path in (f'{BASE}{of}/edit/', f'{BASE}{of}/certificate/', f'{BASE}{of}/whitewash/',
                     f'{BASE}{of}/whitewash/add/', f'{BASE}{of}/whitewash/download/', f'{BASE}{of}/annual-return/',
                     f'{BASE}{of}/annual-return/add/', f'{BASE}{of}/annual-return/{ar.pk}/edit/',
                     f'{BASE}{of}/annual-return/{ar.pk}/download/'):
            self.assertEqual(self.get(path).status_code, 404, path)
        self.assertEqual(self.post(f'{BASE}{of}/whitewash/{w.pk}/delete/').status_code, 404)
        self.assertEqual(self.post(f'{BASE}{of}/annual-return/{ar.pk}/delete/').status_code, 404)
        self.assertEqual(self.post(f'{BASE}{of}/whitewash/add/', {}).status_code, 404)

    @direct
    def test_cannot_reach_other_factorys_entry_through_own_factory(self, _):
        w = self.ww(self.of)
        ar = FactoryAnnualReturn.objects.create(factory=self.of, year=YEAR)
        fid = self.f.pk
        self.assertEqual(self.post(f'{BASE}{fid}/whitewash/{w.pk}/delete/').status_code, 404)
        self.assertEqual(self.get(f'{BASE}{fid}/annual-return/{ar.pk}/edit/').status_code, 404)
        self.assertEqual(self.get(f'{BASE}{fid}/annual-return/{ar.pk}/download/').status_code, 404)
        self.assertTrue(FactoryWhitewashRegister.objects.filter(pk=w.pk).exists())

    @direct
    def test_home_lists_only_own_factories(self, _):
        self.assertEqual([f.pk for f in self.get(BASE).context['factories']], [self.f.pk])


@override_settings(ALLOWED_HOSTS=['*'])
class FactoryServiceTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK Foods', 'AAAAA1111A')
        self.f = FactoryRegistration.objects.create(
            company=self.c1, factory_license_no='FL-1', occupier_name='O', manager_name='M',
            factory_area_sqm=D('1'), total_hp_used=D('1'), max_workers_day=1, max_workers_night=0,
            license_expiry_date=TODAY)

    def test_empty_registers_raise_with_aapp_messages(self):
        for build, msg in ((fr.build_whitewash_register_pdf, 'No whitewash records found for this factory.'),
                           (fr.build_vessel_register_pdf, 'No vessel examination records found for this factory.'),
                           (fr.build_accident_register_pdf, 'No accident records found for this factory.')):
            with self.assertRaises(NothingToGenerate) as cm:
                build(self.c1, self.f)
            self.assertEqual(str(cm.exception), msg)

    def test_certificate_and_return_filenames(self):
        pdf, name = fr.build_factory_certificate_pdf(self.c1, self.f)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(name, 'Factory_Registration_FL-1.pdf')
        rec = FactoryAnnualReturn.objects.create(factory=self.f, year=2026)
        self.assertEqual(fr.build_factory_annual_return_pdf(self.c1, rec)[1], 'Factory_AnnualReturn_FL-1_2026.pdf')
