# Generated by Django 3.1.2 on 2022-11-30 11:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pyvcloud_project', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuthDetail',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=100, null=True)),
                ('host', models.CharField(blank=True, max_length=100, null=True)),
                ('username', models.CharField(blank=True, max_length=45, null=True)),
                ('password', models.CharField(blank=True, max_length=45, null=True)),
                ('org', models.CharField(blank=True, max_length=45, null=True)),
                ('api_version', models.CharField(blank=True, max_length=45, null=True)),
            ],
            options={
                'verbose_name_plural': 'AuthDetails',
            },
        ),
    ]
