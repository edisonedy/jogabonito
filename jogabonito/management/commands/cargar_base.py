# coding=utf-8
"""Carga la base del sistema: modulos, grupos y usuario administrador.

    py manage.py cargar_base
    py manage.py cargar_base --admin-clave "MiClave2026" --demo
"""
import io
from datetime import time

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction

from jogabonito.models import (
    ROL_ADMINISTRADOR, Categoria, GruposModulos, Indicador, Modulo, PerfilUsuario, Posicion,
)

MODULOS = [
    {'url': 'adm_asistencia', 'nombre': 'Asistencia', 'descripcion': 'Registro diario de asistencia por grupo.',
     'icono': 'fa-solid fa-clipboard-check', 'orden': 0},
    {'url': 'adm_jugador', 'nombre': 'Jugadores', 'descripcion': 'Fichas de los jugadores de la academia.',
     'icono': 'fa-solid fa-user-group', 'orden': 1},
    {'url': 'adm_categoria', 'nombre': 'Categorias', 'descripcion': 'Grupos de entrenamiento y horarios.',
     'icono': 'fa-solid fa-layer-group', 'orden': 2},
    {'url': 'adm_entrenador', 'nombre': 'Entrenadores', 'descripcion': 'Cuerpo tecnico y sus accesos.',
     'icono': 'fa-solid fa-clipboard-user', 'orden': 3},
    {'url': 'adm_representante', 'nombre': 'Representantes', 'descripcion': 'Padres y representantes.',
     'icono': 'fa-solid fa-address-book', 'orden': 4},
    {'url': 'adm_evaluacion', 'nombre': 'Evaluaciones', 'descripcion': 'Pruebas periodicas y progreso de cada jugador.',
     'icono': 'fa-solid fa-chart-line', 'orden': 5},
    {'url': 'adm_solicitud', 'nombre': 'Solicitudes', 'descripcion': 'Pedidos de cupo desde la pagina publica.',
     'icono': 'fa-solid fa-envelope-open-text', 'orden': 6},
    {'url': 'adm_indicador', 'nombre': 'Que medimos', 'descripcion': 'Indicadores de las pruebas y posiciones.',
     'icono': 'fa-solid fa-ruler-combined', 'orden': 7},
]

MODULOS_ADMINISTRADOR = ['adm_asistencia', 'adm_evaluacion', 'adm_jugador', 'adm_categoria',
                         'adm_entrenador', 'adm_representante', 'adm_solicitud', 'adm_indicador']
MODULOS_ENTRENADOR = ['adm_asistencia', 'adm_evaluacion', 'adm_jugador']

POSICIONES = [
    ('ARQUERO', 'ARQ', 1),
    ('DEFENSA CENTRAL', 'DFC', 2),
    ('LATERAL DERECHO', 'LD', 3),
    ('LATERAL IZQUIERDO', 'LI', 4),
    ('VOLANTE DE MARCA', 'MCD', 5),
    ('VOLANTE MIXTO', 'MC', 6),
    ('VOLANTE OFENSIVO', 'MCO', 7),
    ('EXTREMO DERECHO', 'ED', 8),
    ('EXTREMO IZQUIERDO', 'EI', 9),
    ('DELANTERO', 'DC', 10),
]

# Punto de partida sugerido: el administrador agrega, edita o desactiva lo que quiera.
# (nombre, area, tipo_medida, unidad, orden, descripcion)
INDICADORES = [
    ('CONTROL Y DOMINIO DEL BALON', 1, 1, '', 1, 'Del 1 al 10 segun el control en recepcion y conduccion.'),
    ('PASE CORTO', 1, 1, '', 2, 'Del 1 al 10 segun precision y peso del pase.'),
    ('PASE LARGO', 1, 1, '', 3, 'Del 1 al 10 segun precision en distancia.'),
    ('REMATE Y DEFINICION', 1, 1, '', 4, 'Del 1 al 10 segun potencia y colocacion.'),
    ('REGATE 1 CONTRA 1', 1, 1, '', 5, 'Del 1 al 10 segun encare y salida del duelo.'),
    ('DOMINADAS SEGUIDAS', 1, 2, 'reps', 6, 'Cuantas dominadas hace sin que caiga el balon.'),
    ('VELOCIDAD 30 METROS', 2, 3, 'seg', 1, 'Tiempo en recorrer 30 metros desde parado.'),
    ('RESISTENCIA 6 MINUTOS', 2, 2, 'm', 2, 'Metros recorridos en 6 minutos.'),
    ('SALTO VERTICAL', 2, 2, 'cm', 3, 'Altura del salto sin impulso.'),
    ('LECTURA DE JUEGO', 3, 1, '', 1, 'Del 1 al 10 segun la toma de decisiones con y sin balon.'),
    ('DESMARQUE Y POSICIONAMIENTO', 3, 1, '', 2, 'Del 1 al 10 segun como se ubica en la cancha.'),
    ('ACTITUD Y COMPROMISO', 4, 1, '', 1, 'Del 1 al 10 segun esfuerzo, puntualidad y respeto.'),
    ('TRABAJO EN EQUIPO', 4, 1, '', 2, 'Del 1 al 10 segun como juega para el companiero.'),
]

