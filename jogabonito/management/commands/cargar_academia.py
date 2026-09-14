# coding=utf-8
"""Deja la academia con sus datos reales de arranque.

Kevyn Supe es el duenio Y entrena, asi que tambien tiene ficha de entrenador.
Los alumnos con los que arranca el sistema son tres, en el grupo de la noche.

    python manage.py cargar_academia            # crea/actualiza lo real
    python manage.py cargar_academia --limpiar  # ademas borra los de prueba

Con --limpiar se van los jugadores que NO son estos tres (y todo lo que cuelga
de ellos: asistencias, mediciones, mensualidades, notas). Es para dejar la base
lista para mostrarla, no para usarla con datos de verdad ya cargados.
"""
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from jogabonito.cobros import poner_al_dia_jugador
from jogabonito.models import (
    JUGADOR_ACTIVO, MENSUALIDAD_PAGADO, NOTA_ATENCION, NOTA_FELICITACION, NOTA_GENERAL,
    PAGO_EFECTIVO, Categoria, ControlFisico, Entrenador, Evaluacion, Indicador, Jugador,
    Medicion, Nota, Posicion, Representante, TipoEvaluacion,
)

HOY = date.today()

# El grupo con el que arranca: la noche.
GRUPO = {
    'nombre': 'NOCHE',
    'descripcion': 'Grupo de adultos, en la noche.',
    'dias': '2,4',
    'hora_inicio': time(18, 0),
    'hora_fin': time(20, 0),
    'valor_mensual': Decimal('25.00'),
    'edad_minima': 18,
    'edad_maxima': 60,
}

# Los de la noche son ADULTOS, no una categoria formativa (hay ninios y
# jovenes en los otros horarios). La fecha de Edison es la real; las otras dos
# son de relleno para que salgan como adultos: corregirlas en su ficha.
# (nombre1, nombre2, apellido1, apellido2, cedula, telefono, direccion,
#  nacimiento, ingreso, posicion, pie)
ALUMNOS = [
    ('EDISON', 'ROLANDO', 'MOYOLEMA', 'MOYOLEMA', '1804290490', '0999955936',
     'Picaihua, Tangaiche', date(1989, 3, 13), date(2026, 9, 2), 'VOLANTE MIXTO', 1),
    ('CHRISTIAN', '', 'MOYOLEMA', '', '', '', '',
     date(1998, 8, 9), HOY - timedelta(days=70), 'DELANTERO', 1),
    ('LUIS', '', 'SAILEMA', '', '', '', '',
     date(1993, 2, 25), HOY - timedelta(days=40), 'DEFENSA CENTRAL', 2),
]

# Que se le midio a cada uno en cada prueba: (indicador, valor de cada alumno).
# Hay huecos a proposito: no a todos se les toma todo el mismo dia.
PRUEBAS = [
    # (dias atras, titulo, tipo, [(indicador, [valor edison, christian, luis])])
    (60, 'PRUEBA DE INGRESO', 'DIAGNOSTICA INICIAL', [
        ('CONTROL Y DOMINIO DEL BALON', ['6', '5', '7']),
        ('PASE CORTO', ['6', '6', '7']),
        ('VELOCIDAD 30 METROS', ['5.90', '6.20', '5.60']),
        ('LECTURA DE JUEGO', ['5', '6', '7']),
        ('ACTITUD Y COMPROMISO', ['8', '9', '7']),
    ]),
    (30, 'CONTROL DEL MES', 'EVALUACION MENSUAL', [
        ('CONTROL Y DOMINIO DEL BALON', ['7', '6', '7']),
        ('PASE CORTO', ['7', '7', None]),          # Luis falto ese dia
        ('VELOCIDAD 30 METROS', ['5.75', '6.05', '5.62']),
        ('LECTURA DE JUEGO', ['6', '7', '7']),
        ('ACTITUD Y COMPROMISO', ['9', '9', '6']),
    ]),
    (5, 'SEGUIMIENTO DE LA SEMANA', 'SEGUIMIENTO SEMANAL', [
        ('CONTROL Y DOMINIO DEL BALON', ['8', '7', '7']),
        ('VELOCIDAD 30 METROS', ['5.60', '5.95', '5.70']),
        ('ACTITUD Y COMPROMISO', ['9', '10', '6']),
    ]),
]

