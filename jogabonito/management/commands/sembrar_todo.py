# coding=utf-8
"""Deja la base lista, igual que la del computador, con un solo comando.

Es lo que se corre en el servidor recien instalado para poder probar todo
lo que se hizo: los modulos y permisos, los catalogos, Kevyn como entrenador,
los tres alumnos reales, sus pruebas, sus medidas, sus notas, sus asistencias
de todos estos meses y sus mensualidades (pagadas menos la del mes en curso).

    python manage.py sembrar_todo --admin-clave "la-clave-que-quieras"

Se puede correr las veces que haga falta: no duplica nada, porque cada parte
busca antes de crear. Lo unico que NO vuelve a tocar es lo que ya se edito a
mano (una ficha de salud escrita, un historial de asistencias ya cargado).

    --limpiar   ademas borra los jugadores de prueba que no sean los reales.
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand

from jogabonito.models import (
    Asistencia, Categoria, Entrenador, Evaluacion, Indicador, Jugador, Medicion,
    Mensualidad, Nota, Posicion,
)


class Command(BaseCommand):
    help = 'Deja la base lista para usar: catalogos, academia y datos de arranque.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-clave', default='',
            help='Clave del usuario admin. Si se omite y el usuario ya existe, no se cambia.'
        )
        parser.add_argument(
            '--admin-usuario', default='admin',
            help='Nombre del usuario administrador (por defecto: admin).'
        )
        parser.add_argument(
            '--clave-kevyn', default='',
            help='Clave del usuario ksupe (Kevyn, el duenio). Vacio = no se le toca.'
        )
        parser.add_argument(
            '--limpiar', action='store_true',
            help='Ademas borra los jugadores de prueba que no sean los reales.'
        )

    def handle(self, *args, **opciones):
        self.titulo('1 de 2: modulos, permisos y catalogos')
        call_command(
            'cargar_base',
            admin_usuario=opciones['admin_usuario'],
            admin_clave=opciones['admin_clave'],
        )

        self.titulo('2 de 2: la academia y sus datos')
        call_command(
            'cargar_academia',
            limpiar=opciones['limpiar'],
            clave_kevyn=opciones['clave_kevyn'],
        )

        self.resumen()

    # ------------------------------------------------------------------
    def titulo(self, texto):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(texto))

    def resumen(self):
        """Las cuentas, para poder compararlas con las del computador."""
        filas = [
            ('Posiciones', Posicion.objects.count(), 'puestos en la cancha'),
            ('Indicadores', Indicador.objects.count(), 'cosas que se pueden medir'),
            ('Grupos', Categoria.objects.count(), 'categorias'),
            ('Entrenadores', Entrenador.objects.count(), ''),
            ('Jugadores', Jugador.objects.count(), ''),
            ('Pruebas', Evaluacion.objects.count(), ''),
            ('Mediciones', Medicion.objects.count(), ''),
            ('Asistencias', Asistencia.objects.count(), 'clases marcadas'),
            ('Mensualidades', Mensualidad.objects.count(), ''),
            ('Notas del profe', Nota.objects.count(), ''),
        ]

        self.titulo('Asi quedo la base')
        for nombre, cuantos, detalle in filas:
            self.stdout.write('  %-22s %5s  %s' % (nombre, cuantos, detalle))

        debe = sum((j.total_que_debe() for j in Jugador.objects.all()), 0)
        self.stdout.write('')
        self.stdout.write('  Deuda total de la academia: $ %s' % debe)
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            'Listo. Entra al sistema y revisa Tablero, Mensualidades y Asistencia.'))
