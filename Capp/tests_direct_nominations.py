"""D5b-2 tests - nomination, family declaration, gratuity nominee and leave-with-wages registers."""
from datetime import date, timedelta
from decimal import Decimal as D
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.epf_esi import EpfNomination, EsiFamilyMember
from Aapp.app.factory_act import LeaveWithWagesRegister
from Aapp.app.gratuity import gratuity_nominee
from Aapp.app.services import nominations as nm
from Aapp.app.services.statutory_files import NothingToGenerate
from Capp.models import CompanyOwnerProfile
from Capp.tests_direct_payroll import add_staff
from Capp.tests_masters import HOST, make_company
from Sapp.app.company import company_statury

BASE = '/direct/nominations/'
KEYS = ('epf-nominations', 'esi-family', 'gratuity-nominees', 'leave-wages')
TODAY = date.today()


def direct(fn):
    return patch('Capp.direct.guards.get_mode', return_value='DIRECT')(fn)


@override_settings(ALLOWED_HOSTS=['*'])
class NominationTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK', 'AAAAA1111A')
        self.c2 = make_company('Other', 'BBBBB2222B')
        self.user = User.objects.create_user('owner', password='x')
        CompanyOwnerProfile.objects.create(user=self.user, company=self.c1)
        self.client.login(username='owner', password='x')
        self.emps = add_staff(self.c1, self.user)
        self.other_emps = add_staff(self.c2, self.user, n=1)
        self.stat = company_statury.objects.create(
            company=self.c1, epfo='HRGGN0012345000', esic='12345678901234567', shop_act='SA/1')

    def get(self, path):
        return self.client.get(path, **HOST)

    def post(self, path, data=None):
        return self.client.post(path, data or {}, **HOST)

    # fixtures ---------------------------------------------------------------------
    def epf_data(self, emp=None, **kw):
        return {'employee': (emp or self.emps[0]).pk, 'nominee_name': 'Asha', 'relationship': 'spouse',
                'share_percent': '60', 'nomination_date': '2026-01-10', **kw}

    def epf(self, emp=None, share='50', company=None):
        company = company or self.c1
        return EpfNomination.objects.create(
            company=company, employee=emp or self.emps[0], nominee_name='Asha', relationship='spouse',
            share_percent=D(share), nomination_date=date(2026, 1, 10))

    def esi(self, emp=None, company=None):
        return EsiFamilyMember.objects.create(
            company=company or self.c1, employee=emp or self.emps[0], member_name='Ravi',
            relationship='son', gender='Male')

    def grat_data(self, emp=None, **kw):
        return {'employee': (emp or self.emps[0]).pk, 'nominee_name': 'Asha', 'relationship': 'spouse',
                'gender': 'Female', 'share_percent': '100', 'address': 'Gurgaon', **kw}

    def leave_data(self, emp=None, **kw):
        return {'employee': (emp or self.emps[0]).pk, 'year': TODAY.year, 'opening_balance': '5',
                'leave_earned': '10', 'leave_availed': '4', 'leave_lapsed': '0', 'leave_encashed': '2',
                'encashment_amount': '1500', **kw}

    # -- access ------------------------------------------------------------------
    def test_associate_mode_blocked(self):
        paths = [BASE] + [f'{BASE}{k}/{s}' for k in KEYS for s in ('', 'add/', 'download/')]
        for path in paths:
            self.assertEqual(self.get(path).status_code, 302, path)
        self.assertEqual(self.post(f'{BASE}gratuity-nominees/add/', self.grat_data()).status_code, 302)
        self.assertEqual(gratuity_nominee.objects.count(), 0)

    @direct
    def test_permission_denied(self, _):
        with patch('Capp.access.has_perm', return_value=False):
            self.assertEqual(self.get(BASE).status_code, 302)
            self.assertEqual(self.post(f'{BASE}gratuity-nominees/add/', self.grat_data()).status_code, 302)
        self.assertEqual(gratuity_nominee.objects.count(), 0)

    @direct
    def test_pages_load_and_unknown_key_404(self, _):
        self.assertEqual(self.get(BASE).status_code, 200)
        for k in KEYS:
            self.assertEqual(self.get(f'{BASE}{k}/').status_code, 200, k)
            self.assertEqual(self.get(f'{BASE}{k}/add/').status_code, 200, k)
        self.assertEqual(self.get(f'{BASE}nothing/').status_code, 404)

    # -- gates (fail-closed) ---------------------------------------------------------
    @direct
    def test_registers_off_without_registration(self, _):
        self.stat.epfo = self.stat.esic = self.stat.shop_act = ''
        self.stat.save()
        for key, data in (('epf-nominations', self.epf_data()),
                          ('leave-wages', self.leave_data())):
            self.assertEqual(self.post(f'{BASE}{key}/add/', data).status_code, 302)
            self.assertEqual(self.get(f'{BASE}{key}/download/').status_code, 302)
            self.assertTrue(self.get(f'{BASE}{key}/').context['off'])
        self.post(f'{BASE}esi-family/add/', {'employee': self.emps[0].pk, 'member_name': 'R',
                                             'relationship': 'son', 'gender': 'Male'})
        self.assertEqual((EpfNomination.objects.count(), LeaveWithWagesRegister.objects.count(),
                          EsiFamilyMember.objects.count()), (0, 0, 0))

    @direct
    def test_gratuity_has_no_registration_gate(self, _):
        self.stat.delete()
        self.assertEqual(self.post(f'{BASE}gratuity-nominees/add/', self.grat_data()).status_code, 302)
        self.assertEqual(gratuity_nominee.objects.count(), 1)

    @direct
    def test_each_gate_is_independent(self, _):
        self.stat.esic = ''
        self.stat.save()
        self.assertTrue(self.get(f'{BASE}esi-family/').context['off'])
        self.assertFalse(self.get(f'{BASE}epf-nominations/').context['off'])

    # -- EPF nominations --------------------------------------------------------------
    @direct
    def test_epf_add_edit_delete_audited(self, _):
        with patch('Capp.direct.nominations.log_action') as log:
            r = self.post(f'{BASE}epf-nominations/add/', self.epf_data())
            self.assertEqual(r.status_code, 302, r.content[:400])
            n = EpfNomination.objects.get()
            self.assertEqual((n.company, n.created_by), (self.c1, self.user))
            r = self.post(f'{BASE}epf-nominations/{n.pk}/edit/', self.epf_data(nominee_name='Asha K'))
            self.assertEqual(r.status_code, 302, r.content[:400])
            self.assertEqual(EpfNomination.objects.get().nominee_name, 'Asha K')
            self.post(f'{BASE}epf-nominations/{n.pk}/delete/')
        self.assertEqual(EpfNomination.objects.count(), 0)
        self.assertEqual([c[0][1] for c in log.call_args_list],
                         ['nomination.epf-nominations.add', 'nomination.epf-nominations.edit',
                          'nomination.epf-nominations.delete'])

    @direct
    def test_epf_share_cap_and_warning(self, _):
        self.epf(share='60')
        r = self.post(f'{BASE}epf-nominations/add/', self.epf_data(share_percent='50'))
        self.assertEqual(r.status_code, 200)                      # 110% refused
        self.assertEqual(EpfNomination.objects.count(), 1)
        warn = self.get(f'{BASE}epf-nominations/').context['warnings']
        self.assertEqual(len(warn), 1)                            # 60% is not 100%
        r = self.post(f'{BASE}epf-nominations/add/', self.epf_data(share_percent='40'))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.get(f'{BASE}epf-nominations/').context['warnings'], [])

    @direct
    def test_epf_editing_own_share_is_not_double_counted(self, _):
        n = self.epf(share='100')
        r = self.post(f'{BASE}epf-nominations/{n.pk}/edit/', self.epf_data(share_percent='100'))
        self.assertEqual(r.status_code, 302)

    @direct
    def test_epf_validation(self, _):
        bad = [self.epf_data(share_percent='0'), self.epf_data(share_percent='101'),
               self.epf_data(aadhar_number='123'), self.epf_data(bank_ifsc='BAD'),
               self.epf_data(bank_account='12'), self.epf_data(is_minor='on'),     # no guardian
               self.epf_data(nomination_date=(TODAY + timedelta(days=2)).isoformat()),
               self.epf_data(emp=self.other_emps[0])]                              # other tenant
        for data in bad:
            self.assertEqual(self.post(f'{BASE}epf-nominations/add/', data).status_code, 200, data)
        self.assertEqual(EpfNomination.objects.count(), 0)

    @direct
    def test_epf_minor_with_guardian_ok(self, _):
        r = self.post(f'{BASE}epf-nominations/add/',
                      self.epf_data(is_minor='on', guardian_name='Mohan', aadhar_number='123456789012'))
        self.assertEqual(r.status_code, 302, r.content[:400])

    # -- gratuity -------------------------------------------------------------------
    @direct
    def test_gratuity_add_masks_aadhaar_in_list(self, _):
        r = self.post(f'{BASE}gratuity-nominees/add/', self.grat_data(aadhar_number='123456789012'))
        self.assertEqual(r.status_code, 302, r.content[:400])
        cells = self.get(f'{BASE}gratuity-nominees/').context['rows'][0]['cells']
        self.assertIn('XXXXXXXX9012', cells)
        self.assertNotIn('123456789012', cells)

    @direct
    def test_gratuity_requires_gender_and_valid_pan(self, _):
        data = self.grat_data()
        data.pop('gender')
        self.assertEqual(self.post(f'{BASE}gratuity-nominees/add/', data).status_code, 200)
        self.assertEqual(self.post(f'{BASE}gratuity-nominees/add/',
                                   self.grat_data(pan_number='abc')).status_code, 200)
        self.assertEqual(gratuity_nominee.objects.count(), 0)
        r = self.post(f'{BASE}gratuity-nominees/add/', self.grat_data(pan_number='abcde1234f'))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(gratuity_nominee.objects.get().pan_number, 'ABCDE1234F')

    # -- ESI family -----------------------------------------------------------------
    @direct
    def test_esi_add_and_remove_form_1b(self, _):
        r = self.post(f'{BASE}esi-family/add/', {'employee': self.emps[0].pk, 'member_name': 'Ravi',
                                                 'relationship': 'son', 'gender': 'Male',
                                                 'is_dependent': 'on', 'is_residing_with': 'on'})
        self.assertEqual(r.status_code, 302, r.content[:400])
        m = EsiFamilyMember.objects.get()
        self.assertTrue(self.get(f'{BASE}esi-family/{m.pk}/remove/').status_code == 200)
        r = self.post(f'{BASE}esi-family/{m.pk}/remove/',
                      {'date_removed': TODAY.isoformat(), 'reason_for_removal': 'Marriage'})
        self.assertEqual(r.status_code, 302, r.content[:400])
        m.refresh_from_db()
        self.assertEqual((m.date_removed, m.reason_for_removal), (TODAY, 'Marriage'))
        # already removed: no second removal, and the row is no longer offered for removal
        self.assertEqual(self.post(f'{BASE}esi-family/{m.pk}/remove/',
                                   {'date_removed': TODAY.isoformat(), 'reason_for_removal': 'x'}).status_code, 302)
        self.assertFalse(self.get(f'{BASE}esi-family/').context['rows'][0]['removable'])

    @direct
    def test_esi_remove_validation(self, _):
        m = self.esi()
        for data in ({'date_removed': (TODAY + timedelta(days=1)).isoformat(), 'reason_for_removal': 'x'},
                     {'date_removed': (TODAY - timedelta(days=5)).isoformat(), 'reason_for_removal': 'x'},
                     {'date_removed': TODAY.isoformat(), 'reason_for_removal': ''}):
            self.assertEqual(self.post(f'{BASE}esi-family/{m.pk}/remove/', data).status_code, 200, data)
        m.refresh_from_db()
        self.assertIsNone(m.date_removed)

    @direct
    def test_remove_only_for_esi(self, _):
        n = self.epf()
        self.assertEqual(self.get(f'{BASE}epf-nominations/{n.pk}/remove/').status_code, 404)

    # -- leave with wages -----------------------------------------------------------
    @direct
    def test_leave_add_list_balance_and_duplicate(self, _):
        r = self.post(f'{BASE}leave-wages/add/', self.leave_data())
        self.assertEqual(r.status_code, 302, r.content[:400])
        row = self.get(f'{BASE}leave-wages/').context['rows'][0]['cells']
        self.assertEqual(row[-1], D('9'))                          # 5 + 10 - 4 - 0 - 2
        self.assertEqual(self.post(f'{BASE}leave-wages/add/', self.leave_data()).status_code, 200)
        self.assertEqual(LeaveWithWagesRegister.objects.count(), 1)

    @direct
    def test_leave_validation(self, _):
        bad = [self.leave_data(leave_availed='20'),                 # more than opening + earned
               self.leave_data(opening_balance='-1'),
               self.leave_data(year='1990'),
               self.leave_data(leave_encashed='0', encashment_amount='500'),
               self.leave_data(emp=self.other_emps[0])]             # other tenant
        for data in bad:
            self.assertEqual(self.post(f'{BASE}leave-wages/add/', data).status_code, 200, data)
        self.assertEqual(LeaveWithWagesRegister.objects.count(), 0)

    @direct
    def test_leave_lists_only_own_company(self, _):
        LeaveWithWagesRegister.objects.create(employee=self.other_emps[0], year=TODAY.year)
        self.assertEqual(self.get(f'{BASE}leave-wages/').context['rows'], [])

    # -- tenant isolation -------------------------------------------------------------
    @direct
    def test_other_company_rows_not_visible_editable_or_deletable(self, _):
        other = {'epf-nominations': self.epf(self.other_emps[0], company=self.c2),
                 'esi-family': self.esi(self.other_emps[0], company=self.c2),
                 'gratuity-nominees': gratuity_nominee.objects.create(
                     company=self.c2, employee=self.other_emps[0], nominee_name='x', relationship='son',
                     address='a', share_percent=D('100'), gender='Male'),
                 'leave-wages': LeaveWithWagesRegister.objects.create(
                     employee=self.other_emps[0], year=TODAY.year)}
        pks = {'epf-nominations': 'nomination_id', 'esi-family': 'member_id',
               'gratuity-nominees': 'nominee_id', 'leave-wages': 'leave_register_id'}
        for key, obj in other.items():
            pk = getattr(obj, pks[key])
            self.assertEqual(self.get(f'{BASE}{key}/{pk}/edit/').status_code, 404, key)
            self.assertEqual(self.post(f'{BASE}{key}/{pk}/delete/').status_code, 404, key)
            self.assertEqual(self.get(f'{BASE}{key}/').context['rows'], [], key)
            self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists(), key)
        m = other['esi-family']
        self.assertEqual(self.get(f'{BASE}esi-family/{m.pk}/remove/').status_code, 404)

    @direct
    def test_delete_needs_post(self, _):
        n = self.epf()
        self.assertEqual(self.get(f'{BASE}epf-nominations/{n.pk}/delete/').status_code, 405)

    # -- downloads -------------------------------------------------------------------
    @direct
    def test_downloads_give_pdf(self, _):
        self.epf()
        self.esi()
        gratuity_nominee.objects.create(company=self.c1, employee=self.emps[0], nominee_name='x',
                                        relationship='son', address='a', share_percent=D('100'), gender='Male')
        LeaveWithWagesRegister.objects.create(employee=self.emps[0], year=TODAY.year)
        for k in KEYS:
            r = self.get(f'{BASE}{k}/download/')
            self.assertEqual(r.status_code, 200, k)
            self.assertTrue(r.content.startswith(b'%PDF'), k)

    @direct
    def test_empty_register_download_redirects(self, _):
        for k in KEYS:
            self.assertEqual(self.get(f'{BASE}{k}/download/').status_code, 302, k)

    @direct
    def test_download_excludes_other_company(self, _):
        self.epf(self.other_emps[0], company=self.c2)
        self.assertEqual(self.get(f'{BASE}epf-nominations/download/').status_code, 302)


