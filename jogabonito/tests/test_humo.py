# coding=utf-8
"""Prueba de humo: que TODAS las pantallas y modales abran sin reventar.

No revisa la logica (para eso estan las otras pruebas): revisa que no quede
una plantilla rota, una variable mal escrita o un modal que ya no existe.
Es la red que avisa cuando un cambio en un lado rompe otro.
"""
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase

from jogabonito.models import (
    AREA_TECNICA, MEDIDA_ESCALA, ROL_ENTRENADOR, Categoria, ControlFisico, Division, Entrenador,
    Evaluacion, Indicador, Jugador, Medicion, Mensualidad, Nota, PerfilUsuario, Posicion,
    Representante, SolicitudInscripcion, TipoEvaluacion,
)

CLAVE = 'clave-de-prueba-2026'
HOY = date.today()


class HumoTest(TestCase):
    """Una sola base de datos con un poco de todo, y a abrir todo."""

    @classmethod
    def setUpTestData(cls):
        call_command('cargar_base', '--admin-clave', CLAVE, verbosity=0)
        cls.admin = User.objects.get(username='admin')

        cls.usuario_entrenador = User.objects.create_user('profehumo', password=CLAVE)
        cls.usuario_entrenador.groups.add(Group.objects.get(name='ENTRENADOR'))
        PerfilUsuario.objects.create(usuario=cls.usuario_entrenador, rol=ROL_ENTRENADOR)
        cls.profe = Entrenador.objects.create(
            nombres='luis', apellidos='mora', telefono='0999999999', usuario=cls.usuario_entrenador
        )

        cls.categoria = Categoria.objects.create(
            nombre='manana', dias='1,2,3,4,5', hora_inicio=time(7, 0), hora_fin=time(9, 0),
            valor_mensual=Decimal('25.00')
        )
        cls.categoria.entrenadores.add(cls.profe)

        cls.representante = Representante.objects.create(
            nombres='maria', apellidos='torres', telefono='0988888888', parentesco=1
        )
        cls.jugador = Jugador.objects.create(
            nombres='pedro', apellidos='vera', apodo='pepe',
            fecha_nacimiento=date(2013, 3, 3), categoria=cls.categoria,
            representante=cls.representante, fecha_ingreso=HOY - timedelta(days=45),
            cuidados='fascitis plantar'
        )

        cls.indicador = Indicador.objects.create(
            nombre='control del balon', area=AREA_TECNICA, tipo_medida=MEDIDA_ESCALA, orden=1
        )
        cls.evaluacion = Evaluacion.objects.create(
            categoria=cls.categoria, fecha=HOY - timedelta(days=7),
            fecha_fin=HOY, titulo='prueba de humo'
        )
        cls.evaluacion.indicadores.set([cls.indicador])
        cls.medicion = Medicion.objects.create(
            evaluacion=cls.evaluacion, jugador=cls.jugador, indicador=cls.indicador,
            valor=Decimal('8'), fecha=HOY
        )

        cls.mensualidad = Mensualidad.objects.create(
            jugador=cls.jugador, mes=HOY.month, anio=HOY.year, valor=Decimal('25.00'),
            valor_completo=Decimal('25.00'), fecha_vencimiento=HOY,
            periodo_inicio=HOY, periodo_fin=HOY + timedelta(days=29)
        )
        cls.nota = Nota.objects.create(
            jugador=cls.jugador, fecha=HOY, tipo=1, texto='viene bien de actitud'
        )
        cls.control = ControlFisico.objects.create(
            jugador=cls.jugador, fecha=HOY, peso=Decimal('38.50'), estatura=145
        )
        cls.categoria.encargado = cls.profe
        cls.categoria.save()
        cls.solicitud = SolicitudInscripcion.objects.create(
            nombre='nino nuevo', telefono='0977777777', edad=10, categoria=cls.categoria
        )
        cls.posicion = Posicion.objects.first()
        cls.tipo = TipoEvaluacion.objects.first()
        cls.division = Division.objects.first()

    def abrir(self, url):
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200, 'se cayo: %s' % url)
        return respuesta

    # ------------------------------------------------ administrador
    def test_el_administrador_abre_todas_las_pantallas(self):
        self.client.force_login(self.admin)

        for url in [
            '/sistema/',
            '/sistema/dashboard',
            '/sistema/adm_asistencia',
            '/sistema/adm_asistencia?categoria=%s' % self.categoria.id,
            '/sistema/adm_jugador',
            '/sistema/adm_categoria',
            '/sistema/adm_entrenador',
            '/sistema/adm_representante',
            '/sistema/adm_mensualidad',
            '/sistema/adm_evaluacion',
            '/sistema/adm_indicador',
            '/sistema/adm_solicitud',
            '/sistema/adm_turno',
            '/sistema/micuenta',
        ]:
            self.abrir(url)

    def test_se_abren_todos_los_modales_de_jugadores(self):
        self.client.force_login(self.admin)
        jugador = self.jugador.id

        for url in [
            '/sistema/adm_jugador?action=add',
            '/sistema/adm_jugador?action=edit&id=%s' % jugador,
            '/sistema/adm_jugador?action=delete&id=%s' % jugador,
            '/sistema/adm_jugador?action=view&id=%s' % jugador,
            '/sistema/adm_jugador?action=representante&id=%s' % jugador,
            '/sistema/adm_evaluacion?action=nota&jugador=%s' % jugador,
            '/sistema/adm_evaluacion?action=borrarnota&id=%s' % self.nota.id,
            '/sistema/adm_evaluacion?action=control&jugador=%s' % jugador,
            '/sistema/adm_evaluacion?action=editcontrol&jugador=%s&id=%s' % (jugador, self.control.id),
            '/sistema/adm_evaluacion?action=borrarcontrol&id=%s' % self.control.id,
            '/sistema/adm_jugador?division=%s' % self.division.id,
            '/sistema/adm_jugador?cuenta=debe',
            '/sistema/adm_jugador?cuenta=aldia',
            '/sistema/adm_jugador?s=vera',
        ]:
            self.abrir(url)

    def test_se_abren_todos_los_modales_de_plata(self):
        self.client.force_login(self.admin)

        for url in [
            '/sistema/adm_mensualidad?action=pagar&id=%s' % self.mensualidad.id,
            '/sistema/adm_mensualidad?action=delete&id=%s' % self.mensualidad.id,
            '/sistema/adm_mensualidad?action=siguiente&id=%s' % self.jugador.id,
            '/sistema/adm_mensualidad?action=aldia',
            '/sistema/adm_mensualidad?action=add',
            '/sistema/adm_mensualidad?action=add&jugador=%s' % self.jugador.id,
            '/sistema/adm_mensualidad?action=precio&id=%s' % self.jugador.id,
            '/sistema/adm_mensualidad?action=generar',
            '/sistema/adm_mensualidad?action=deudores',
            '/sistema/adm_mensualidad?estado=atrasadas',
            '/sistema/adm_mensualidad?s=vera',
        ]:
            self.abrir(url)

    def test_se_abren_todas_las_pantallas_de_medir(self):
        self.client.force_login(self.admin)

        for url in [
            '/sistema/adm_evaluacion?action=add',
            '/sistema/adm_evaluacion?action=edit&id=%s' % self.evaluacion.id,
            '/sistema/adm_evaluacion?action=delete&id=%s' % self.evaluacion.id,
            '/sistema/adm_evaluacion?action=planilla&id=%s' % self.evaluacion.id,
            '/sistema/adm_evaluacion?action=progreso&id=%s' % self.jugador.id,
            '/sistema/adm_evaluacion?action=progreso&id=%s&desde=%s' % (
                self.jugador.id, (HOY - timedelta(days=30)).strftime('%Y-%m-%d')),
            '/sistema/adm_evaluacion?action=bajando',
            '/sistema/adm_evaluacion?action=bajando&categoria=%s' % self.categoria.id,
            '/sistema/adm_indicador?action=add',
            '/sistema/adm_indicador?action=edit&id=%s' % self.indicador.id,
            '/sistema/adm_indicador?action=delete&id=%s' % self.indicador.id,
            '/sistema/adm_indicador?action=addposicion',
            '/sistema/adm_indicador?action=editposicion&id=%s' % self.posicion.id,
            '/sistema/adm_indicador?action=delposicion&id=%s' % self.posicion.id,
            '/sistema/adm_indicador?action=addtipo',
            '/sistema/adm_indicador?action=edittipo&id=%s' % self.tipo.id,
            '/sistema/adm_indicador?action=deltipo&id=%s' % self.tipo.id,
        ]:
            self.abrir(url)

    def test_se_abren_los_modales_del_resto(self):
        self.client.force_login(self.admin)

        for url in [
            '/sistema/adm_categoria?action=add',
            '/sistema/adm_categoria?action=edit&id=%s' % self.categoria.id,
            '/sistema/adm_categoria?action=delete&id=%s' % self.categoria.id,
            '/sistema/adm_categoria?action=view&id=%s' % self.categoria.id,
            '/sistema/adm_categoria?action=adddivision',
            '/sistema/adm_categoria?action=editdivision&id=%s' % self.division.id,
            '/sistema/adm_categoria?action=deldivision&id=%s' % self.division.id,
            '/sistema/adm_entrenador?action=add',
            '/sistema/adm_entrenador?action=edit&id=%s' % self.profe.id,
            '/sistema/adm_entrenador?action=delete&id=%s' % self.profe.id,
            '/sistema/adm_entrenador?action=view&id=%s' % self.profe.id,
            '/sistema/adm_entrenador?action=usuario&id=%s' % self.profe.id,
            '/sistema/adm_representante?action=add',
            '/sistema/adm_representante?action=edit&id=%s' % self.representante.id,
            '/sistema/adm_representante?action=delete&id=%s' % self.representante.id,
            '/sistema/adm_representante?action=view&id=%s' % self.representante.id,
            '/sistema/adm_solicitud?action=gestionar&id=%s' % self.solicitud.id,
            '/sistema/adm_solicitud?action=delete&id=%s' % self.solicitud.id,
            '/sistema/adm_asistencia?action=detalle&categoria=%s&fecha=%s&jugador=%s' % (
                self.categoria.id, HOY.strftime('%Y-%m-%d'), self.jugador.id),
            '/sistema/adm_asistencia?action=historial&id=%s' % self.jugador.id,
            '/sistema/adm_turno',
        ]:
            self.abrir(url)

    # ------------------------------------------------ entrenador
    def test_el_entrenador_abre_lo_suyo(self):
        self.client.force_login(self.usuario_entrenador)

        for url in [
            '/sistema/',
            '/sistema/adm_asistencia',
            '/sistema/adm_asistencia?categoria=%s' % self.categoria.id,
            '/sistema/adm_evaluacion',
            '/sistema/adm_evaluacion?action=progreso&id=%s' % self.jugador.id,
            '/sistema/adm_evaluacion?action=bajando',
            '/sistema/adm_evaluacion?action=planilla&id=%s' % self.evaluacion.id,
            '/sistema/adm_evaluacion?action=nota&jugador=%s' % self.jugador.id,
            '/sistema/adm_evaluacion?action=control&jugador=%s' % self.jugador.id,
            '/sistema/micuenta',
        ]:
            self.abrir(url)

    def test_el_entrenador_no_entra_a_lo_del_administrador(self):
        self.client.force_login(self.usuario_entrenador)

        for url in ['/sistema/dashboard', '/sistema/adm_jugador', '/sistema/adm_mensualidad',
                    '/sistema/adm_categoria', '/sistema/adm_turno', '/sistema/adm_indicador']:
            respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 302, 'deberia estar cerrado: %s' % url)

    def test_la_pagina_publica_sigue_abriendo(self):
        self.abrir('/')

    # ------------------------------------------------ sin datos
    def test_todo_abre_tambien_con_la_base_vacia(self):
        """El caso del primer dia: sin jugadores, sin pruebas, sin nada."""
        Medicion.objects.all().delete()
        Mensualidad.objects.all().delete()
        Nota.objects.all().delete()
        ControlFisico.objects.all().delete()
        Evaluacion.objects.all().delete()
        Jugador.objects.all().delete()

        self.client.force_login(self.admin)
        for url in [
            '/sistema/dashboard',
            '/sistema/adm_jugador',
            '/sistema/adm_mensualidad',
            '/sistema/adm_mensualidad?action=aldia',
            '/sistema/adm_mensualidad?action=deudores',
            '/sistema/adm_evaluacion?action=bajando',
            '/sistema/adm_turno',
            '/sistema/adm_categoria',
            '/',
        ]:
            self.abrir(url)
