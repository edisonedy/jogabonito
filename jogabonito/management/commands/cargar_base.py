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
    ROL_ADMINISTRADOR, Categoria, Division, GruposModulos, Indicador, Modulo, PerfilUsuario,
    Posicion,
    TipoEvaluacion,
)

MODULOS = [
    {'url': 'dashboard', 'nombre': 'Tablero', 'descripcion': 'Como va la academia hoy: asistencia, alertas y pruebas.',
     'icono': 'fa-solid fa-gauge-high', 'orden': -1},
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
    {'url': 'adm_mensualidad', 'nombre': 'Mensualidades', 'descripcion': 'Cobros del mes, descuentos y quien debe.',
     'icono': 'fa-solid fa-money-bill-wave', 'orden': 4},
    {'url': 'adm_turno', 'nombre': 'Turnos', 'descripcion': 'Que profe dirige cada grupo esta semana.',
     'icono': 'fa-solid fa-calendar-week', 'orden': 5},
    {'url': 'adm_evaluacion', 'nombre': 'Evaluaciones', 'descripcion': 'Pruebas periodicas y progreso de cada jugador.',
     'icono': 'fa-solid fa-chart-line', 'orden': 5},
    {'url': 'adm_solicitud', 'nombre': 'Solicitudes', 'descripcion': 'Pedidos de cupo desde la pagina publica.',
     'icono': 'fa-solid fa-envelope-open-text', 'orden': 6},
    {'url': 'adm_indicador', 'nombre': 'Que medimos', 'descripcion': 'Indicadores de las pruebas y posiciones.',
     'icono': 'fa-solid fa-ruler-combined', 'orden': 7},
]

MODULOS_ADMINISTRADOR = ['dashboard', 'adm_asistencia', 'adm_evaluacion', 'adm_jugador', 'adm_categoria',
                         'adm_entrenador', 'adm_representante', 'adm_mensualidad', 'adm_solicitud',
                         'adm_indicador', 'adm_turno']
# El entrenador trabaja con dos cosas: tomar lista y medir. Las notas y las
# medidas de sus jugadores viven dentro de adm_evaluacion, por eso no necesita
# el modulo de jugadores.
MODULOS_ENTRENADOR = ['adm_asistencia', 'adm_evaluacion']

# (nombre, abreviatura, orden, peso tecnica, fisica, tactica, actitud)
# Los pesos dicen que pide cada puesto; el administrador los puede cambiar.
# Divisiones por edad: el grupo dice cuando entrena, esto dice contra quien
# juega. (nombre, edad minima, edad maxima, orden). Se pueden cambiar desde
# la pantalla de Categorias.
DIVISIONES = [
    ('SUB-6', 3, 6, 1),
    ('SUB-8', 7, 8, 2),
    ('SUB-10', 9, 10, 3),
    ('SUB-12', 11, 12, 4),
    ('SUB-14', 13, 14, 5),
    ('SUB-16', 15, 16, 6),
    ('SUB-18', 17, 18, 7),
    ('ADULTOS', 19, 99, 8),
]

# Todos los puestos de una cancha de 11, con la sigla con que se los nombra.
# (nombre, sigla, orden, peso tecnica, peso fisica, peso tactica, peso actitud)
# Los pesos van de 0 a 3 y dicen cuanto cuenta cada area para jugar ahi.
POSICIONES = [
    # ---- arco ----
    ('ARQUERO', 'POR', 1, 2, 3, 2, 3),
    # ---- defensa ----
    ('LIBERO', 'LIB', 2, 2, 2, 3, 2),
    ('DEFENSA CENTRAL', 'DFC', 3, 1, 3, 3, 2),
    ('LATERAL DERECHO', 'LD', 4, 2, 3, 2, 2),
    ('LATERAL IZQUIERDO', 'LI', 5, 2, 3, 2, 2),
    ('CARRILERO DERECHO', 'CAD', 6, 2, 3, 2, 2),
    ('CARRILERO IZQUIERDO', 'CAI', 7, 2, 3, 2, 2),
    # ---- medio ----
    ('VOLANTE DE MARCA', 'MCD', 8, 2, 3, 3, 2),
    ('VOLANTE MIXTO', 'MC', 9, 3, 2, 3, 2),
    ('INTERIOR DERECHO', 'MD', 10, 3, 2, 2, 2),
    ('INTERIOR IZQUIERDO', 'MI', 11, 3, 2, 2, 2),
    ('VOLANTE OFENSIVO', 'MCO', 12, 3, 1, 3, 1),
    ('MEDIAPUNTA', 'MP', 13, 3, 1, 3, 1),
    # ---- ataque ----
    ('EXTREMO DERECHO', 'ED', 14, 3, 3, 1, 1),
    ('EXTREMO IZQUIERDO', 'EI', 15, 3, 3, 1, 1),
    ('SEGUNDO DELANTERO', 'SD', 16, 3, 2, 2, 1),
    ('DELANTERO', 'DC', 17, 3, 2, 2, 1),
]

