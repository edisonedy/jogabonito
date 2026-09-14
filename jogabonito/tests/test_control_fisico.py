# coding=utf-8
"""Pruebas del peso y la estatura, los cuidados de cada ninio, el ajuste del
valor de un mes y el boton de abrir el siguiente mes.
"""
import json
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from jogabonito.models import (
    MENSUALIDAD_PAGADO, PAGO_EFECTIVO, ROL_ENTRENADOR, Categoria, ControlFisico, Entrenador,
    Jugador, Mensualidad, PerfilUsuario,
)

CLAVE = 'clave-de-prueba-2026'
HOY = date.today()


class BaseFisico(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('cargar_base', '--admin-clave', CLAVE, verbosity=0)
        cls.admin = User.objects.get(username='admin')

        cls.usuario_entrenador = User.objects.create_user('profe3', password=CLAVE)
        cls.usuario_entrenador.groups.add(Group.objects.get(name='ENTRENADOR'))
        PerfilUsuario.objects.create(usuario=cls.usuario_entrenador, rol=ROL_ENTRENADOR)
        cls.profe = Entrenador.objects.create(
            nombres='luis', apellidos='mora', telefono='0999999999', usuario=cls.usuario_entrenador
        )

        cls.categoria = Categoria.objects.create(
            nombre='manana', dias='1,3,5', hora_inicio=time(7, 0), hora_fin=time(9, 0),
            valor_mensual=Decimal('25.00')
        )
        cls.categoria.entrenadores.add(cls.profe)

        cls.ajena = Categoria.objects.create(
            nombre='noche', dias='2,4', hora_inicio=time(18, 0), hora_fin=time(20, 0),
            valor_mensual=Decimal('25.00')
        )

        cls.jugador = Jugador.objects.create(
            nombres='pedro', apellidos='vera', fecha_nacimiento=date(2013, 3, 3),
            categoria=cls.categoria, fecha_ingreso=HOY - timedelta(days=40)
        )


class PesoYEstaturaTest(BaseFisico):
    def setUp(self):
        self.client.force_login(self.admin)

    def tomar(self, **extra):
        datos = {
            'action': 'control', 'jugador': self.jugador.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'peso': '38.50', 'estatura': 145,
        }
        datos.update(extra)
        return self.client.post('/sistema/adm_evaluacion', datos)

    def test_se_guarda_el_peso_y_la_estatura(self):
        respuesta = self.tomar()
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        control = ControlFisico.objects.get()
        self.assertEqual(control.jugador, self.jugador)
        self.assertEqual(control.peso, Decimal('38.50'))
        self.assertEqual(control.estatura, 145)
        self.assertEqual(control.texto_peso(), '38.5 kg')

    def test_calcula_el_imc(self):
        self.tomar()
        self.assertEqual(ControlFisico.objects.get().imc(), Decimal('18.3'))

    def test_sin_los_dos_datos_no_hay_imc(self):
        control = ControlFisico.objects.create(jugador=self.jugador, fecha=HOY, peso=Decimal('38'))
        self.assertIsNone(control.imc())

    def test_basta_con_uno_de_los_dos(self):
        respuesta = self.tomar(estatura='')
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertIsNone(ControlFisico.objects.get().estatura)

    def test_no_acepta_vacio(self):
        respuesta = self.tomar(peso='', estatura='')
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertEqual(ControlFisico.objects.count(), 0)

    def test_avisa_si_el_peso_es_absurdo(self):
        respuesta = self.tomar(peso='950')
        datos = json.loads(respuesta.content)
        self.assertEqual(datos['result'], 'bad')
        self.assertIn('10 y 200', datos['mensaje'])

    def test_avisa_si_la_estatura_va_en_metros(self):
        respuesta = self.tomar(estatura='1')
        datos = json.loads(respuesta.content)
        self.assertEqual(datos['result'], 'bad')
        self.assertIn('centimetros', datos['mensaje'])

    def test_no_acepta_una_fecha_futura(self):
        respuesta = self.tomar(fecha=(HOY + timedelta(days=1)).strftime('%Y-%m-%d'))
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')

    def test_no_deja_dos_controles_del_mismo_dia(self):
        self.tomar()
        respuesta = self.tomar(peso='39')
        datos = json.loads(respuesta.content)

        self.assertEqual(datos['result'], 'bad')
        self.assertIn('Ya hay un control de ese dia', datos['mensaje'])
        self.assertEqual(ControlFisico.objects.count(), 1)

    def test_la_base_tampoco_deja_repetir_el_dia(self):
        ControlFisico.objects.create(jugador=self.jugador, fecha=HOY, peso=Decimal('38'))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ControlFisico.objects.create(jugador=self.jugador, fecha=HOY, peso=Decimal('39'))

    def test_mide_el_crecimiento_entre_el_primero_y_el_ultimo(self):
        ControlFisico.objects.create(jugador=self.jugador, fecha=HOY - timedelta(days=60),
                                     peso=Decimal('36.00'), estatura=140)
        ControlFisico.objects.create(jugador=self.jugador, fecha=HOY,
                                     peso=Decimal('38.50'), estatura=145)

        crecimiento = self.jugador.crecimiento()
        self.assertEqual(crecimiento['estatura'], 5)
        self.assertEqual(crecimiento['peso'], Decimal('2.50'))
        self.assertEqual(crecimiento['dias'], 60)

    def test_con_un_solo_control_no_hay_crecimiento(self):
        self.tomar()
        self.assertIsNone(self.jugador.crecimiento())

    def test_se_edita_y_se_borra(self):
        self.tomar()
        control = ControlFisico.objects.get()

        self.client.post('/sistema/adm_evaluacion', {
            'action': 'editcontrol', 'id': control.id, 'jugador': self.jugador.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'peso': '40', 'estatura': 146,
        })
        control.refresh_from_db()
        self.assertEqual(control.estatura, 146)

        self.client.post('/sistema/adm_evaluacion', {'action': 'borrarcontrol', 'id': control.id})
        self.assertEqual(ControlFisico.objects.count(), 0)

    def test_el_entrenador_puede_tomar_medidas_a_los_suyos(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.tomar()
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

    def test_pero_no_a_los_de_otro_grupo(self):
        ajeno = Jugador.objects.create(
            nombres='sofia', apellidos='ruiz', fecha_nacimiento=date(2013, 4, 4),
            categoria=self.ajena
        )
        self.client.force_login(self.usuario_entrenador)
        self.client.post('/sistema/adm_evaluacion', {
            'action': 'control', 'jugador': ajeno.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'peso': '38',
        })
        self.assertEqual(ControlFisico.objects.count(), 0)

    def test_sale_en_la_ficha(self):
        self.tomar()
        respuesta = self.client.get('/sistema/adm_jugador?action=view&id=%s' % self.jugador.id)
        self.assertEqual(respuesta.context['ultimo_control'].estatura, 145)


class CuidadosDelJugadorTest(BaseFisico):
    def test_por_defecto_no_tiene(self):
        self.assertFalse(self.jugador.tiene_cuidados())

    def test_se_guarda_desde_la_ficha(self):
        self.client.force_login(self.admin)
        self.client.post('/sistema/adm_jugador', {
            'action': 'edit', 'id': self.jugador.id,
            'nombres': 'pedro', 'apellidos': 'vera',
            'fecha_nacimiento': '2013-03-03',
            'fecha_ingreso': self.jugador.fecha_ingreso.strftime('%Y-%m-%d'),
            'categoria': self.categoria.id, 'estado': 1,
            'cuidados': 'Tiene fascitis plantar: no hacerle saltar mucho.',
        })
        self.jugador.refresh_from_db()

        self.assertTrue(self.jugador.tiene_cuidados())
        self.assertIn('fascitis', self.jugador.cuidados)

    def test_sale_marcado_en_la_lista_de_asistencia(self):
        self.jugador.cuidados = 'asma'
        self.jugador.save()

        self.client.force_login(self.admin)
        respuesta = self.client.get(
            '/sistema/adm_asistencia?categoria=%s' % self.categoria.id)
        self.assertContains(respuesta, 'cuidado')


class AjusteDelValorDelMesTest(BaseFisico):
    """Lo comun es que pague lo mismo, pero un mes puede salir distinto."""

    def setUp(self):
        self.mensualidad = Mensualidad.objects.create(
            jugador=self.jugador, mes=9, anio=2026, valor=Decimal('25.00'),
            valor_completo=Decimal('25.00'), fecha_vencimiento=date(2026, 9, 10),
            periodo_inicio=date(2026, 9, 10), periodo_fin=date(2026, 10, 9)
        )
        self.client.force_login(self.admin)

    def cobrar(self, **extra):
        datos = {'action': 'pagar', 'id': self.mensualidad.id, 'estado': 1}
        datos.update(extra)
        return self.client.post('/sistema/adm_mensualidad', datos)

    def test_se_puede_cobrar_otro_valor_ese_mes(self):
        respuesta = self.cobrar(valor_completo='30.00')
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.valor_completo, Decimal('30.00'))
        self.assertEqual(self.mensualidad.valor, Decimal('30.00'))

    def test_el_valor_nuevo_manda_en_el_prorrateo(self):
        # 30 dias de periodo, 3 que no viene: paga 27/30 de 30 dolares.
        self.cobrar(valor_completo='30.00', dias_ausente=3, motivo_ajuste='viaje')

        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.valor, Decimal('27.00'))

    def test_dejarlo_vacio_no_cambia_lo_que_costaba(self):
        self.cobrar()
        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.valor_completo, Decimal('25.00'))

    def test_no_acepta_un_valor_negativo(self):
        respuesta = self.cobrar(valor_completo='-5')
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')

    def test_el_valor_no_cambia_el_de_los_demas_meses(self):
        otra = Mensualidad.objects.create(
            jugador=self.jugador, mes=10, anio=2026, valor=Decimal('25.00'),
            valor_completo=Decimal('25.00'), fecha_vencimiento=date(2026, 10, 10),
            periodo_inicio=date(2026, 10, 10), periodo_fin=date(2026, 11, 9)
        )
        self.cobrar(valor_completo='30.00')

        otra.refresh_from_db()
        self.assertEqual(otra.valor, Decimal('25.00'))

    def test_se_puede_cobrar_y_pagar_de_una(self):
        self.cobrar(valor_completo='30.00', estado=MENSUALIDAD_PAGADO,
                    forma_pago=PAGO_EFECTIVO, fecha_pago=HOY.strftime('%Y-%m-%d'))
        self.mensualidad.refresh_from_db()

        self.assertTrue(self.mensualidad.esta_pagada())
        self.assertEqual(self.mensualidad.valor, Decimal('30.00'))


