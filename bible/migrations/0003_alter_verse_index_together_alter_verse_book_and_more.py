# Generated by Django 4.1.4 on 2023-01-24 14:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bible', '0002_load_scriptures'),
    ]

    operations = [
        migrations.AlterIndexTogether(
            name='verse',
            index_together=set(),
        ),
        migrations.AlterField(
            model_name='verse',
            name='book',
            field=models.CharField(db_index=True, max_length=3),
        ),
        migrations.AlterField(
            model_name='verse',
            name='chapter',
            field=models.IntegerField(db_index=True),
        ),
        migrations.AlterField(
            model_name='verse',
            name='verse',
            field=models.IntegerField(db_index=True),
        ),
    ]