CATEGORIAS_DEMO = [
    {'nombre': 'MANANA', 'dias': '1,3,5', 'hora_inicio': time(7, 0), 'hora_fin': time(9, 0), 'valor_mensual': 25},
    {'nombre': 'TARDE', 'dias': '1,3,5', 'hora_inicio': time(15, 0), 'hora_fin': time(17, 0), 'valor_mensual': 25},
    {'nombre': 'NOCHE', 'dias': '2,4', 'hora_inicio': time(18, 0), 'hora_fin': time(20, 0), 'valor_mensual': 25},
]


class Command(BaseCommand):
    help = 'Crea los modulos, los grupos y el usuario administrador de la academia.'

    def add_arguments(self, parser):
        parser.add_argument('--admin-usuario', default='admin')
        parser.add_argument('--admin-clave', default='')
        parser.add_argument('--demo', action='store_true', help='Crea las categorias Manana/Tarde/Noche.')

    @transaction.atomic
    def handle(self, *args, **opciones):
        if opciones.get('verbosity', 1) == 0:
            self.stdout = io.StringIO()
        modulos = {}
        for datos in MODULOS:
            modulo, creado = Modulo.objects.update_or_create(url=datos['url'], defaults=datos)
            modulos[datos['url']] = modulo
            self.stdout.write('  %s modulo %s' % ('creado ' if creado else 'actualizado', modulo.url))

        for nombre_grupo, urls in (('ADMINISTRADOR', MODULOS_ADMINISTRADOR), ('ENTRENADOR', MODULOS_ENTRENADOR)):
            grupo, _ = Group.objects.get_or_create(name=nombre_grupo)
            asignacion, _ = GruposModulos.objects.get_or_create(grupo=grupo)
            asignacion.modulos.set([modulos[u] for u in urls])
            self.stdout.write('  grupo %s con %s modulos' % (nombre_grupo, len(urls)))

        username = opciones['admin_usuario']
        clave = opciones['admin_clave']
        usuario = User.objects.filter(username=username).first()

        if usuario is None:
            if not clave:
                clave = 'jogabonito2026'
                self.stdout.write(self.style.WARNING(
                    '  OJO: se uso la clave por defecto "%s". Cambiela ahora mismo.' % clave))
            usuario = User.objects.create_superuser(username=username, email='', password=clave)
            self.stdout.write('  usuario administrador creado: %s' % username)
        elif clave:
            usuario.set_password(clave)
            usuario.save()
            self.stdout.write('  clave del usuario %s actualizada' % username)

        usuario.groups.add(Group.objects.get(name='ADMINISTRADOR'))
        perfil = PerfilUsuario.objects.filter(usuario=usuario).first() or PerfilUsuario(usuario=usuario)
        perfil.rol = ROL_ADMINISTRADOR
        perfil.activo = True
        perfil.save()

        for nombre, abreviatura, orden in POSICIONES:
            Posicion.objects.get_or_create(
                nombre=nombre, defaults={'abreviatura': abreviatura, 'orden': orden}
            )
        self.stdout.write('  posiciones disponibles: %s' % Posicion.objects.count())

        for nombre, area, tipo, unidad, orden, descripcion in INDICADORES:
            Indicador.objects.get_or_create(
                nombre=nombre,
                defaults={'area': area, 'tipo_medida': tipo, 'unidad': unidad,
                          'orden': orden, 'descripcion': descripcion}
            )
        self.stdout.write('  indicadores disponibles: %s' % Indicador.objects.count())

        if opciones['demo']:
            for datos in CATEGORIAS_DEMO:
                categoria, creado = Categoria.objects.get_or_create(nombre=datos['nombre'], defaults=datos)
                if creado:
                    self.stdout.write('  categoria demo creada: %s' % categoria.nombre)

        self.stdout.write(self.style.SUCCESS('Base del sistema lista.'))
