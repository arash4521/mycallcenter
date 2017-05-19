# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2017-05-19 14:17
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ominicontacto_app', '0087_auto_20170518_1252'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReglasIncidencia',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado', models.PositiveIntegerField(choices=[(1, 'Ocupado'), (2, 'Contestador'), (3, 'No atendido'), (4, 'Rechazado'), (5, 'Timeout')])),
                ('estado_personalizado', models.CharField(blank=True, max_length=128, null=True)),
                ('intento_max', models.IntegerField()),
                ('reintentar_tarde', models.IntegerField()),
                ('en_modo', models.PositiveIntegerField(choices=[(1, 'FIXED'), (2, 'MULT')], default=2)),
                ('campana', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reglas_incidencia', to='ominicontacto_app.CampanaDialer')),
            ],
        ),
    ]
