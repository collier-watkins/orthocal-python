# Generated by Django 4.1.4 on 2023-01-23 22:23

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('calendarium', '0003_reading_pericope_link'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='reading',
            name='pericope',
        ),
    ]
