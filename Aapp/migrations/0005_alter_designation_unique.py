from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Aapp', '0004_employee_driving_license_expiry_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='designation',
            name='designationname',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterUniqueTogether(
            name='designation',
            unique_together={('designationname', 'company')},
        ),
    ]
