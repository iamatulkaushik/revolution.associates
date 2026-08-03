"""
Drops the three models fully superseded by this refactor, now that their
data has been copied elsewhere:
    employee_leave      -> data copied into attendance (see 0019)
    wages_record         -> superseded by salary_slip (Aapp.app.salary_processing);
                            no data migration needed since salary_slip was
                            already the authoritative payroll record —
                            wages_record was a parallel/orphaned duplicate
    overtime_register     -> superseded by MinimumWagesOvertimeRegister
                            (Aapp.app.attandance); same reasoning as above

wages_fine and wages_deduction keep their tables — only their FK target
changed (wages_record -> salary_slip), handled by AlterField below since
the FK column itself doesn't need renaming, just its target model.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('Aapp', '0019_migrate_employee_leave_to_attendance'),
    ]

    operations = [
        # Repoint wages_fine / wages_deduction FKs before dropping wages_record
        migrations.AlterField(
            model_name='wages_fine',
            name='wages_record',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='fines', to='Aapp.salary_slip',
            ),
        ),
        migrations.RenameField(
            model_name='wages_fine',
            old_name='wages_record',
            new_name='salary_slip',
        ),
        migrations.AlterField(
            model_name='wages_deduction',
            name='wages_record',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='extra_deductions', to='Aapp.salary_slip',
            ),
        ),
        migrations.RenameField(
            model_name='wages_deduction',
            old_name='wages_record',
            new_name='salary_slip',
        ),

        migrations.DeleteModel(name='employee_leave'),
        migrations.DeleteModel(name='wages_record'),
        migrations.DeleteModel(name='overtime_register'),
    ]