# Punto de partida sugerido: el administrador agrega, edita o desactiva lo que quiera.
# (nombre, area, tipo_medida, unidad, orden, descripcion)
INDICADORES = [
    # ---------------------------- TECNICA (area 1) ----------------------------
    # Casi todo del 1 al 10 porque lo califica el ojo del profe.
    ('CONTROL Y DOMINIO DEL BALON', 1, 1, '', 1,
     'Del 1 al 10 segun el control en recepcion y conduccion.'),
    ('PASE CORTO', 1, 1, '', 2, 'Del 1 al 10 segun precision y peso del pase.'),
    ('PASE LARGO', 1, 1, '', 3, 'Del 1 al 10 segun precision en distancia.'),
    ('REMATE Y DEFINICION', 1, 1, '', 4, 'Del 1 al 10 segun potencia y colocacion.'),
    ('REGATE 1 CONTRA 1', 1, 1, '', 5, 'Del 1 al 10 segun encare y salida del duelo.'),
    ('JUEGO DE CABEZA', 1, 1, '', 6, 'Del 1 al 10 segun salto, timing y direccion.'),
    ('DOMINADAS SEGUIDAS', 1, 2, 'reps', 7,
     'Cuantas dominadas hace sin que caiga el balon.'),
    ('CONDUCCION EN SLALOM', 1, 3, 'seg', 8,
     'Tiempo en recorrer 6 conos separados 2 metros, ida y vuelta, con balon.'),
    ('PRECISION DE PASE (10 INTENTOS)', 1, 2, 'aciertos', 9,
     'De 10 pases a 15 metros, cuantos llegan al companiero o al arco chico.'),

    # ---------------------------- FISICO (area 2) -----------------------------
    # Lo que se mide con cronometro y cinta: es el bloque mas objetivo.
    ('VELOCIDAD 10 METROS', 2, 3, 'seg', 1,
     'Arranque desde parado. Mide la explosion en los primeros pasos.'),
    ('VELOCIDAD 30 METROS', 2, 3, 'seg', 2,
     'Tiempo en recorrer 30 metros desde parado. La velocidad punta.'),
    ('AGILIDAD 5-10-5', 2, 3, 'seg', 3,
     'Cambio de direccion: 5 m a un lado, 10 al otro y 5 de vuelta.'),
    ('TEST DE ILLINOIS', 2, 3, 'seg', 4,
     'Circuito de agilidad con conos (10 x 5 m). Clasico de cantera.'),
    ('SALTO VERTICAL', 2, 2, 'cm', 5,
     'Altura del salto con las manos en la cintura (CMJ). Fuerza de piernas.'),
    ('SALTO HORIZONTAL', 2, 2, 'cm', 6,
     'Salto largo sin impulso, con los dos pies.'),
    ('RESISTENCIA 6 MINUTOS', 2, 2, 'm', 7,
     'Metros recorridos en 6 minutos de carrera continua.'),
    ('COURSE NAVETTE (NIVEL)', 2, 2, 'nivel', 8,
     'Test de ida y vuelta de 20 m con audio. El nivel al que abandona.'),
    ('FLEXIBILIDAD (SIT AND REACH)', 2, 2, 'cm', 9,
     'Sentado, cuanto alcanza con las manos pasando la punta de los pies.'),
    ('ABDOMINALES EN 30 SEGUNDOS', 2, 2, 'reps', 10,
     'Cuantas repeticiones completas hace en medio minuto.'),
    ('PLANCHA ISOMETRICA', 2, 2, 'seg', 11,
     'Segundos que aguanta la plancha con la tecnica correcta.'),
    ('FUERZA: PESO QUE LEVANTA', 2, 2, 'kg', 12,
     'Kilos que levanta en el ejercicio de fuerza acordado (solo mayores).'),

    # ---------------------------- TACTICA (area 3) ----------------------------
    ('LECTURA DE JUEGO', 3, 1, '', 1,
     'Del 1 al 10 segun la toma de decisiones con y sin balon.'),
    ('DESMARQUE Y POSICIONAMIENTO', 3, 1, '', 2,
     'Del 1 al 10 segun como se ubica en la cancha.'),
    ('PRESION Y RECUPERACION', 3, 1, '', 3,
     'Del 1 al 10 segun como presiona y roba cuando pierde el balon.'),
    ('JUEGO SIN BALON', 3, 1, '', 4,
     'Del 1 al 10 segun coberturas, apoyos y movilidad.'),

    # ---------------------------- ACTITUD (area 4) ----------------------------
    ('ACTITUD Y COMPROMISO', 4, 1, '', 1,
     'Del 1 al 10 segun esfuerzo, puntualidad y respeto.'),
    ('TRABAJO EN EQUIPO', 4, 1, '', 2,
     'Del 1 al 10 segun como juega para el companiero.'),
    ('DISCIPLINA EN EL ENTRENAMIENTO', 4, 1, '', 3,
     'Del 1 al 10 segun atencion, orden y cumplimiento de las consignas.'),
    ('REACCION AL ERROR', 4, 1, '', 4,
     'Del 1 al 10: como sigue despues de fallar o de recibir un gol.'),

    # ---------------------------- PORTERO (area 5) ----------------------------
    # Solo para arqueros. No entran en la afinidad de los jugadores de campo.
    ('BLOCAJE Y SEGURIDAD', 5, 1, '', 1, 'Del 1 al 10 segun como atrapa y asegura el balon.'),
    ('ACHIQUE Y 1 CONTRA 1', 5, 1, '', 2, 'Del 1 al 10 segun como sale al delantero.'),
    ('JUEGO CON LOS PIES', 5, 1, '', 3, 'Del 1 al 10 segun su salida jugando.'),
    ('SAQUE LARGO', 5, 2, 'm', 4, 'Metros que alcanza con el saque de arco.'),
    ('ATAJADAS DE 10 REMATES', 5, 4, '', 5,
     'De 10 remates a puerta, que porcentaje ataja.'),

    # ---------------------------- MENTAL (area 6) -----------------------------
    ('CONCENTRACION EN EL PARTIDO', 6, 1, '', 1,
     'Del 1 al 10: se mantiene atento los 90 minutos o se desconecta.'),
    ('DECISION BAJO PRESION', 6, 1, '', 2,
     'Del 1 al 10: que tan bien resuelve cuando lo aprietan.'),
    ('TIEMPO DE REACCION', 6, 3, 'seg', 3,
     'Segundos en responder al estimulo (luz, silbato o senia del profe).'),
    ('LIDERAZGO EN LA CANCHA', 6, 1, '', 4,
     'Del 1 al 10: habla, ordena y levanta al companiero.'),
]

