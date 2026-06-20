from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('Aapp', '0010_attendance'),
        ('Sapp', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='employee_leave',
            fields=[
                ('leaveid',       models.AutoField(primary_key=True, serialize=False)),
                ('emp_code',      models.CharField(max_length=20)),
                ('salary_month',  models.PositiveSmallIntegerField(choices=[(1,'January'),(2,'February'),(3,'March'),(4,'April'),(5,'May'),(6,'June'),(7,'July'),(8,'August'),(9,'September'),(10,'October'),(11,'November'),(12,'December')])),
                ('salary_year',   models.PositiveSmallIntegerField()),
                ('leaves_earned', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('leave_availed', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('leave_balance', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('wages_paid',    models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('created_date',  models.DateTimeField(auto_now_add=True)),
                ('updated_date',  models.DateTimeField(auto_now=True)),
                ('companyid',     models.ForeignKey(db_column='companyid', on_delete=django.db.models.deletion.CASCADE, to='Sapp.company')),
                ('created_by',    models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='leave_created', to='auth.user')),
                ('employee_id',   models.ForeignKey(db_column='employee_id', on_delete=django.db.models.deletion.CASCADE, related_name='leaves', to='Aapp.employee')),
                ('updated_by',    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='leave_updated', to='auth.user')),
            ],
            options={
                'db_table': 'employee_leave',
                'ordering': ['-salary_year', '-salary_month'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='employee_leave',
            unique_together={('employee_id', 'salary_month', 'salary_year')},
        ),
    ]
