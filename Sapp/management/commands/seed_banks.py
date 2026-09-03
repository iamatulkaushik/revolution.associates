"""
Seed the standard list of Indian banks into bank_name.
Run manually: python manage.py seed_banks

Replaces a dead post_migrate signal that was previously nested inside
bank_form (a method definition inside a class body, never actually
connected to the signal — it silently never ran). Matches this
codebase's established pattern: explicit management commands over
signals for seed data, and module-level definitions only.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from Sapp.app.bank import bank_name, INDIAN_BANKS


class Command(BaseCommand):
    help = "Seed the standard list of Indian banks (idempotent)."

    def handle(self, *args, **options):
        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            for name in INDIAN_BANKS:
                _, created = bank_name.objects.get_or_create(name=name)
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Banks seeded: {created_count} created, {skipped_count} already existed."
        ))
