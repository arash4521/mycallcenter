# Generated by Django 2.2.7 on 2020-02-14 19:19

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ominicontacto_app', '0039_queue_announce_position'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='agenteprofile',
            name='modulos',
        ),
        migrations.DeleteModel(
            name='Modulo',
        ),
    ]
