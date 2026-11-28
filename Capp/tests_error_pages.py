"""Custom error pages are wired in EVERY URLconf (django-hosts serves each subdomain from its own)."""
import importlib

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import get_resolver

from revolution import error_views

URLCONFS = ['revolution.urls', 'Sapp.urls', 'Aapp.urls', 'Capp.urls', 'Cxapp.urls']


class HandlerWiring(SimpleTestCase):
    def test_every_urlconf_names_importable_handlers(self):
        for conf in URLCONFS:
            resolver = get_resolver(conf)
            for code in (400, 403, 404, 500):
                handler = resolver.resolve_error_handler(code)
                self.assertEqual(handler.__module__, 'revolution.error_views', (conf, code))
                self.assertEqual(handler.__name__, f'custom_{code}', (conf, code))

    def test_handler_strings_point_at_real_functions(self):
        for conf in URLCONFS:
            mod = importlib.import_module(conf)
            for code in (400, 403, 404, 500):
                path = getattr(mod, f'handler{code}')
                module, _, name = path.rpartition('.')
                self.assertTrue(callable(getattr(importlib.import_module(module), name)), (conf, path))

    def test_csrf_failure_view_is_wired(self):
        self.assertEqual(settings.CSRF_FAILURE_VIEW, 'revolution.error_views.custom_403_csrf')


@override_settings(ALLOWED_HOSTS=['*'])
class ErrorPagesAnswer(TestCase):
    def test_404_on_every_host(self):
        for host in ('www', 'sapp', 'aapp', 'capp', 'cxapp'):
            r = self.client.get('/definitely-not-a-page-xyz/', HTTP_HOST=f'{host}.localhost')
            self.assertEqual(r.status_code, 404, host)

    def test_csrf_failure_renders_the_custom_page(self):
        from django.test import Client
        r = Client(enforce_csrf_checks=True).post('/login/', {'username': 'a', 'password': 'b'},
                                                  HTTP_HOST='capp.localhost')
        self.assertEqual(r.status_code, 403)
        self.assertTemplateUsed(r, '403_csrf.html')

    def test_handlers_return_the_right_status(self):
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        req = RequestFactory().get('/x/')
        req.user = AnonymousUser()                                 # the auth middleware does this
        self.assertEqual(error_views.custom_400(req).status_code, 400)
        self.assertEqual(error_views.custom_403(req).status_code, 403)
        self.assertEqual(error_views.custom_404(req).status_code, 404)
        self.assertEqual(error_views.custom_500(req).status_code, 500)