class AbrirElSiguienteMesTest(BaseFisico):
    """Un clic y queda abierto el mes que sigue de ese jugador."""

    def setUp(self):
        self.client.force_login(self.admin)

    def abrir(self, jugador=None):
        return self.client.post('/sistema/adm_mensualidad', {
            'action': 'siguiente', 'id': (jugador or self.jugador).id,
        })

    def test_abre_el_primero_desde_su_ingreso(self):
        respuesta = self.abrir()
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        mensualidad = Mensualidad.objects.get()
        self.assertEqual(mensualidad.periodo_inicio, self.jugador.fecha_ingreso)
        self.assertEqual(mensualidad.valor, Decimal('25.00'))

    def test_el_siguiente_arranca_donde_termino_el_anterior(self):
        self.abrir()
        primera = Mensualidad.objects.get()

        self.abrir()
        segunda = Mensualidad.objects.exclude(pk=primera.pk).get()
        self.assertEqual(segunda.periodo_inicio, primera.periodo_fin + timedelta(days=1))

    def test_no_repite_un_mes_ya_abierto(self):
        self.abrir()
        mensualidad = Mensualidad.objects.get()

        # Se borra el segundo para que el proximo periodo vuelva a ser el mismo.
        respuesta = self.client.post('/sistema/adm_mensualidad', {
            'action': 'siguiente', 'id': self.jugador.id,
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertEqual(Mensualidad.objects.filter(periodo_inicio=mensualidad.periodo_inicio).count(), 1)

    def test_el_modal_dice_que_periodo_se_va_a_abrir(self):
        respuesta = self.client.get(
            '/sistema/adm_mensualidad?action=siguiente&id=%s' % self.jugador.id)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['proximo'][0], self.jugador.fecha_ingreso)
        self.assertEqual(respuesta.context['valor'], Decimal('25.00'))

    def test_el_entrenador_no_puede_abrir_meses(self):
        self.client.force_login(self.usuario_entrenador)
        self.abrir()
        self.assertEqual(Mensualidad.objects.count(), 0)


class CobroRapidoTest(BaseFisico):
    """Llega, paga, listo. Sin tocar fechas ni valores."""

    def setUp(self):
        self.mensualidad = Mensualidad.objects.create(
            jugador=self.jugador, mes=9, anio=2026, valor=Decimal('25.00'),
            valor_completo=Decimal('25.00'), fecha_vencimiento=date(2026, 9, 10),
            periodo_inicio=date(2026, 9, 10), periodo_fin=date(2026, 10, 9)
        )
        self.client.force_login(self.admin)

    def cobrar(self, **extra):
        datos = {'action': 'cobrar', 'id': self.mensualidad.id, 'forma_pago': PAGO_EFECTIVO}
        datos.update(extra)
        return self.client.post('/sistema/adm_mensualidad', datos)

    def test_con_la_forma_de_pago_basta(self):
        respuesta = self.cobrar()
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        self.mensualidad.refresh_from_db()
        self.assertTrue(self.mensualidad.esta_pagada())
        self.assertEqual(self.mensualidad.fecha_pago, HOY)
        self.assertEqual(self.mensualidad.valor, Decimal('25.00'))

    def test_no_cambia_el_periodo_ni_el_valor(self):
        self.cobrar()
        self.mensualidad.refresh_from_db()

        self.assertEqual(self.mensualidad.periodo_inicio, date(2026, 9, 10))
        self.assertEqual(self.mensualidad.periodo_fin, date(2026, 10, 9))
        self.assertEqual(self.mensualidad.valor_completo, Decimal('25.00'))

    def test_exige_decir_como_pago(self):
        respuesta = self.cobrar(forma_pago='')
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')

        self.mensualidad.refresh_from_db()
        self.assertFalse(self.mensualidad.esta_pagada())

    def test_se_puede_cobrar_con_otra_fecha(self):
        ayer = HOY - timedelta(days=1)
        self.cobrar(fecha_pago=ayer.strftime('%Y-%m-%d'), comprobante='rec-12')

        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.fecha_pago, ayer)
        self.assertEqual(self.mensualidad.comprobante, 'REC-12')

    def test_no_acepta_una_fecha_futura(self):
        respuesta = self.cobrar(fecha_pago=(HOY + timedelta(days=1)).strftime('%Y-%m-%d'))
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')

    def test_no_deja_cobrar_dos_veces(self):
        self.cobrar()
        respuesta = self.cobrar()
        datos = json.loads(respuesta.content)

        self.assertEqual(datos['result'], 'bad')
        self.assertIn('ya estaba pagada', datos['mensaje'])

    def test_el_modal_de_cobro_solo_pide_lo_del_pago(self):
        respuesta = self.client.get(
            '/sistema/adm_mensualidad?action=cobrar&id=%s' % self.mensualidad.id)

        campos = list(respuesta.context['form'].fields)
        self.assertEqual(campos, ['forma_pago', 'fecha_pago', 'comprobante'])

    def test_el_de_editar_sigue_trayendo_todo(self):
        respuesta = self.client.get(
            '/sistema/adm_mensualidad?action=pagar&id=%s' % self.mensualidad.id)

        campos = list(respuesta.context['form'].fields)
        self.assertIn('periodo_inicio', campos)
        self.assertIn('valor_completo', campos)
        self.assertIn('dias_ausente', campos)

    def test_el_entrenador_no_cobra(self):
        self.client.force_login(self.usuario_entrenador)
        self.cobrar()

        self.mensualidad.refresh_from_db()
        self.assertFalse(self.mensualidad.esta_pagada())