# (alumno, dias atras, peso, estatura)
MEDIDAS = [
    (0, 60, '38.50', 148), (0, 5, '39.20', 150),
    (1, 60, '31.00', 132), (1, 5, '31.80', 134),
    (2, 60, '45.00', 158), (2, 5, '45.40', 159),
]

# (alumno, dias atras, tipo, texto)
NOTAS = [
    (0, 45, NOTA_FELICITACION, 'Se le nota mas seguro con el balon y ayuda a los mas pequenios.'),
    (1, 20, NOTA_GENERAL, 'Le esta costando el pase largo; hay que trabajarlo en la semana.'),
    (2, 8, NOTA_ATENCION, 'Vino desanimado las ultimas dos clases. Conversar con la familia.'),
]


class Command(BaseCommand):
    help = 'Carga los datos reales de arranque: Kevyn como entrenador y los tres alumnos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpiar', action='store_true',
            help='Borra los jugadores de prueba que no sean estos tres.'
        )

    @transaction.atomic
    def handle(self, *args, **opciones):
        kevyn = self.crear_entrenador()
        grupo = self.crear_grupo(kevyn)
        alumnos = self.crear_alumnos(grupo)

        if opciones['limpiar']:
            self.limpiar(alumnos)

        self.crear_pruebas(grupo, alumnos)
        self.crear_medidas(alumnos)
        self.crear_notas(alumnos, kevyn)
        self.crear_mensualidades(alumnos)

        self.stdout.write(self.style.SUCCESS(
            'Academia lista: %s con %s alumnos.' % (grupo.nombre, len(alumnos))))

    # ------------------------------------------------------------------
    def crear_entrenador(self):
        """Kevyn es el duenio y ademas dirige, asi que tiene las dos cosas."""
        kevyn, creado = Entrenador.objects.get_or_create(
            nombres='KEVYN', apellidos='SUPE',
            defaults={'telefono': '0980137922', 'email': 'ksupe07@gmail.com'}
        )
        self.stdout.write('  entrenador %s %s' % (kevyn.nombre_completo(),
                                                  '(creado)' if creado else '(ya estaba)'))
        return kevyn

    def crear_grupo(self, kevyn):
        grupo, creado = Categoria.objects.get_or_create(
            nombre=GRUPO['nombre'], defaults=GRUPO)

        grupo.entrenadores.add(kevyn)
        if grupo.encargado_id is None:
            grupo.encargado = kevyn
            grupo.save()

        self.stdout.write('  grupo %s %s' % (grupo.nombre, '(creado)' if creado else '(ya estaba)'))
        return grupo

    def crear_alumnos(self, grupo):
        alumnos = []
        for datos in ALUMNOS:
            (nombre1, nombre2, apellido1, apellido2, cedula, telefono,
             direccion, nacimiento, ingreso, posicion, pie) = datos

            jugador, creado = Jugador.objects.get_or_create(
                nombre1=nombre1, apellido1=apellido1,
                defaults={
                    'nombre2': nombre2,
                    'apellido2': apellido2,
                    'cedula': cedula,
                    'telefono': telefono,
                    'direccion': direccion,
                    'fecha_nacimiento': nacimiento,
                    'fecha_ingreso': ingreso,
                    'categoria': grupo,
                    'estado': JUGADOR_ACTIVO,
                    'pie_habil': pie,
                    'posicion': Posicion.objects.filter(nombre=posicion).first(),
                }
            )
            if not creado:
                jugador.categoria = grupo
                jugador.estado = JUGADOR_ACTIVO
                jugador.save()

            alumnos.append(jugador)
            self.stdout.write('  alumno %s %s' % (jugador.nombre_completo(),
                                                  '(creado)' if creado else '(ya estaba)'))

        self.crear_representante(alumnos)
        return alumnos

    def crear_representante(self, alumnos):
        """Los dos Moyolema comparten representante; es lo normal en hermanos."""
        papa, _ = Representante.objects.get_or_create(
            nombres='EDISON', apellidos='MOYOLEMA LEMA',
            defaults={'telefono': '0980137922', 'whatsapp': '0980137922',
                      'parentesco': 1}
        )
        for jugador in alumnos[:2]:
            if jugador.representante_id is None:
                jugador.representante = papa
                jugador.save()

    def limpiar(self, alumnos):
        """Se van los de prueba: no queremos mostrar datos inventados."""
        sobrantes = Jugador.objects.exclude(pk__in=[j.pk for j in alumnos])
        cuantos = sobrantes.count()

        for jugador in sobrantes:
            jugador.mensualidades.all().delete()
            jugador.asistencias.all().delete()
            jugador.mediciones.all().delete()
            jugador.notas.all().delete()
            jugador.controles.all().delete()
            jugador.evaluaciones_propias.all().delete()
            jugador.delete()

        if cuantos:
            self.stdout.write(self.style.WARNING('  se borraron %s jugadores de prueba' % cuantos))

        # Las pruebas que quedaron sin ninguna medicion eran de esos jugadores.
        vacias = Evaluacion.objects.filter(mediciones__isnull=True)
        cuantas = vacias.count()
        if cuantas:
            for evaluacion in vacias:
                evaluacion.indicadores.clear()
            vacias.delete()
            self.stdout.write(self.style.WARNING('  se borraron %s pruebas vacias' % cuantas))

    # ------------------------------------------------------------------
    def crear_pruebas(self, grupo, alumnos):
        for dias_atras, titulo, tipo, mediciones in PRUEBAS:
            fecha = HOY - timedelta(days=dias_atras)

            evaluacion, creada = Evaluacion.objects.get_or_create(
                titulo=titulo, categoria=grupo,
                defaults={'fecha': fecha, 'fecha_fin': fecha + timedelta(days=2),
                          'tipo': TipoEvaluacion.objects.filter(nombre=tipo).first()}
            )
            if not creada:
                continue

            indicadores = []
            for nombre, valores in mediciones:
                indicador = Indicador.objects.filter(nombre=nombre).first()
                if indicador is None:
                    continue
                indicadores.append(indicador)

                for posicion, valor in enumerate(valores):
                    if valor is None or posicion >= len(alumnos):
                        continue  # ese dia no se le tomo a ese alumno
                    Medicion.objects.get_or_create(
                        evaluacion=evaluacion, jugador=alumnos[posicion], indicador=indicador,
                        defaults={'valor': Decimal(valor),
                                  'fecha': fecha + timedelta(days=posicion % 2)}
                    )

            evaluacion.indicadores.set(indicadores)
            self.stdout.write('  prueba %s (%s)' % (titulo, fecha.strftime('%d/%m/%Y')))

    def crear_medidas(self, alumnos):
        for posicion, dias_atras, peso, estatura in MEDIDAS:
            if posicion >= len(alumnos):
                continue
            ControlFisico.objects.get_or_create(
                jugador=alumnos[posicion], fecha=HOY - timedelta(days=dias_atras),
                defaults={'peso': Decimal(peso), 'estatura': estatura}
            )
        self.stdout.write('  peso y estatura: %s controles' % ControlFisico.objects.count())

    def crear_notas(self, alumnos, kevyn):
        for posicion, dias_atras, tipo, texto in NOTAS:
            if posicion >= len(alumnos):
                continue
            Nota.objects.get_or_create(
                jugador=alumnos[posicion], fecha=HOY - timedelta(days=dias_atras),
                defaults={'tipo': tipo, 'texto': texto, 'entrenador': kevyn}
            )
        self.stdout.write('  notas del profe: %s' % Nota.objects.count())

    def crear_mensualidades(self, alumnos):
        """Se abren los meses que le tocan a cada uno desde su ingreso."""
        for jugador in alumnos:
            poner_al_dia_jugador(jugador)

        # El primer mes de cada uno queda pagado: asi se ve cobrado y pendiente.
        for jugador in alumnos:
            primera = jugador.mensualidades_en_orden().first()
            if primera and not primera.esta_pagada():
                primera.estado = MENSUALIDAD_PAGADO
                primera.fecha_pago = primera.periodo_inicio
                primera.forma_pago = PAGO_EFECTIVO
                primera.save()

        self.stdout.write('  mensualidades abiertas para los tres alumnos')
