"""
Copies every employee_leave row into the matching (or newly created)
attendance row for the same employee/month/year, before employee_leave
is dropped in a later migration.

Field mapping (old -> new, both on attendance now):
    leaves_earned          -> split is not reversible field-for-field since
                               attendance already had casual/earned/sick/comp
                               as separate buckets while employee_leave had
                               one combined 'leaves_earned' number. We put
                               the combined total into earned_leaves and
                               leave the pre-existing casual/sick/comp
                               fields on attendance untouched (they were not
                               populated by employee_leave in the first
                               place — it was a separate, newer table).
    leave_availed           -> leave_lapsed  (closest semantic match: leave
                               used up counts toward reducing balance the
                               same way lapsed leave does in the new model)
    leave_balance            -> not copied — now always derived via
                               attendance.leave_balance() at read time
    leave_lapsed              -> leave_lapsed (added to leave_availed above
                               if both present)
    leave_encased               -> leave_encashed
    encashmanent_amount           -> leave_encashment_amount
    wages_paid                     -> leave_wages_paid
"""
from django.db import migrations


def migrate_leave_data(apps, schema_editor):
    employee_leave = apps.get_model('Aapp', 'employee_leave')
    attendance = apps.get_model('Aapp', 'attendance')

    for old in employee_leave.objects.all():
        att, _created = attendance.objects.get_or_create(
            employee_id_id=old.employee_id_id,
            salary_month=old.salary_month,
            salary_year=old.salary_year,
            defaults={
                'emp_code': old.emp_code,
                'companyid_id': old.companyid_id,
            },
        )
        att.earned_leaves = (att.earned_leaves or 0) + (old.leaves_earned or 0)
        att.leave_lapsed = (att.leave_lapsed or 0) + (old.leave_availed or 0) + (old.leave_lapsed or 0)
        att.leave_encashed = (att.leave_encashed or 0) + (old.leave_encased or 0)
        att.leave_encashment_amount = (att.leave_encashment_amount or 0) + (old.encashmanent_amount or 0)
        att.leave_wages_paid = (att.leave_wages_paid or 0) + (old.wages_paid or 0)
        att.save()


def reverse_noop(apps, schema_editor):
    # Not reversible — employee_leave rows are gone by the time this would
    # run in reverse (it's dropped in a later migration). No-op keeps the
    # migration reversible without error.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('Aapp', '0018_attendance_leave_fields'),
    ]

    operations = [
        migrations.RunPython(migrate_leave_data, reverse_noop),
    ]
