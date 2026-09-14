# coding=utf-8
"""Dos reglas que pidio el usuario despues de usar el sistema:

1. El descuento se habla de dos maneras: "hazme el 10 por ciento" o "cobrame
   5 menos". Las dos tienen que entrar, y el motivo va en el MES, porque un
   descuento puede durar dos meses y despues no.
2. Lo que ya tiene datos adentro no se borra: un jugador nunca, una prueba con
   mediciones tampoco, una solicitud que ya se volvio alumno tampoco.
"""
import json
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase

from jogabonito.models import (
    AREA_TECNICA, MEDIDA_ESCALA, ROL_ENTRENADOR, SOLICITUD_INSCRITO, SOLICITUD_NUEVA,
    Categoria, Entrenador, Evaluacion, Indicador, Jugador, Medicion, Mensualidad,
    PerfilUsuario, SolicitudInscripcion,
)

CLAVE = 'clave-de-prueba-2026'
HOY = date.today()


class BaseDescuentos(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command('cargar_base', '--admin-clave', CLAVE, verbosity=0)
        cls.admin = User.objects.get(username='admin')

        cls.categoria = Categoria.objects.create(
            nombre='tarde', dias='1,3,5', hora_inicio=time(15, 0), hora_fin=time(17, 0),
            valor_mensual=Decimal('25.00')
        )
        cls.jugador = Jugador.objects.create(
            nombres='ana', apellidos='pena', fecha_nacimiento=date(2012, 4, 10),
            categoria=cls.categoria, fecha_ingreso=date(2026, 6, 10)
        )

    def setUp(self):
        self.client.force_login(self.admin)


class DescuentoEnDolaresTest(BaseDescuentos):
    """Lo mismo se puede decir en porcentaje o en plata."""

    def crear(self, **extra):
        datos = {'action': 'add', 'jugador': self.jugador.id,
                 'periodo_inicio': '2026-09-10', 'periodo_fin': '2026-10-09',
                 'valor': '25.00'}
        datos.update(extra)
        return self.client.post('/sistema/adm_mensualidad', datos)

    def test_en_dolares_baja_esa_plata_exacta(self):
        self.crear(descuento_monto='5.00', motivo_descuento='Acuerdo de este mes')

        mensualidad = Mensualidad.objects.get(jugador=self.jugador)
        self.assertEqual(mensualidad.valor, Decimal('20.00'))
        self.assertEqual(mensualidad.valor_completo, Decimal('25.00'))
        self.assertEqual(mensualidad.descuento_monto, Decimal('5.00'))
        self.assertIn('$ 5 de descuento', mensualidad.texto_descuento())

    def test_en_porcentaje_saca_el_porcentaje(self):
        self.crear(descuento_aplicado='10', motivo_descuento='Beca')

        mensualidad = Mensualidad.objects.get(jugador=self.jugador)
        self.assertEqual(mensualidad.valor, Decimal('22.50'))
        self.assertEqual(mensualidad.descuento_monto, Decimal('0'))
        self.assertIn('10% de descuento', mensualidad.texto_descuento())

    def test_si_pone_los_dos_manda_la_plata(self):
        """Es lo que la gente dice en voz alta: "cobrame 5 menos"."""
        self.crear(descuento_aplicado='50', descuento_monto='5.00',
                   motivo_descuento='Acuerdo')

        mensualidad = Mensualidad.objects.get(jugador=self.jugador)
        self.assertEqual(mensualidad.valor, Decimal('20.00'))
        self.assertEqual(mensualidad.descuento_aplicado, Decimal('0'))

    def test_no_se_puede_descontar_mas_de_lo_que_cuesta(self):
        respuesta = self.crear(descuento_monto='90.00')
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertFalse(Mensualidad.objects.filter(jugador=self.jugador).exists())

    def test_el_motivo_se_guarda_en_el_mes_no_en_la_persona(self):
        """Un mes con rebaja y el siguiente completo: cada uno con su historia."""
        self.crear(descuento_monto='5.00', motivo_descuento='Se lesiono')
        self.crear(periodo_inicio='2026-10-10', periodo_fin='2026-11-09')

        con_rebaja = Mensualidad.objects.get(jugador=self.jugador, periodo_inicio=date(2026, 9, 10))
        completo = Mensualidad.objects.get(jugador=self.jugador, periodo_inicio=date(2026, 10, 10))

        self.assertEqual(con_rebaja.motivo_descuento, 'Se lesiono')
        self.assertEqual(con_rebaja.valor, Decimal('20.00'))
        self.assertEqual(completo.motivo_descuento, '')
        self.assertEqual(completo.valor, Decimal('25.00'))

    def test_el_descuento_del_jugador_puede_ir_en_dolares(self):
        self.client.post('/sistema/adm_mensualidad', {
            'action': 'precio', 'id': self.jugador.id, 'cobro_activo': 'on',
            'descuento': '0', 'descuento_monto': '5.00',
            'motivo_descuento': 'hermano en la academia',
        })
        self.jugador.refresh_from_db()
        self.assertEqual(self.jugador.valor_mensual_vigente(), Decimal('20.00'))
        self.assertIn('$ 5 de descuento', self.jugador.explicacion_precio())

    def test_editando_el_mes_tambien_se_le_puede_bajar_el_precio(self):
        """La pantalla de editar es la que se usa cuando ya estaba creado."""
        self.crear()
        mensualidad = Mensualidad.objects.get(jugador=self.jugador)

        respuesta = self.client.post('/sistema/adm_mensualidad', {
            'action': 'pagar', 'id': mensualidad.id,
            'periodo_inicio': '2026-09-10', 'periodo_fin': '2026-10-09',
            'fecha_vencimiento': '2026-09-10', 'valor_completo': '25.00',
            'descuento_monto': '7.50', 'motivo_descuento': 'Acuerdo de este mes',
            'estado': 1, 'dias_ausente': 0,
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        mensualidad.refresh_from_db()
        self.assertEqual(mensualidad.valor, Decimal('17.50'))
        self.assertEqual(mensualidad.descuento_monto, Decimal('7.50'))

    def test_la_ausencia_se_descuenta_despues_de_la_rebaja(self):
        """Primero la rebaja del mes y sobre eso los dias que aviso."""
        self.crear(descuento_monto='5.00', motivo_descuento='Acuerdo')
        mensualidad = Mensualidad.objects.get(jugador=self.jugador)

        # 30 dias de periodo, avisa que falta 6: paga 24/30 de 20.
        mensualidad.dias_ausente = 6
        self.assertEqual(mensualidad.recalcular_por_ausencia(), Decimal('16.00'))


class NoSeBorraLoQueTieneDatosTest(BaseDescuentos):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.indicador = Indicador.objects.create(
            nombre='pase de prueba', area=AREA_TECNICA, tipo_medida=MEDIDA_ESCALA, orden=1
        )
        cls.con_mediciones = Evaluacion.objects.create(
            categoria=cls.categoria, fecha=HOY - timedelta(days=5), titulo='con datos'
        )
        cls.con_mediciones.indicadores.add(cls.indicador)
        Medicion.objects.create(
            evaluacion=cls.con_mediciones, jugador=cls.jugador,
            indicador=cls.indicador, valor=Decimal('7.00')
        )
        cls.vacia = Evaluacion.objects.create(
            categoria=cls.categoria, fecha=HOY - timedelta(days=3), titulo='sin datos'
        )

    def test_al_jugador_no_lo_borra_nadie(self):
        respuesta = self.client.post('/sistema/adm_jugador',
                                     {'action': 'delete', 'id': self.jugador.id})
        datos = json.loads(respuesta.content)
        self.assertEqual(datos['result'], 'bad')
        self.assertTrue(Jugador.objects.filter(pk=self.jugador.pk).exists())

    def test_el_modal_explica_que_se_desactiva(self):
        respuesta = self.client.get('/sistema/adm_jugador?action=delete&id=%s' % self.jugador.id)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'desactivarlo')

    def test_una_prueba_con_mediciones_no_se_borra(self):
        respuesta = self.client.post('/sistema/adm_evaluacion',
                                     {'action': 'delete', 'id': self.con_mediciones.id})
        datos = json.loads(respuesta.content)
        self.assertEqual(datos['result'], 'bad')
        self.assertIn('1 medicion', datos['mensaje'])
        self.assertTrue(Evaluacion.objects.filter(pk=self.con_mediciones.pk).exists())

    def test_una_prueba_vacia_si_se_borra(self):
        """Si nadie la dio todavia, fue un error al crearla."""
        respuesta = self.client.post('/sistema/adm_evaluacion',
                                     {'action': 'delete', 'id': self.vacia.id})
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertFalse(Evaluacion.objects.filter(pk=self.vacia.pk).exists())

    def test_la_solicitud_que_ya_es_alumno_no_se_borra(self):
        solicitud = SolicitudInscripcion.objects.create(
            nombre='juan cruz', telefono='0999999999', edad=13,
            estado=SOLICITUD_INSCRITO
        )
        respuesta = self.client.post('/sistema/adm_solicitud',
                                     {'action': 'delete', 'id': solicitud.id})
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertTrue(SolicitudInscripcion.objects.filter(pk=solicitud.pk).exists())

    def test_la_solicitud_nueva_si_se_borra(self):
        solicitud = SolicitudInscripcion.objects.create(
            nombre='spam spam', telefono='0900000000', edad=12,
            estado=SOLICITUD_NUEVA
        )
        respuesta = self.client.post('/sistema/adm_solicitud',
                                     {'action': 'delete', 'id': solicitud.id})
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertFalse(SolicitudInscripcion.objects.filter(pk=solicitud.pk).exists())


class TodasLasAsistenciasTest(BaseDescuentos):
    """La pantalla para ver todo lo que se marco, no solo el dia de hoy."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.usuario_entrenador = User.objects.create_user('profedesc', password=CLAVE)
        cls.usuario_entrenador.groups.add(Group.objects.get(name='ENTRENADOR'))
        PerfilUsuario.objects.create(usuario=cls.usuario_entrenador, rol=ROL_ENTRENADOR)
        cls.profe = Entrenador.objects.create(
            nombres='ruth', apellidos='paez', usuario=cls.usuario_entrenador
        )
        cls.categoria.entrenadores.add(cls.profe)

    def marcar(self, dias_atras, estado):
        from jogabonito.models import Asistencia
        Asistencia.objects.create(
            jugador=self.jugador, categoria=self.categoria,
            fecha=HOY - timedelta(days=dias_atras), estado=estado
        )

    def test_resume_como_vino_cada_uno_en_el_rango(self):
        self.marcar(2, 1)
        self.marcar(4, 1)
        self.marcar(6, 2)

        respuesta = self.client.get('/sistema/adm_asistencia?action=todas&desde=%s&hasta=%s' % (
            (HOY - timedelta(days=10)).strftime('%Y-%m-%d'), HOY.strftime('%Y-%m-%d')))

        self.assertEqual(respuesta.status_code, 200)
        fila = respuesta.context['resumen'][0]
        self.assertEqual(fila['jugador'], self.jugador)
        self.assertEqual(fila['total'], 3)
        self.assertEqual(fila['presentes'], 2)
        self.assertEqual(fila['faltas'], 1)
        self.assertEqual(fila['porcentaje'], 66.7)

    def test_el_rango_deja_fuera_lo_de_antes(self):
        self.marcar(2, 1)
        self.marcar(60, 1)

        respuesta = self.client.get('/sistema/adm_asistencia?action=todas&desde=%s&hasta=%s' % (
            (HOY - timedelta(days=10)).strftime('%Y-%m-%d'), HOY.strftime('%Y-%m-%d')))
        self.assertEqual(respuesta.context['resumen'][0]['total'], 1)

    def test_el_entrenador_solo_ve_sus_grupos(self):
        otra = Categoria.objects.create(
            nombre='ajena', dias='2,4', hora_inicio=time(9, 0), hora_fin=time(11, 0),
            valor_mensual=Decimal('25.00')
        )
        ajeno = Jugador.objects.create(
            nombres='otro', apellidos='chico', fecha_nacimiento=date(2012, 1, 1),
            categoria=otra, fecha_ingreso=HOY - timedelta(days=30)
        )
        from jogabonito.models import Asistencia
        Asistencia.objects.create(jugador=ajeno, categoria=otra, fecha=HOY, estado=1)
        self.marcar(1, 1)

        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/adm_asistencia?action=todas')

        jugadores = [f['jugador'] for f in respuesta.context['resumen']]
        self.assertIn(self.jugador, jugadores)
        self.assertNotIn(ajeno, jugadores)


class HistorialDePagosTest(BaseDescuentos):
    """Un chico puede llevar anios: el historial va agrupado por anio."""

    def test_agrupa_por_anio_y_saca_los_totales(self):
        from jogabonito.models import MENSUALIDAD_PAGADO

        Mensualidad.objects.create(
            jugador=self.jugador, mes=12, anio=2025, valor=Decimal('25.00'),
            valor_completo=Decimal('25.00'), fecha_vencimiento=date(2025, 12, 10),
            periodo_inicio=date(2025, 12, 10), periodo_fin=date(2026, 1, 9),
            estado=MENSUALIDAD_PAGADO, fecha_pago=date(2025, 12, 11)
        )
        Mensualidad.objects.create(
            jugador=self.jugador, mes=1, anio=2026, valor=Decimal('25.00'),
            valor_completo=Decimal('25.00'), fecha_vencimiento=date(2026, 1, 10),
            periodo_inicio=date(2026, 1, 10), periodo_fin=date(2026, 2, 9)
        )

        historial = self.jugador.historial_de_pagos()
        self.assertEqual(historial['cuantos'], 2)
        self.assertEqual(historial['total_pagado'], Decimal('25.00'))
        self.assertEqual(historial['total_pendiente'], Decimal('25.00'))
        self.assertEqual([a['anio'] for a in historial['anios']], [2026, 2025])

    def test_la_pantalla_abre_con_el_jugador(self):
        respuesta = self.client.get(
            '/sistema/adm_mensualidad?action=historial&id=%s' % self.jugador.id)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['jugador'], self.jugador)

    def test_en_el_historial_solo_se_puede_eliminar_la_pendiente(self):
        from jogabonito.models import MENSUALIDAD_PAGADO

        pendiente = Mensualidad.objects.create(
            jugador=self.jugador, mes=1, anio=2026, valor=Decimal('25.00'),
            fecha_vencimiento=date(2026, 1, 10), estado=1
        )
        pagada = Mensualidad.objects.create(
            jugador=self.jugador, mes=2, anio=2026, valor=Decimal('25.00'),
            fecha_vencimiento=date(2026, 2, 10), estado=MENSUALIDAD_PAGADO
        )

        respuesta = self.client.get(
            '/sistema/adm_mensualidad?action=historial&id=%s' % self.jugador.id)

        self.assertContains(respuesta, 'action=delete&amp;id=%s' % pendiente.id, html=False)
        self.assertNotContains(respuesta, 'action=delete&amp;id=%s' % pagada.id, html=False)


class AQuienLeTocaPagarTest(BaseDescuentos):
    """La lista de a quien se le viene el mes encima."""

    def test_separa_a_los_que_ya_les_toca_de_los_que_faltan(self):
        respuesta = self.client.get('/sistema/adm_mensualidad?action=proximos')
        self.assertEqual(respuesta.status_code, 200)

        todos = (list(respuesta.context['ya_toca'])
                 + list(respuesta.context['esta_semana'])
                 + list(respuesta.context['despues']))
        self.assertIn(self.jugador, [f['jugador'] for f in todos])

    def test_el_que_tiene_el_cobro_apagado_sale_aparte(self):
        self.jugador.cobro_activo = False
        self.jugador.save()

        respuesta = self.client.get('/sistema/adm_mensualidad?action=proximos')
        self.assertIn(self.jugador, list(respuesta.context['apagados']))
