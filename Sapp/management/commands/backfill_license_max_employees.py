"""
Set License.max_employees on existing licences from the company's plan default.

    python manage.py backfill_license_max_employees            # dry run (default)
    python manage.py backfill_license_max_employees --apply    # write

Only licences whose max_employees is empty are touched. Plan default: copper = 150,
every other plan stays empty (unlimited). Explicit command, never a post_migrate hook.
"""
from django.core.management.base import BaseCommand

from revolution.app.plan_limits import PLAN_DEFAULTS
from Sapp.app.license import License


class Command(BaseCommand):
    help = 'Backfill License.max_employees from plan defaults (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write changes.')

    def handle(self, *args, **opts):
        todo = []
        for lic in License.objects.filter(max_employees__isnull=True).select_related('company'):
            default = PLAN_DEFAULTS.get(lic.company.plan)
            if default is not None:
                todo.append((lic, default))
        for lic, default in todo:
            self.stdout.write(f'{lic.company.company_name}: licence {lic.license_key} -> {default}')
            if opts['apply']:
                lic.max_employees = default
                lic.save(update_fields=['max_employees'])
        self.stdout.write(self.style.SUCCESS(
            f"{len(todo)} licence(s) {'updated' if opts['apply'] else 'would be updated (dry run)'}."))
