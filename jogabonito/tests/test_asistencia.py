# coding=utf-8
"""Pruebas de la FASE 2: registro de asistencia."""
import json
from datetime import date, time, timedelta

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from jogabonito.models import (
    ASISTENCIA_ATRASO, ASISTENCIA_FALTA, ASISTENCIA_JUSTIFICADO, ASISTENCIA_PRESENTE,
    ROL_ENTRENADOR, Asistencia, Categoria, Entrenador, Jugador, PerfilUsuario,
)

CLAVE = 'clave-de-prueba-2026'
HOY = date.today()
AYER = HOY - timedelta(days=1)


class BaseAsistencia(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('cargar_base', '--admin-clave', CLAVE, verbosity=0)
        cls.admin = User.objects.get(username='admin')

        cls.usuario_entrenador = User.objects.create_user('entrenador1', password=CLAVE)
        cls.usuario_entrenador.groups.add(Group.objects.get(name='ENTRENADOR'))
        PerfilUsuario.objects.create(usuario=cls.usuario_entrenador, rol=ROL_ENTRENADOR)
        cls.entrenador = Entrenador.objects.create(
            nombres='luis', apellidos='mora', telefono='0999999999', usuario=cls.usuario_entrenador
        )

        cls.mi_categoria = Categoria.objects.create(
            nombre='mi grupo', dias='1,3', hora_inicio=time(7, 0), hora_fin=time(9, 0), valor_mensual=25
        )
        cls.mi_categoria.entrenadores.add(cls.entrenador)
        cls.otra_categoria = Categoria.objects.create(
            nombre='otro grupo', dias='2,4', hora_inicio=time(18, 0), hora_fin=time(20, 0), valor_mensual=25
        )

        cls.jugador = Jugador.objects.create(
            nombres='pedro', apellidos='vera', fecha_nacimiento=date(2013, 3, 3), categoria=cls.mi_categoria
        )
        cls.companiero = Jugador.objects.create(
            nombres='ana', apellidos='pozo', fecha_nacimiento=date(2013, 6, 6), categoria=cls.mi_categoria
        )
        cls.retirado = Jugador.objects.create(
            nombres='raul', apellidos='cruz', fecha_nacimiento=date(2013, 7, 7),
            categoria=cls.mi_categoria, estado=3
        )
        cls.jugador_ajeno = Jugador.objects.create(
            nombres='sofia', apellidos='ruiz', fecha_nacimiento=date(2013, 4, 4), categoria=cls.otra_categoria
        )

    def marcar(self, jugador, estado, categoria=None, fecha=None):
        return self.client.post('/sistema/adm_asistencia', {
            'action': 'marcar',
            'categoria': (categoria or self.mi_categoria).id,
            'fecha': (fecha or HOY).strftime('%Y-%m-%d'),
            'jugador': jugador.id,
            'estado': estado,
        })


class ModeloAsistenciaTest(BaseAsistencia):
    def test_no_permite_dos_registros_del_mismo_jugador_en_la_misma_fecha(self):
        Asistencia.objects.create(jugador=self.jugador, categoria=self.mi_categoria,
                                  fecha=HOY, estado=ASISTENCIA_PRESENTE)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Asistencia.objects.create(jugador=self.jugador, categoria=self.mi_categoria,
                                          fecha=HOY, estado=ASISTENCIA_FALTA)

    def test_porcentaje_cuenta_presentes_y_atrasos(self):
        base = HOY - timedelta(days=10)
        estados = [ASISTENCIA_PRESENTE, ASISTENCIA_PRESENTE, ASISTENCIA_ATRASO,
                   ASISTENCIA_FALTA, ASISTENCIA_JUSTIFICADO]
        for indice, estado in enumerate(estados):
            Asistencia.objects.create(jugador=self.jugador, categoria=self.mi_categoria,
                                      fecha=base + timedelta(days=indice), estado=estado)

        resumen = self.jugador.resumen_asistencia()
        self.assertEqual(resumen['total'], 5)
        self.assertEqual(resumen['presentes'], 2)
        self.assertEqual(resumen['atrasos'], 1)
        self.assertEqual(resumen['faltas'], 1)
        self.assertEqual(resumen['justificados'], 1)
        self.assertEqual(resumen['porcentaje'], 60.0)  # (2 presentes + 1 atraso) / 5

    def test_sin_registros_el_porcentaje_es_cero(self):
        self.assertEqual(self.jugador.porcentaje_asistencia(), 0.0)

    def test_borrar_al_jugador_arrastra_sus_asistencias(self):
        Asistencia.objects.create(jugador=self.companiero, categoria=self.mi_categoria,
                                  fecha=HOY, estado=ASISTENCIA_PRESENTE)
        self.companiero.delete()
        self.assertEqual(Asistencia.objects.filter(jugador_id=self.companiero.id).count(), 0)


class MarcarAsistenciaTest(BaseAsistencia):
    def setUp(self):
        self.client.force_login(self.usuario_entrenador)

    def test_el_entrenador_marca_a_su_jugador(self):
        respuesta = self.marcar(self.jugador, ASISTENCIA_PRESENTE)
        datos = json.loads(respuesta.content)

        self.assertEqual(datos['result'], 'ok')
        self.assertEqual(datos['resumen']['presentes'], 1)
        self.assertEqual(datos['resumen']['total'], 2)      # solo los activos
        self.assertEqual(datos['resumen']['pendientes'], 1)

        asistencia = Asistencia.objects.get(jugador=self.jugador, fecha=HOY)
        self.assertEqual(asistencia.estado, ASISTENCIA_PRESENTE)
        self.assertEqual(asistencia.usuario_creacion, self.usuario_entrenador)

    def test_marcar_dos_veces_actualiza_en_vez_de_duplicar(self):
        self.marcar(self.jugador, ASISTENCIA_PRESENTE)
        self.marcar(self.jugador, ASISTENCIA_ATRASO)

        registros = Asistencia.objects.filter(jugador=self.jugador, fecha=HOY)
        self.assertEqual(registros.count(), 1)
        self.assertEqual(registros.first().estado, ASISTENCIA_ATRASO)
        self.assertEqual(registros.first().usuario_modificacion, self.usuario_entrenador)

    def test_no_marca_a_un_jugador_de_otra_categoria(self):
        respuesta = self.marcar(self.jugador_ajeno, ASISTENCIA_PRESENTE, categoria=self.otra_categoria)
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertEqual(Asistencia.objects.count(), 0)

    def test_no_mezcla_un_jugador_con_una_categoria_que_no_es_la_suya(self):
        """Aunque la categoria sea suya, el jugador debe pertenecer a ella."""
        respuesta = self.marcar(self.jugador_ajeno, ASISTENCIA_PRESENTE, categoria=self.mi_categoria)
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertEqual(Asistencia.objects.count(), 0)

    def test_no_marca_a_un_jugador_retirado(self):
        respuesta = self.marcar(self.retirado, ASISTENCIA_PRESENTE)
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertEqual(Asistencia.objects.count(), 0)

    def test_no_acepta_fechas_futuras(self):
        respuesta = self.marcar(self.jugador, ASISTENCIA_PRESENTE, fecha=HOY + timedelta(days=1))
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertEqual(Asistencia.objects.count(), 0)

    def test_no_acepta_un_estado_inventado(self):
        respuesta = self.client.post('/sistema/adm_asistencia', {
            'action': 'marcar', 'categoria': self.mi_categoria.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'jugador': self.jugador.id, 'estado': 99,
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertEqual(Asistencia.objects.count(), 0)

    def test_si_puede_registrar_una_fecha_pasada(self):
        respuesta = self.marcar(self.jugador, ASISTENCIA_FALTA, fecha=AYER)
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertTrue(Asistencia.objects.filter(jugador=self.jugador, fecha=AYER).exists())


class MarcarTodosTest(BaseAsistencia):
    def setUp(self):
        self.client.force_login(self.usuario_entrenador)

    def test_marca_solo_a_los_que_faltan_y_respeta_lo_ya_marcado(self):
        Asistencia.objects.create(jugador=self.jugador, categoria=self.mi_categoria,
                                  fecha=HOY, estado=ASISTENCIA_FALTA)

        respuesta = self.client.post('/sistema/adm_asistencia', {
            'action': 'marcartodos', 'categoria': self.mi_categoria.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'estado': ASISTENCIA_PRESENTE,
        })
        datos = json.loads(respuesta.content)

        self.assertEqual(datos['result'], 'ok')
        self.assertEqual(Asistencia.objects.filter(fecha=HOY).count(), 2)  # el retirado no entra
        self.assertEqual(
            Asistencia.objects.get(jugador=self.jugador, fecha=HOY).estado, ASISTENCIA_FALTA
        )
        self.assertEqual(
            Asistencia.objects.get(jugador=self.companiero, fecha=HOY).estado, ASISTENCIA_PRESENTE
        )

    def test_no_marca_en_una_categoria_ajena(self):
        respuesta = self.client.post('/sistema/adm_asistencia', {
            'action': 'marcartodos', 'categoria': self.otra_categoria.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'estado': ASISTENCIA_PRESENTE,
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertEqual(Asistencia.objects.count(), 0)


class DetalleYBorradoTest(BaseAsistencia):
    def setUp(self):
        self.client.force_login(self.usuario_entrenador)

    def test_guarda_estado_con_observacion(self):
        respuesta = self.client.post('/sistema/adm_asistencia', {
            'action': 'detalle', 'categoria': self.mi_categoria.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'jugador': self.jugador.id,
            'estado': ASISTENCIA_JUSTIFICADO, 'observacion': 'presento certificado medico',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        asistencia = Asistencia.objects.get(jugador=self.jugador, fecha=HOY)
        self.assertEqual(asistencia.estado, ASISTENCIA_JUSTIFICADO)
        self.assertEqual(asistencia.observacion, 'presento certificado medico')

    def test_borra_una_marca_equivocada(self):
        self.marcar(self.jugador, ASISTENCIA_PRESENTE)
        respuesta = self.client.post('/sistema/adm_asistencia', {
            'action': 'borrar', 'categoria': self.mi_categoria.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'jugador': self.jugador.id,
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertEqual(Asistencia.objects.count(), 0)

    def marcar(self, jugador, estado):
        return self.client.post('/sistema/adm_asistencia', {
            'action': 'marcar', 'categoria': self.mi_categoria.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'jugador': jugador.id, 'estado': estado,
        })


class PantallaAsistenciaTest(BaseAsistencia):
    def test_el_entrenador_ve_solo_sus_grupos_y_sus_jugadores_activos(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/adm_asistencia?categoria=%s' % self.mi_categoria.id)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([c.id for c in respuesta.context['categorias']], [self.mi_categoria.id])
        ids = [fila['jugador'].id for fila in respuesta.context['filas']]
        self.assertIn(self.jugador.id, ids)
        self.assertNotIn(self.retirado.id, ids)
        self.assertNotIn(self.jugador_ajeno.id, ids)

    def test_no_abre_una_categoria_ajena(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/adm_asistencia?categoria=%s' % self.otra_categoria.id)
        self.assertIsNone(respuesta.context)

    def test_el_administrador_ve_todas_las_categorias(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get('/sistema/adm_asistencia')
        ids = [c.id for c in respuesta.context['categorias']]
        self.assertIn(self.mi_categoria.id, ids)
        self.assertIn(self.otra_categoria.id, ids)

    def test_anonimo_no_entra(self):
        respuesta = self.client.get('/sistema/adm_asistencia')
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/sistema/login/', respuesta['Location'])

    def test_el_historial_ajeno_no_se_abre(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/adm_asistencia?action=historial&id=%s' % self.jugador_ajeno.id)
        self.assertIsNone(respuesta.context)

    def test_el_historial_propio_si_se_abre(self):
        Asistencia.objects.create(jugador=self.jugador, categoria=self.mi_categoria,
                                  fecha=AYER, estado=ASISTENCIA_PRESENTE)
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/adm_asistencia?action=historial&id=%s' % self.jugador.id)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['resumen']['porcentaje'], 100.0)

    def test_el_historial_conserva_el_jugador_al_cambiar_de_pagina(self):
        for indice in range(31):
            Asistencia.objects.create(
                jugador=self.jugador, categoria=self.mi_categoria,
                fecha=HOY - timedelta(days=indice), estado=ASISTENCIA_PRESENTE,
            )

        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get(
            '/sistema/adm_asistencia?action=historial&id=%s&page=2' % self.jugador.id)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['jugador'], self.jugador)
        self.assertEqual(respuesta.context['page'].number, 2)
        self.assertContains(
            respuesta,
            'action=historial&amp;id=%s&amp;page=1' % self.jugador.id,
            html=False,
        )