# El peso y la estatura NO son indicadores: van en ControlFisico, en la ficha
# del jugador. No son una marca que se mejora, es un ninio creciendo.

# Tipos de prueba de arranque. El administrador agrega los que quiera.
TIPOS_EVALUACION = [
    ('DIAGNOSTICA INICIAL', 'Con que llego el jugador a la academia. Es su punto de partida.',
     'primary', True, 1),
    ('SEGUIMIENTO SEMANAL', 'Control corto para ver como va la semana.', 'success', False, 2),
    ('EVALUACION MENSUAL', 'Medicion completa de fin de mes.', 'warning', False, 3),
    ('PRUEBA FINAL', 'Cierre del ciclo o del periodo.', 'danger', False, 4),
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

        for nombre, abreviatura, orden, tecnica, fisica, tactica, actitud in POSICIONES:
            Posicion.objects.update_or_create(
                nombre=nombre,
                defaults={'abreviatura': abreviatura, 'orden': orden,
                          'peso_tecnica': tecnica, 'peso_fisica': fisica,
                          'peso_tactica': tactica, 'peso_actitud': actitud}
            )
        self.stdout.write('  posiciones disponibles: %s' % Posicion.objects.count())

        for nombre, minima, maxima, orden in DIVISIONES:
            Division.objects.get_or_create(
                nombre=nombre,
                defaults={'edad_minima': minima, 'edad_maxima': maxima, 'orden': orden}
            )
        self.stdout.write('  divisiones por edad: %s' % Division.objects.count())

        for nombre, area, tipo, unidad, orden, descripcion in INDICADORES:
            Indicador.objects.get_or_create(
                nombre=nombre,
                defaults={'area': area, 'tipo_medida': tipo, 'unidad': unidad,
                          'orden': orden, 'descripcion': descripcion}
            )
        self.stdout.write('  indicadores disponibles: %s' % Indicador.objects.count())

        for nombre, descripcion, color, inicial, orden in TIPOS_EVALUACION:
            TipoEvaluacion.objects.get_or_create(
                nombre=nombre,
                defaults={'descripcion': descripcion, 'color': color,
                          'es_inicial': inicial, 'orden': orden}
            )
        self.stdout.write('  tipos de evaluacion: %s' % TipoEvaluacion.objects.count())

        if opciones['demo']:
            for datos in CATEGORIAS_DEMO:
                categoria, creado = Categoria.objects.get_or_create(nombre=datos['nombre'], defaults=datos)
                if creado:
                    self.stdout.write('  categoria demo creada: %s' % categoria.nombre)

        self.stdout.write(self.style.SUCCESS('Base del sistema lista.'))
