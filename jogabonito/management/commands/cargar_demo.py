# coding=utf-8
"""Datos de ejemplo para probar el sistema sin ensuciar la base real.

    py manage.py cargar_demo            # crea entrenador, representantes, jugadores y asistencia
    py manage.py cargar_demo --borrar   # borra SOLO lo que creo este comando
"""
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from decimal import Decimal

from jogabonito.models import (
    ASISTENCIA_ATRASO, ASISTENCIA_FALTA, ASISTENCIA_JUSTIFICADO, ASISTENCIA_PRESENTE,
    AREAS_INDICADOR, MEDIDA_ESCALA, MEDIDA_TIEMPO, Asistencia, Categoria, Entrenador, Evaluacion,
    Indicador, Jugador, Medicion, Posicion, Representante, TipoEvaluacion,
)

MARCA = '[DEMO]'

ENTRENADORES = [
    ('CARLOS', 'ANDRADE', '0987112233'),
    ('JORGE', 'VILLACIS', '0987445566'),
]

REPRESENTANTES = [
    ('MARIA', 'TORRES', '0991122334', 2),
    ('LUIS', 'GUAMAN', '0992233445', 1),
]

JUGADORES = [
    ('MATEO', 'TORRES LEON', 2014),
    ('SEBASTIAN', 'GUAMAN PEREZ', 2013),
    ('JOAQUIN', 'LOPEZ DIAZ', 2015),
    ('DAMIAN', 'CHICAIZA MORA', 2014),
    ('EMILIO', 'SANCHEZ RUIZ', 2013),
    ('THIAGO', 'PAREDES SILVA', 2015),
]

ESTADOS_SORTEO = (
    [ASISTENCIA_PRESENTE] * 7 + [ASISTENCIA_FALTA] * 2 + [ASISTENCIA_ATRASO, ASISTENCIA_JUSTIFICADO]
)


