from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('Aapp', '0009_rename_intership_start_date_employee_internship_start_date'),
        ('Sapp', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='attendance',
            fields=[
                ('attendanceid',   models.AutoField(primary_key=True, serialize=False)),
                ('is_bulk',        models.BooleanField(default=False)),
                ('emp_code',       models.CharField(max_length=20)),
                ('divisionid',     models.CharField(blank=True, default='', max_length=100)),
                ('salary_month',   models.PositiveSmallIntegerField(choices=[(1,'January'),(2,'February'),(3,'March'),(4,'April'),(5,'May'),(6,'June'),(7,'July'),(8,'August'),(9,'September'),(10,'October'),(11,'November'),(12,'December')])),
                ('salary_year',    models.PositiveSmallIntegerField()),
                ('working_days',   models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('holidays',       models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('casual_leaves',  models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('earned_leaves',  models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('sick_leaves',    models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('comp_leaves',    models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('work_pay',       models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('created_date',   models.DateTimeField(auto_now_add=True)),
                ('updated_date',   models.DateTimeField(auto_now=True)),
                ('branchid',       models.ForeignKey(blank=True, db_column='branchid', null=True, on_delete=django.db.models.deletion.SET_NULL, to='Aapp.branch')),
                ('companyid',      models.ForeignKey(db_column='companyid', on_delete=django.db.models.deletion.CASCADE, to='Sapp.company')),
                ('created_by',     models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_created', to='auth.user')),
                ('employee_id',    models.ForeignKey(db_column='employee_id', on_delete=django.db.models.deletion.CASCADE, related_name='attendances', to='Aapp.employee')),
                ('updated_by',     models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_updated', to='auth.user')),
            ],
            options={
                'db_table': 'attendance',
                'ordering': ['-salary_year', '-salary_month'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='attendance',
            unique_together={('employee_id', 'salary_month', 'salary_year')},
        ),
    ]
