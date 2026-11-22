from datetime import date

from django.test import SimpleTestCase, TestCase

from Capp.access import PERMISSIONS, get_mode
from Capp.tests_masters import make_company
from revolution.app import plan_limits as pl


class PlanLimitContract(TestCase):
    def setUp(self):
        self.co = make_company('JSK', 'AAAAA1111A')

    def test_copper_limit_is_150(self):
        self.assertEqual(self.co.plan, 'copper')
        self.assertEqual(pl.employee_limit(self.co), 150)
        self.assertEqual(pl.remaining(self.co), 150)

    def test_check_can_add_blocks_only_adding(self):
        pl.check_can_add(self.co, 150)                     # exactly at the limit: allowed
        with self.assertRaises(pl.PlanLimitExceeded) as cm:
            pl.check_can_add(self.co, 151)
        self.assertEqual((cm.exception.limit, cm.exception.current), (150, 0))

    def test_plan_without_default_is_unlimited(self):
        self.co.plan = 'silver'                  # limit comes from the licence when issued
        pl.check_can_add(self.co, 10 ** 6)
        self.assertIsNone(pl.remaining(self.co))


class AccessContract(SimpleTestCase):
    def test_permission_names_frozen(self):
        self.assertEqual(len(PERMISSIONS), len(set(PERMISSIONS)))
        self.assertIn('payroll.finalize', PERMISSIONS)

    def test_default_mode(self):
        class C: pass
        self.assertEqual(get_mode(C()), 'ASSOCIATE')
