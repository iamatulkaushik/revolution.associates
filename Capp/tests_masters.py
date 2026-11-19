from datetime import date
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from Aapp.app.branch_department import branch, department
from Aapp.app.designation import designation
from Capp.models import CompanyOwnerProfile
from Sapp.app.bank import bank_name
from Sapp.app.company import Company
from Sapp.app.state_district import State, District

HOST = {'HTTP_HOST': 'capp.localhost'}


def make_company(name, pan):
    st, _ = State.objects.get_or_create(name='Haryana')
    di, _ = District.objects.get_or_create(state=st, name='Sonipat')
    return Company.objects.create(company_name=name, start_date=date(2020, 1, 1), state_id=st,
                                  district_id=di, mobile='9999999999', email1='a@b.com', pan=pan)


@override_settings(ALLOWED_HOSTS=['*'])
class MastersTests(TestCase):
    def setUp(self):
        self.c1 = make_company('JSK', 'AAAAA1111A')
        self.c2 = make_company('Other', 'BBBBB2222B')
        self.user = User.objects.create_user('owner', password='x')
        self.profile = CompanyOwnerProfile.objects.create(user=self.user, company=self.c1)
        self.client.login(username='owner', password='x')

    def test_branch_department_designation_flow(self):
        r = self.client.post('/masters/branches/add/', {'branch_name': 'Murthal'}, **HOST)
        self.assertEqual(r.status_code, 302, r.content[:300])
        b = branch.objects.get(branch_name='Murthal')
        self.assertEqual(b.companyid, self.c1)
        r = self.client.post('/masters/departments/add/', {'department_name': 'S.P', 'branch': b.pk}, **HOST)
        self.assertEqual(r.status_code, 302)
        r = self.client.post('/masters/designations/add/',
                             {'designationname': 'Helper', 'basicpay': '15221', 'hra': '2779',
                              'is_active': 'on'}, **HOST)
        self.assertEqual(r.status_code, 302, r.content[:500])
        d = designation.objects.get(designationname='Helper')
        self.assertEqual(d.company, self.c1)
        self.assertEqual(d.da, 0)
        for url in ('/masters/branches/', '/masters/departments/', '/masters/designations/',
                    '/masters/company/'):
            self.assertEqual(self.client.get(url, **HOST).status_code, 200, url)

    def test_duplicate_branch_rejected(self):
        branch.objects.create(branch_name='Murthal', companyid=self.c1, created_by=self.user)
        r = self.client.post('/masters/branches/add/', {'branch_name': 'murthal'}, **HOST)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(branch.objects.filter(companyid=self.c1).count(), 1)

    def test_tenant_isolation(self):
        other = branch.objects.create(branch_name='X', companyid=self.c2, created_by=self.user)
        self.assertEqual(self.client.get(f'/masters/branches/{other.pk}/edit/', **HOST).status_code, 404)
        self.assertEqual(self.client.post(f'/masters/branches/{other.pk}/delete/', **HOST).status_code, 404)
        self.assertTrue(branch.objects.filter(pk=other.pk).exists())

    def test_permission_flag(self):
        self.profile.can_manage_masters = False
        self.profile.save()
        r = self.client.get('/masters/branches/', **HOST)
        self.assertEqual(r.status_code, 302)

    def test_company_bank_validation(self):
        bk = bank_name.objects.create(name='Canara Bank')
        base = {'bank_id': bk.pk, 'account': '1234567890', 'ifsc': 'cnrb0001234', 'mobile': '9999999999',
                'email1': 'a@b.com'}
        r = self.client.post('/masters/company/', base, **HOST)
        self.assertEqual(r.status_code, 302, r.content[:400])
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.ifsc, 'CNRB0001234')
        self.assertEqual(self.c1.company_name, 'JSK')
        bad = dict(base, ifsc='BAD')
        self.assertEqual(self.client.post('/masters/company/', bad, **HOST).status_code, 200)
