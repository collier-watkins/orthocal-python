# Generated by Django 4.1.4 on 2023-01-24 00:26

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('calendarium', '0006_alter_reading_pericope'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='reading',
            name='book',
        ),
    ]
