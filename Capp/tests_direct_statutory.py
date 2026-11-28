"""D1 tests - statutory setup for DIRECT companies."""
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.statutory_gates import get_company_gates, lwf_allowed
from Capp.models import CompanyOwnerProfile
from Capp.tests_masters import HOST, make_company
from Sapp.app.company import company_statury

URL = '/direct/statutory/'
VALID = {
    'epfo': 'HRGGN0012345000', 'esic': '12345678901234567',
    'shop_act': 'SA/123', 'labour': 'LL-45', 'pt_number': 'PT9988',
}


def direct(fn):
    return patch('Capp.direct.guards.get_mode', return_value='DIRECT')(fn)


@override_settings(ALLOWED_HOSTS=['*'])
class StatutorySetupTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK', 'AAAAA1111A')
        self.c2 = make_company('Other', 'BBBBB2222B')
        self.user = User.objects.create_user('owner', password='x')
        CompanyOwnerProfile.objects.create(user=self.user, company=self.c1)
        self.client.login(username='owner', password='x')

    def post(self, data):
        return self.client.post(URL, data, **HOST)

    # -- access --------------------------------------------------------------
    def test_login_required(self):
        self.client.logout()
        r = self.client.get(URL, **HOST)
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r['Location'])

    def test_associate_mode_blocked(self):                 # default mode is ASSOCIATE
        self.assertEqual(self.client.get(URL, **HOST).status_code, 302)
        self.assertEqual(self.post(VALID).status_code, 302)
        self.assertFalse(company_statury.objects.filter(company=self.c1).exists())

    @direct
    def test_permission_denied(self, _):
        with patch('Capp.access.has_perm', return_value=False):
            self.assertEqual(self.post(VALID).status_code, 302)
        self.assertFalse(company_statury.objects.filter(company=self.c1).exists())

    # -- happy path and gates --------------------------------------------------
    @direct
    def test_page_loads(self, _):
        self.assertEqual(self.client.get(URL, **HOST).status_code, 200)

    @direct
    def test_save_switches_gates_on(self, _):
        g = get_company_gates(self.c1)
        self.assertFalse(g['epf'] or g['esi'] or g['shop_act'] or lwf_allowed(g) or g['pt'])
        r = self.post(VALID)
        self.assertEqual(r.status_code, 302, r.content[:400])
        g = get_company_gates(self.c1)
        self.assertTrue(g['epf'] and g['esi'] and g['shop_act'])
        self.assertTrue(lwf_allowed(g))

    @direct
    def test_values_normalised(self, _):
        self.post({**VALID, 'epfo': 'hrggn0012345000'})
        self.assertEqual(company_statury.objects.get(company=self.c1).epfo, 'HRGGN0012345000')

    @direct
    def test_clearing_esic_switches_it_off_and_warns(self, _):
        self.post(VALID)
        r = self.client.post(URL, {**VALID, 'esic': ''}, follow=True, **HOST)
        self.assertFalse(get_company_gates(self.c1)['esi'])
        self.assertIn('ESIC number removed', ''.join(str(m) for m in r.context['messages']))

    @direct
    def test_lwf_needs_shop_act(self, _):
        self.post({**VALID, 'shop_act': ''})
        self.assertFalse(lwf_allowed(get_company_gates(self.c1)))

    @direct
    def test_second_save_updates_same_row(self, _):
        self.post(VALID)
        self.post({**VALID, 'pt_number': 'PT1111'})
        rows = company_statury.objects.filter(company=self.c1)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows[0].pt_number, 'PT1111')

    # -- validation ------------------------------------------------------------
    @direct
    def test_invalid_values_rejected(self, _):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        bad = [
            {'epfo': 'SHORT'}, {'epfo': 'HRGGN00123450-0'},
            {'esic': '1234'}, {'esic': 'ABCDEFGHIJKLMNOPQ'},
            {'gst': '06ABCDE1234F1'}, {'shop_act': 'bad number!'},
            {'epfo_date': tomorrow},
            {'labour_from': '2025-05-01', 'labour_to': '2025-01-01'},
        ]
        for data in bad:
            r = self.post(data)
            self.assertEqual(r.status_code, 200, data)
        self.assertFalse(company_statury.objects.filter(company=self.c1).exists())

    @direct
    def test_valid_gstin_accepted(self, _):
        self.assertEqual(self.post({'gst': '06ABCDE1234F1Z5'}).status_code, 302)

    # -- tenant isolation ------------------------------------------------------
    @direct
    def test_other_company_row_untouched(self, _):
        other = company_statury.objects.create(company=self.c2, epfo='ZZZZZ0000000000')
        self.post(VALID)
        other.refresh_from_db()
        self.assertEqual(other.epfo, 'ZZZZZ0000000000')
        self.assertEqual(company_statury.objects.get(company=self.c1).epfo, VALID['epfo'])

    # -- audit -----------------------------------------------------------------
    @direct
    def test_audit_logged_on_change_only(self, _):
        with patch('Capp.direct.statutory.log_action') as log:
            self.post(VALID)
            self.assertEqual(log.call_count, 1)
            self.assertEqual(log.call_args[0][1], 'statutory.update')
            self.post(VALID)                               # no change
            self.assertEqual(log.call_count, 1)