class Command(BaseCommand):
    help = 'Crea (o borra) datos de ejemplo: entrenadores, jugadores y asistencia de las ultimas semanas.'

    def add_arguments(self, parser):
        parser.add_argument('--borrar', action='store_true', help='Elimina los datos de ejemplo.')
        parser.add_argument('--semanas', type=int, default=3, help='Semanas de asistencia a generar.')

    @transaction.atomic
    def handle(self, *args, **opciones):
        if opciones['borrar']:
            return self.borrar_datos()

        categorias = list(Categoria.objects.filter(activo=True).order_by('hora_inicio'))
        if not categorias:
            self.stdout.write(self.style.ERROR(
                'No hay categorias. Ejecuta primero: manage.py cargar_base --demo'))
            return

        entrenadores = []
        for nombres, apellidos, telefono in ENTRENADORES:
            entrenador, _ = Entrenador.objects.get_or_create(
                nombres=nombres, apellidos=apellidos,
                defaults={'telefono': telefono, 'email': '', 'activo': True}
            )
            entrenadores.append(entrenador)

        for indice, categoria in enumerate(categorias):
            categoria.entrenadores.add(entrenadores[indice % len(entrenadores)])

        representantes = []
        for nombres, apellidos, telefono, parentesco in REPRESENTANTES:
            representante, _ = Representante.objects.get_or_create(
                nombres=nombres, apellidos=apellidos,
                defaults={'telefono': telefono, 'whatsapp': '593' + telefono[1:],
                          'parentesco': parentesco, 'direccion': MARCA}
            )
            representantes.append(representante)

        # Los grupos demo quedan tambien separados por edad.
        for indice, categoria in enumerate(categorias):
            if categoria.edad_minima is None and categoria.edad_maxima is None:
                categoria.edad_minima = 6 + indice * 4
                categoria.edad_maxima = 9 + indice * 4
                categoria.save()

        posiciones = list(Posicion.objects.filter(activo=True).order_by('orden'))
        jugadores = []
        for indice, (nombres, apellidos, anio) in enumerate(JUGADORES):
            jugador, _ = Jugador.objects.get_or_create(
                nombres=nombres, apellidos=apellidos,
                defaults={
                    'fecha_nacimiento': date(anio, ((indice * 2) % 12) + 1, 12),
                    'categoria': categorias[indice % len(categorias)],
                    'representante': representantes[indice % len(representantes)],
                    'fecha_ingreso': date.today() - timedelta(days=60),
                    'posicion': posiciones[indice % len(posiciones)] if posiciones else None,
                    'pie_habil': (indice % 3) + 1,
                    'dorsal': 5 + indice,
                    'observacion': MARCA,
                }
            )
            jugadores.append(jugador)

        sorteo = random.Random(2026)
        creadas = 0
        for jugador in jugadores:
            dias = jugador.categoria.dias_lista()
            for atras in range(1, opciones['semanas'] * 7 + 1):
                dia = date.today() - timedelta(days=atras)
                if str(dia.isoweekday()) not in dias:
                    continue
                _, creada = Asistencia.objects.get_or_create(
                    jugador=jugador, categoria=jugador.categoria, fecha=dia,
                    defaults={'estado': sorteo.choice(ESTADOS_SORTEO)}
                )
                creadas += 1 if creada else 0

        # --- pruebas semanales con su progreso ---------------------------
        # Un indicador de cada area, para que la tela de arania salga completa.
        indicadores = []
        for area, _etiqueta in AREAS_INDICADOR:
            indicador = Indicador.objects.filter(activo=True, area=area).order_by('orden').first()
            if indicador:
                indicadores.append(indicador)
        mediciones = 0
        if indicadores:
            for categoria in categorias:
                del_grupo = [j for j in jugadores if j.categoria_id == categoria.id]
                if not del_grupo:
                    continue
                inicial = TipoEvaluacion.objects.filter(es_inicial=True).first()
                seguimiento = TipoEvaluacion.objects.filter(
                    activo=True, es_inicial=False).order_by('orden').first()

                for semana in range(3):
                    fecha = date.today() - timedelta(days=21 - semana * 7)
                    evaluacion, _ = Evaluacion.objects.get_or_create(
                        categoria=categoria, fecha=fecha,
                        titulo='%s Prueba semanal %s' % (MARCA, semana + 1),
                        defaults={'tipo': inicial if semana == 0 else seguimiento}
                    )
                    evaluacion.indicadores.set(indicadores)
                    for jugador in del_grupo:
                        for indicador in indicadores:
                            if indicador.tipo_medida == MEDIDA_ESCALA:
                                valor = Decimal(str(min(10, 5 + semana + sorteo.randint(0, 2))))
                            elif indicador.tipo_medida == MEDIDA_TIEMPO:
                                valor = Decimal(str(round(5.6 - semana * 0.15 + sorteo.uniform(-0.2, 0.2), 2)))
                            else:
                                valor = Decimal(str(10 + semana * 4 + sorteo.randint(0, 6)))
                            Medicion.objects.update_or_create(
                                evaluacion=evaluacion, jugador=jugador, indicador=indicador,
                                defaults={'valor': valor}
                            )
                            mediciones += 1

        self.stdout.write('  entrenadores: %s' % len(entrenadores))
        self.stdout.write('  jugadores: %s' % len(jugadores))
        self.stdout.write('  asistencias creadas: %s' % creadas)
        self.stdout.write('  mediciones creadas: %s' % mediciones)
        self.stdout.write(self.style.SUCCESS('Datos de ejemplo listos.'))

    def borrar_datos(self):
        nombres_jugadores = [(n, a) for n, a, _ in JUGADORES]
        jugadores = Jugador.objects.none()
        for nombres, apellidos in nombres_jugadores:
            jugadores = jugadores | Jugador.objects.filter(nombres=nombres, apellidos=apellidos)

        Asistencia.objects.filter(jugador__in=jugadores).delete()
        Medicion.objects.filter(jugador__in=jugadores).delete()
        for evaluacion in Evaluacion.objects.filter(titulo__startswith=MARCA):
            evaluacion.indicadores.clear()
            evaluacion.delete()
        borrados = jugadores.count()
        jugadores.delete()

        for nombres, apellidos, _telefono, _parentesco in REPRESENTANTES:
            Representante.objects.filter(nombres=nombres, apellidos=apellidos).delete()

        for nombres, apellidos, _telefono in ENTRENADORES:
            entrenador = Entrenador.objects.filter(nombres=nombres, apellidos=apellidos).first()
            if entrenador:
                entrenador.categorias.clear()
                entrenador.delete()

        self.stdout.write(self.style.SUCCESS('Datos de ejemplo eliminados (%s jugadores).' % borrados))
