# Generated by Django 4.1.2 on 2022-11-24 07:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0016_viewpay'),
    ]

    operations = [
        migrations.CreateModel(
            name='DecodingOfDeskSectionsAndTaxGroups',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tax_group', models.CharField(blank=True, max_length=250, null=True)),
                ('desk_sections', models.CharField(blank=True, max_length=250, null=True)),
                ('taxation_system', models.CharField(blank=True, max_length=250, null=True)),
                ('count_operation', models.CharField(blank=True, max_length=250, null=True)),
                ('summ', models.CharField(blank=True, max_length=250, null=True)),
            ],
        ),
        migrations.AlterModelOptions(
            name='baloon',
            options={},
        ),
        migrations.AlterModelOptions(
            name='deskitems',
            options={},
        ),
        migrations.AlterModelOptions(
            name='kontur',
            options={},
        ),
        migrations.AlterModelOptions(
            name='passagesturnstile',
            options={},
        ),
        migrations.AlterModelOptions(
            name='rulelist',
            options={},
        ),
        migrations.AlterModelOptions(
            name='servicelist',
            options={},
        ),
    ]
