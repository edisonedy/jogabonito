# coding=utf-8
"""Abre los meses que le falten a cada jugador.

Sirve para dejarlo programado (una tarea diaria del servidor). En la pantalla
de mensualidades esto ya corre solo cada vez que se abre el modulo.

    python manage.py poner_al_dia
    python manage.py poner_al_dia --hasta 2026-12-31
"""
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from jogabonito.cobros import poner_al_dia, texto_resultado


class Command(BaseCommand):
    help = 'Genera las mensualidades que le falten a cada jugador activo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hasta', default='',
            help='Fecha limite (aaaa-mm-dd). Por defecto, hoy.'
        )

    def handle(self, *args, **opciones):
        hasta = None
        if opciones['hasta']:
            try:
                hasta = datetime.strptime(opciones['hasta'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('La fecha va asi: --hasta 2026-12-31')

        resultado = poner_al_dia(hasta=hasta)
        self.stdout.write(self.style.SUCCESS(texto_resultado(resultado)))
