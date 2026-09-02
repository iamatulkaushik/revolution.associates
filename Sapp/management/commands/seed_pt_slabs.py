"""
Seed Professional Tax slabs for states that levy PT.
Run manually: python manage.py seed_pt_slabs
Not a post_migrate signal on purpose — PT slabs are state-notified rates
that change independently of schema migrations; auto-firing on every
migrate risks silently reapplying stale rates after a state notifies a
change. Aatul runs this deliberately and updates rates here first.

Rates are the standard published monthly PT slabs (FY 2025-26) subject
to a Rs. 2,500/year statutory cap under Article 276 of the Constitution.
Verify against current state notifications before production use.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from Sapp.app.state_district import State
from Sapp.app.professional_tax import PTSlab


# (state_name, [(salary_from, salary_to_or_None, monthly_tax), ...])
PT_SLAB_DATA = [
    ("karnataka", [
        (Decimal("0"), Decimal("24999"), Decimal("0")),
        (Decimal("25000"), None, Decimal("200")),
    ]),
    ("west bengal", [
        (Decimal("0"), Decimal("10000"), Decimal("0")),
        (Decimal("10001"), Decimal("15000"), Decimal("110")),
        (Decimal("15001"), Decimal("25000"), Decimal("130")),
        (Decimal("25001"), Decimal("40000"), Decimal("150")),
        (Decimal("40001"), None, Decimal("200")),
    ]),
    ("maharashtra", [
        (Decimal("0"), Decimal("7500"), Decimal("0")),
        (Decimal("7501"), Decimal("10000"), Decimal("175")),
        (Decimal("10001"), None, Decimal("200")),
    ]),
    ("andhra pradesh", [
        (Decimal("0"), Decimal("15000"), Decimal("0")),
        (Decimal("15001"), Decimal("20000"), Decimal("150")),
        (Decimal("20001"), None, Decimal("200")),
    ]),
    ("telangana", [
        (Decimal("0"), Decimal("15000"), Decimal("0")),
        (Decimal("15001"), Decimal("20000"), Decimal("150")),
        (Decimal("20001"), None, Decimal("200")),
    ]),
    ("madhya pradesh", [
        (Decimal("0"), Decimal("18750"), Decimal("0")),
        (Decimal("18751"), Decimal("25000"), Decimal("125")),
        (Decimal("25001"), Decimal("33333"), Decimal("167")),
        (Decimal("33334"), None, Decimal("208")),
    ]),
    ("gujarat", [
        (Decimal("0"), Decimal("11999"), Decimal("0")),
        (Decimal("12000"), None, Decimal("200")),
    ]),
    ("assam", [
        (Decimal("0"), Decimal("10000"), Decimal("0")),
        (Decimal("10001"), Decimal("15000"), Decimal("150")),
        (Decimal("15001"), Decimal("25000"), Decimal("180")),
        (Decimal("25001"), None, Decimal("208")),
    ]),
    ("tripura", [
        (Decimal("0"), Decimal("7500"), Decimal("0")),
        (Decimal("7501"), Decimal("15000"), Decimal("150")),
        (Decimal("15001"), None, Decimal("208")),
    ]),
    ("kerala", [
        (Decimal("0"), Decimal("11999"), Decimal("0")),
        (Decimal("12000"), Decimal("17999"), Decimal("120")),
        (Decimal("18000"), Decimal("29999"), Decimal("180")),
        (Decimal("30000"), Decimal("44999"), Decimal("300")),
        (Decimal("45000"), Decimal("99999"), Decimal("450")),
        (Decimal("100000"), Decimal("124999"), Decimal("600")),
        (Decimal("125000"), None, Decimal("1250")),
    ]),
    ("odisha", [
        (Decimal("0"), Decimal("13304"), Decimal("0")),
        (Decimal("13305"), Decimal("25000"), Decimal("125")),
        (Decimal("25001"), None, Decimal("200")),
    ]),
    ("meghalaya", [
        (Decimal("0"), Decimal("4166"), Decimal("0")),
        (Decimal("4167"), Decimal("6250"), Decimal("16.50")),
        (Decimal("6251"), Decimal("8333"), Decimal("25")),
        (Decimal("8334"), Decimal("12500"), Decimal("41.50")),
        (Decimal("12501"), Decimal("16666"), Decimal("62.50")),
        (Decimal("16667"), Decimal("20833"), Decimal("83.33")),
        (Decimal("20834"), None, Decimal("208")),
    ]),
    ("sikkim", [
        (Decimal("0"), Decimal("20000"), Decimal("0")),
        (Decimal("20001"), Decimal("30000"), Decimal("125")),
        (Decimal("30001"), Decimal("40000"), Decimal("150")),
        (Decimal("40001"), None, Decimal("200")),
    ]),
    ("bihar", [
        (Decimal("0"), Decimal("25000"), Decimal("0")),
        (Decimal("25001"), Decimal("41666"), Decimal("83.33")),
        (Decimal("41667"), Decimal("83333"), Decimal("166.67")),
        (Decimal("83334"), None, Decimal("208.33")),
    ]),
    ("jharkhand", [
        (Decimal("0"), Decimal("25000"), Decimal("0")),
        (Decimal("25001"), Decimal("41666"), Decimal("100")),
        (Decimal("41667"), Decimal("66666"), Decimal("150")),
        (Decimal("66667"), Decimal("83333"), Decimal("175")),
        (Decimal("83334"), None, Decimal("208")),
    ]),
    ("manipur", [
        (Decimal("0"), Decimal("4250"), Decimal("0")),
        (Decimal("4251"), Decimal("6250"), Decimal("100")),
        (Decimal("6251"), Decimal("8333"), Decimal("167")),
        (Decimal("8334"), Decimal("10416"), Decimal("208")),
        (Decimal("10417"), None, Decimal("250")),
    ]),
    ("nagaland", [
        (Decimal("0"), Decimal("4000"), Decimal("0")),
        (Decimal("4001"), Decimal("5000"), Decimal("35")),
        (Decimal("5001"), Decimal("7000"), Decimal("75")),
        (Decimal("7001"), Decimal("9000"), Decimal("110")),
        (Decimal("9001"), Decimal("12000"), Decimal("180")),
        (Decimal("12001"), None, Decimal("208")),
    ]),
    ("mizoram", [
        (Decimal("0"), Decimal("5000"), Decimal("0")),
        (Decimal("5001"), Decimal("8000"), Decimal("75")),
        (Decimal("8001"), Decimal("10000"), Decimal("120")),
        (Decimal("10001"), Decimal("12000"), Decimal("150")),
        (Decimal("12001"), None, Decimal("208")),
    ]),
    ("puducherry", [
        (Decimal("0"), Decimal("99999"), Decimal("0")),
        (Decimal("100000"), Decimal("200000"), Decimal("250")),
        (Decimal("200001"), Decimal("300000"), Decimal("500")),
        (Decimal("300001"), Decimal("400000"), Decimal("750")),
        (Decimal("400001"), Decimal("500000"), Decimal("1000")),
        (Decimal("500001"), None, Decimal("1250")),
    ]),
]


class Command(BaseCommand):
    help = "Seed Professional Tax slabs for states that levy PT (idempotent)."

    def handle(self, *args, **options):
        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            for state_name, slabs in PT_SLAB_DATA:
                state = State.objects.filter(name=state_name).first()
                if not state:
                    self.stdout.write(self.style.WARNING(
                        f"State '{state_name}' not found — run state/district seed first. Skipped."
                    ))
                    continue

                for salary_from, salary_to, monthly_tax in slabs:
                    _, created = PTSlab.objects.get_or_create(
                        state=state,
                        salary_from=salary_from,
                        salary_to=salary_to,
                        defaults={'monthly_tax': monthly_tax},
                    )
                    if created:
                        created_count += 1
                    else:
                        skipped_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"PT slabs seeded: {created_count} created, {skipped_count} already existed."
        ))
