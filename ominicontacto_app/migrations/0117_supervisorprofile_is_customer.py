# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2017-06-28 18:51
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ominicontacto_app', '0116_campana_nombre_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='supervisorprofile',
            name='is_customer',
            field=models.BooleanField(default=False),
        ),
    ]