from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Aapp', '0017_alter_employee_leave_salary_year'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendance',
            name='leave_lapsed',
            field=models.DecimalField(max_digits=5, decimal_places=2, default=0),
        ),
        migrations.AddField(
            model_name='attendance',
            name='leave_encashed',
            field=models.DecimalField(max_digits=5, decimal_places=2, default=0),
        ),
        migrations.AddField(
            model_name='attendance',
            name='leave_encashment_amount',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0),
        ),
        migrations.AddField(
            model_name='attendance',
            name='leave_wages_paid',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0),
        ),
    ]
