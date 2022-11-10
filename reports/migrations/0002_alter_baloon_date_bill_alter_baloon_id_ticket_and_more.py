# Generated by Django 4.1.2 on 2022-11-10 11:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='baloon',
            name='date_bill',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='baloon',
            name='id_ticket',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='baloon',
            name='tariff',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='kontur',
            name='date_bill',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='kontur',
            name='date_of_ticket_passage',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='kontur',
            name='id_ticket',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='kontur',
            name='tariff',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='kontur',
            name='ticket_validity_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]