# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2018-03-26 18:55
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ominicontacto_app', '0167_elimina_campos_sobrantes_calmanual'),
    ]

    operations = [
        migrations.AddField(
            model_name='calificacioncliente',
            name='es_calificacion_manual',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='calificacioncliente',
            name='fecha',
            field=models.DateTimeField(),
        ),
    ]