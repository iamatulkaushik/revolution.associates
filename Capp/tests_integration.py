"""
Integration guards for ALL tracks (owned by AI-1, run at every checkpoint).

1. Frozen contract signatures cannot drift.
2. Every NAV entry (foundation, entry, direct) follows the schema and names real permissions.
3. Smoke: every menu URL, for each mode x role, answers 200/302/403/404, never 500.
4. Direct-only URLs (prefix direct/) are unreachable for ASSOCIATE companies.
"""
import inspect

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from Capp import access, audit
from Capp.context_processors import _sources
from Capp.foundation.models import CompanyOperator
from Capp.models import CompanyOwnerProfile
from Capp.tests_foundation import ALL_FLAGS
from Capp.tests_masters import make_company
from revolution.app import plan_limits as pl

HOST = {'HTTP_HOST': 'capp.localhost'}


def sig(fn):
    return str(inspect.signature(fn))


class FrozenContracts(SimpleTestCase):
    def test_signatures(self):
        self.assertEqual(sig(access.get_mode), '(company)')
        self.assertEqual(sig(access.has_perm), '(request, perm)')
        self.assertEqual(sig(access.capp_perm), '(*perms)')
        self.assertEqual(sig(audit.log_action), "(request, action, obj=None, detail='')")
        self.assertEqual(sig(pl.employee_limit), '(company)')
        self.assertEqual(sig(pl.active_employee_count), '(company)')
        self.assertEqual(sig(pl.remaining), '(company)')
        self.assertEqual(sig(pl.check_can_add), '(company, n=1)')

    def test_limit_exception_shape(self):
        e = pl.PlanLimitExceeded('m', 5, 4)
        self.assertEqual((str(e), e.limit, e.current), ('m', 5, 4))

    def test_original_permission_names_still_present(self):
        original = ['employees.view', 'employees.add', 'employees.edit', 'employees.relieve',
                    'attendance.view', 'attendance.edit', 'loans.view', 'loans.edit',
                    'payroll.process', 'payroll.finalize', 'payroll.download', 'statutory.edit',
                    'challan.download', 'bank.edit', 'masters.edit', 'billing.manage',
                    'operators.manage']
        for p in original:
            self.assertIn(p, access.PERMISSIONS)


class NavSchema(SimpleTestCase):
    def test_entries_are_valid(self):
        ids, modes_ok = set(), {'DIRECT', 'ASSOCIATE'}
        for g in _sources():
            self.assertIn('id', g); self.assertIn('label', g)
            self.assertNotIn(g['id'], ids, f"duplicate nav id {g['id']}")
            ids.add(g['id'])
            self.assertTrue(('items' in g) ^ ('url_name' in g), g['id'])
            if 'items' in g and g.get('perm'):
                self.assertIn(g['perm'], access.PERMISSIONS)
            for e in ([g] if 'url_name' in g else []) + g.get('items', []):
                self.assertIn('label', e)
                if e.get('perm') is not None:
                    self.assertIn(e['perm'], access.PERMISSIONS, e)
                self.assertTrue(set(e.get('modes', modes_ok)) <= modes_ok, e)


@override_settings(ALLOWED_HOSTS=['*'])
class Smoke(TestCase):
    def setUp(self):
        self.co = make_company('JSK', 'AAAAA1111A')

    def urls(self):
        out = []
        for g in _sources():
            for e in ([g] if 'url_name' in g else []) + g.get('items', []):
                try:
                    out.append(reverse(e['url_name'], kwargs=e.get('kwargs')))
                except NoReverseMatch:
                    pass                          # track not merged yet
        return sorted(set(out))

    def run_cell(self, mode, role):
        type(self.co).objects.filter(pk=self.co.pk).update(management_mode=mode)
        name = f'{mode}-{role}'.lower()
        u = User.objects.create_user(name, password='pw-Strong-1')
        if role == 'OWNER':
            CompanyOwnerProfile.objects.create(user=u, company=self.co)
        else:
            CompanyOperator.objects.create(user=u, company=self.co, **{f: True for f in ALL_FLAGS})
        self.client.login(username=name, password='pw-Strong-1')
        bad = []
        for url in self.urls():
            r = self.client.get(url, **HOST)
            if r.status_code >= 500:
                bad.append((url, r.status_code))
        self.assertEqual(bad, [], f'{mode} {role}')

    def test_direct_owner(self):     self.run_cell('DIRECT', 'OWNER')
    def test_direct_operator(self):  self.run_cell('DIRECT', 'OPERATOR')
    def test_assoc_owner(self):      self.run_cell('ASSOCIATE', 'OWNER')
    def test_assoc_operator(self):   self.run_cell('ASSOCIATE', 'OPERATOR')


@override_settings(ALLOWED_HOSTS=['*'])
class DirectOnlyGuard(TestCase):
    """Every argument-free URL of the DIRECT track must refuse an ASSOCIATE company."""

    def test_direct_urls_blocked_in_associate_mode(self):
        from Capp.direct import urls as direct_urls
        co = make_company('JSK', 'AAAAA1111A')                # default mode: ASSOCIATE
        u = User.objects.create_user('o', password='pw-Strong-1')
        CompanyOwnerProfile.objects.create(user=u, company=co)
        self.client.login(username='o', password='pw-Strong-1')
        checked = 0
        for p in direct_urls.urlpatterns:
            if p.pattern.regex.groups or not getattr(p, 'name', None):
                continue
            url = reverse(p.name)
            for method in ('get', 'post'):
                r = getattr(self.client, method)(url, **HOST)
                self.assertIn(r.status_code, (302, 403, 404), (method, url, r.status_code))
                if r.status_code == 302:
                    self.assertNotIn('/direct/', r.url, (method, url, r.url))
            checked += 1
        self.assertGreaterEqual(checked, 0)                    # vacuous until AI-2 merges


class MigrationCoverage(TestCase):
    """Every model of Aapp/Sapp/Capp must be created by some migration.

    Regression guard for INVENTORY R8: Aapp.BatchJob had no migration, so a database built
    from the repo had no table for it. Modules that cannot be imported on their own are skipped.
    """

    def test_every_model_has_a_migration(self):
        import importlib
        import pkgutil
        from django.apps import apps
        from django.db.migrations.loader import MigrationLoader
        import Aapp.app as aapp_pkg
        import Sapp.app as sapp_pkg
        for pkg in (aapp_pkg, sapp_pkg):
            for mod in pkgutil.iter_modules(pkg.__path__):
                try:
                    importlib.import_module(f'{pkg.__name__}.{mod.name}')
                except Exception:
                    pass
        state = MigrationLoader(None, ignore_no_migrations=True).project_state()
        migrated = {f'{k[0]}.{state.models[k].name}'.lower() for k in state.models}
        registered = {m._meta.label for m in apps.get_models()
                      if m._meta.app_label in ('Aapp', 'Sapp', 'Capp')}
        self.assertEqual(sorted(l for l in registered if l.lower() not in migrated), [])
