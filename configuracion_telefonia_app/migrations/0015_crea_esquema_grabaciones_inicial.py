# Generated by Django 2.2.7 on 2021-01-27 21:10

from django.db import migrations

def adicionar_configuracion_inicial_esquema_grabaciones(apps, schema_editor):
    """
    Adiciona la instancia que guarda la configuración del Esquema de grabaciones del sistema
    """
    EsquemaGrabaciones = apps.get_model("configuracion_telefonia_app", "EsquemaGrabaciones")

    EsquemaGrabaciones.objects.get_or_create(pk=1)

class Migration(migrations.Migration):

    dependencies = [
        ('configuracion_telefonia_app', '0014_esquemagrabaciones'),
    ]

    operations = [
        migrations.RunPython(adicionar_configuracion_inicial_esquema_grabaciones, reverse_code=migrations.RunPython.noop),
    ]
