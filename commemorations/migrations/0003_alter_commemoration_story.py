# Generated by Django 4.1.4 on 2023-01-15 21:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commemorations', '0002_alter_commemoration_unique_together'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commemoration',
            name='story',
            field=models.TextField(blank=True, null=True),
        ),
    ]