@override_settings(ALLOWED_HOSTS=['*'])
class NominationServiceTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK Foods', 'AAAAA1111A')
        self.user = User.objects.create_user('owner', password='x')
        self.emps = add_staff(self.c1, self.user, n=1)

    def test_empty_registers_raise_with_aapp_messages(self):
        for build, msg in ((nm.build_gratuity_nominee_register_pdf, 'No gratuity nominees registered.'),
                           (nm.build_epf_nomination_register_pdf, 'No EPF nominations recorded.'),
                           (nm.build_esi_family_register_pdf, 'No ESI family members declared.'),
                           (nm.build_leave_wages_register_pdf,
                            'No leave-with-wages records found for this company.')):
            with self.assertRaises(NothingToGenerate) as cm:
                build(self.c1)
            self.assertEqual(str(cm.exception), msg)

    def test_filenames_match_aapp_pattern(self):
        EpfNomination.objects.create(company=self.c1, employee=self.emps[0], nominee_name='A',
                                     relationship='spouse', share_percent=D('100'),
                                     nomination_date=date(2026, 1, 1))
        pdf, fname = nm.build_epf_nomination_register_pdf(self.c1)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(fname, 'EPF_Nomination_Register_JSK_Foods.pdf')
        LeaveWithWagesRegister.objects.create(employee=self.emps[0], year=2026)
        self.assertEqual(nm.build_leave_wages_register_pdf(self.c1)[1], 'Leave_With_Wages_Register_JSK_Foods.pdf')
