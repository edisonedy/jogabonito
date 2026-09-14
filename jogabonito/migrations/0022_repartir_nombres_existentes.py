# coding=utf-8
"""Parte los nombres que ya estaban en los campos separados.

Lo que estaba como "EDISON ROLANDO" / "MOYOLEMA MOYOLEMA" pasa a
nombre1=EDISON, nombre2=ROLANDO, apellido1=MOYOLEMA, apellido2=MOYOLEMA.
"""
from django.db import migrations


def repartir(apps, schema_editor):
    for nombre_modelo in ('Jugador', 'Entrenador', 'Representante'):
        Modelo = apps.get_model('jogabonito', nombre_modelo)

        for persona in Modelo.objects.all():
            partes = (persona.nombres or '').split()
            persona.nombre1 = partes[0] if partes else ''
            persona.nombre2 = ' '.join(partes[1:])

            partes = (persona.apellidos or '').split()
            persona.apellido1 = partes[0] if partes else ''
            persona.apellido2 = ' '.join(partes[1:])

            persona.save(update_fields=['nombre1', 'nombre2', 'apellido1', 'apellido2'])


def juntar(apps, schema_editor):
    """Al revertir, los campos separados simplemente se vacian."""
    for nombre_modelo in ('Jugador', 'Entrenador', 'Representante'):
        Modelo = apps.get_model('jogabonito', nombre_modelo)
        Modelo.objects.update(nombre1='', nombre2='', apellido1='', apellido2='')


class Migration(migrations.Migration):

    dependencies = [
        ('jogabonito', '0021_nombres_separados'),
    ]

    operations = [
        migrations.RunPython(repartir, juntar),
    ]
