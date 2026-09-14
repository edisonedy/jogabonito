# coding=utf-8
"""Pruebas del cobro que se genera solo.

La regla del negocio: el mes de cada jugador arranca el dia en que ingreso y,
cuando se termina, el sistema abre el siguiente al dia siguiente. Se corta si
el jugador se retira o si le apagan el interruptor.
"""
import json
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase

from jogabonito.cobros import poner_al_dia, poner_al_dia_jugador, proximos_cobros
from jogabonito.models import (
    JUGADOR_RETIRADO, MENSUALIDAD_PAGADO, ROL_ENTRENADOR, Categoria, Entrenador, Jugador,
    Mensualidad, PerfilUsuario,
)

CLAVE = 'clave-de-prueba-2026'
HOY = date.today()


class BaseCobro(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('cargar_base', '--admin-clave', CLAVE, verbosity=0)
        cls.admin = User.objects.get(username='admin')

        cls.usuario_entrenador = User.objects.create_user('entrenador9', password=CLAVE)
        cls.usuario_entrenador.groups.add(Group.objects.get(name='ENTRENADOR'))
        PerfilUsuario.objects.create(usuario=cls.usuario_entrenador, rol=ROL_ENTRENADOR)
        Entrenador.objects.create(nombres='ana', apellidos='paz', telefono='0999999999',
                                  usuario=cls.usuario_entrenador)

        cls.categoria = Categoria.objects.create(
            nombre='tarde', dias='2,4', hora_inicio=time(15, 0), hora_fin=time(17, 0),
            valor_mensual=Decimal('25.00')
        )

    def crear_jugador(self, nombre, dias_atras, **extra):
        datos = {
            'nombres': nombre,
            'apellidos': 'prueba',
            'fecha_nacimiento': date(2014, 4, 4),
            'categoria': self.categoria,
            'fecha_ingreso': HOY - timedelta(days=dias_atras),
        }
        datos.update(extra)
        return Jugador.objects.create(**datos)


class CadaMesSeAbreSoloTest(BaseCobro):
    def test_el_primer_mes_arranca_el_dia_que_ingreso(self):
        jugador = self.crear_jugador('primero', 3)
        poner_al_dia_jugador(jugador)

        mensualidad = jugador.mensualidades.get()
        self.assertEqual(mensualidad.periodo_inicio, jugador.fecha_ingreso)
        self.assertEqual(mensualidad.fecha_vencimiento, jugador.fecha_ingreso)
        self.assertEqual(mensualidad.valor, Decimal('25.00'))

    def test_el_siguiente_arranca_al_dia_siguiente_del_anterior(self):
        jugador = self.crear_jugador('encadenado', 70)
        poner_al_dia_jugador(jugador)

        meses = list(jugador.mensualidades.order_by('anio', 'mes'))
        self.assertGreaterEqual(len(meses), 2)
        for anterior, siguiente in zip(meses, meses[1:]):
            self.assertEqual(siguiente.periodo_inicio, anterior.periodo_fin + timedelta(days=1))

    def test_no_se_adelanta_a_lo_que_todavia_no_toca(self):
        jugador = self.crear_jugador('adelantado', 5)
        poner_al_dia_jugador(jugador)

        self.assertEqual(jugador.mensualidades.count(), 1)
        ultima = jugador.ultima_mensualidad()
        self.assertGreater(ultima.periodo_fin, HOY)

    def test_aunque_no_pague_se_le_abre_el_mes_siguiente(self):
        jugador = self.crear_jugador('moroso', 45)
        poner_al_dia_jugador(jugador)

        self.assertEqual(jugador.mensualidades_pendientes().count(), 2)
        self.assertEqual(jugador.meses_que_debe(), 2)

    def test_correrlo_dos_veces_no_duplica(self):
        jugador = self.crear_jugador('repetido', 40)
        poner_al_dia_jugador(jugador)
        cuantas = jugador.mensualidades.count()

        poner_al_dia_jugador(jugador)
        self.assertEqual(jugador.mensualidades.count(), cuantas)

    def test_respeta_las_fechas_corregidas_a_mano(self):
        jugador = self.crear_jugador('corregido', 40)
        poner_al_dia_jugador(jugador)

        primera = jugador.mensualidades.order_by('anio', 'mes').first()
        primera.periodo_fin = primera.periodo_inicio + timedelta(days=9)
        primera.save()

        jugador.mensualidades.exclude(pk=primera.pk).delete()
        poner_al_dia_jugador(jugador)

        siguiente = jugador.mensualidades.exclude(pk=primera.pk).order_by('anio', 'mes').first()
        self.assertEqual(siguiente.periodo_inicio, primera.periodo_fin + timedelta(days=1))


class CuandoDejaDeCobrarseTest(BaseCobro):
    def test_con_el_interruptor_apagado_no_se_abre_nada(self):
        jugador = self.crear_jugador('pausado', 45, cobro_activo=False)
        poner_al_dia_jugador(jugador)
        self.assertEqual(jugador.mensualidades.count(), 0)

    def test_al_retirado_tampoco(self):
        jugador = self.crear_jugador('retirado', 45, estado=JUGADOR_RETIRADO)
        poner_al_dia_jugador(jugador)
        self.assertEqual(jugador.mensualidades.count(), 0)

    def test_al_prenderlo_de_nuevo_se_pone_al_dia(self):
        jugador = self.crear_jugador('vuelve', 70, cobro_activo=False)
        poner_al_dia_jugador(jugador)
        self.assertEqual(jugador.mensualidades.count(), 0)

        jugador.cobro_activo = True
        jugador.save()
        poner_al_dia_jugador(jugador)

        meses = list(jugador.mensualidades.order_by('periodo_inicio'))
        self.assertGreaterEqual(len(meses), 2)
        self.assertEqual(meses[0].periodo_inicio, jugador.fecha_ingreso)
        self.assertLessEqual(meses[-1].periodo_inicio, HOY)


class PonerAlDiaATodosTest(BaseCobro):
    def setUp(self):
        self.client.force_login(self.admin)
        self.al_dia = self.crear_jugador('aldia', 3)
        self.atrasado = self.crear_jugador('atrasado', 40)
        self.pausado = self.crear_jugador('quieto', 40, cobro_activo=False)

    def test_cuenta_cuantas_abrio(self):
        resultado = poner_al_dia()
        self.assertEqual(resultado['jugadores'], 2)
        self.assertEqual(resultado['creadas'], 3)  # 1 del que entro ayer + 2 del atrasado
        self.assertEqual(self.pausado.mensualidades.count(), 0)

    def test_al_abrir_el_modulo_se_pone_al_dia_solo(self):
        self.client.get('/sistema/adm_mensualidad')
        self.assertTrue(self.al_dia.mensualidades.exists())
        self.assertTrue(self.atrasado.mensualidades.exists())
        self.assertFalse(self.pausado.mensualidades.exists())

    def test_el_boton_de_revisar_responde(self):
        respuesta = self.client.post('/sistema/adm_mensualidad', {'action': 'aldia'})
        datos = json.loads(respuesta.content)
        self.assertEqual(datos['result'], 'ok')
        self.assertIn('Se abrieron', datos['mensaje'])

    def test_el_comando_hace_lo_mismo(self):
        call_command('poner_al_dia', verbosity=0)
        self.assertTrue(self.atrasado.mensualidades.exists())

    def test_la_pantalla_de_control_muestra_a_quien_le_toca(self):
        poner_al_dia()
        filas = {fila['jugador'].id: fila for fila in proximos_cobros()}

        self.assertIn(self.al_dia.id, filas)
        self.assertNotIn(self.pausado.id, filas)
        self.assertFalse(filas[self.al_dia.id]['ya_toca'])
        self.assertGreater(filas[self.al_dia.id]['inicio'], HOY)

    def test_el_entrenador_no_puede_ponerlo_al_dia(self):
        self.client.force_login(self.usuario_entrenador)
        self.client.post('/sistema/adm_mensualidad', {'action': 'aldia'})
        self.assertFalse(self.atrasado.mensualidades.exists())


class InterruptorDesdeLaPantallaTest(BaseCobro):
    def setUp(self):
        self.client.force_login(self.admin)
        self.jugador = self.crear_jugador('interruptor', 40)

    def test_se_apaga_desde_el_modal_de_precio(self):
        respuesta = self.client.post('/sistema/adm_mensualidad', {
            'action': 'precio', 'id': self.jugador.id, 'descuento': '0',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        self.jugador.refresh_from_db()
        self.assertFalse(self.jugador.cobro_activo)
        self.assertFalse(self.jugador.se_le_cobra())

    def test_se_prende_marcando_la_casilla(self):
        self.jugador.cobro_activo = False
        self.jugador.save()

        self.client.post('/sistema/adm_mensualidad', {
            'action': 'precio', 'id': self.jugador.id, 'descuento': '0',
            'cobro_activo': 'on',
        })
        self.jugador.refresh_from_db()
        self.assertTrue(self.jugador.cobro_activo)

    def test_el_mes_ya_pagado_no_se_toca_al_ponerse_al_dia(self):
        poner_al_dia_jugador(self.jugador)
        primera = self.jugador.mensualidades.order_by('anio', 'mes').first()
        primera.estado = MENSUALIDAD_PAGADO
        primera.fecha_pago = HOY
        primera.save()

        poner_al_dia_jugador(self.jugador)
        primera.refresh_from_db()
        self.assertEqual(primera.estado, MENSUALIDAD_PAGADO)


class EstadoDeCuentaTest(BaseCobro):
    """La continuidad: hasta cuando esta cubierto y desde cuando debe."""

    def setUp(self):
        self.jugador = self.crear_jugador('cuenta', 70)
        poner_al_dia_jugador(self.jugador)
        self.meses = list(self.jugador.mensualidades_en_orden())

    def pagar(self, mensualidad):
        mensualidad.estado = MENSUALIDAD_PAGADO
        mensualidad.fecha_pago = HOY
        mensualidad.save()

    def test_el_mes_pertenece_al_mes_en_que_arranca(self):
        mensualidad = Mensualidad.objects.create(
            jugador=self.jugador, mes=1, anio=2000, valor=Decimal('25.00'),
            fecha_vencimiento=date(2026, 9, 23),
            periodo_inicio=date(2026, 9, 23), periodo_fin=date(2026, 10, 22)
        )
        self.assertEqual(mensualidad.mes, 9)
        self.assertEqual(mensualidad.anio, 2026)
        self.assertEqual(mensualidad.periodo(), 'Septiembre 2026')

    def test_debiendo_todo_dice_desde_cuando(self):
        texto = self.jugador.estado_de_cuenta()
        self.assertIn('Debe', texto)
        self.assertIn(self.meses[0].periodo_inicio.strftime('%d/%m/%Y'), texto)
        self.assertIsNone(self.jugador.cubierto_hasta())

    def test_pagando_en_orden_avanza_la_cobertura(self):
        self.pagar(self.meses[0])
        self.assertEqual(self.jugador.cubierto_hasta(), self.meses[0].periodo_fin)
        self.assertEqual(self.jugador.debe_desde(), self.meses[1].periodo_inicio)

        self.pagar(self.meses[1])
        self.assertEqual(self.jugador.cubierto_hasta(), self.meses[1].periodo_fin)

    def test_un_mes_saltado_corta_la_cobertura(self):
        self.pagar(self.meses[1])
        self.assertIsNone(self.jugador.cubierto_hasta())
        self.assertEqual(self.jugador.debe_desde(), self.meses[0].periodo_inicio)

    def test_al_dia_dice_hasta_cuando_esta_cubierto(self):
        for mensualidad in self.meses:
            self.pagar(mensualidad)

        texto = self.jugador.estado_de_cuenta()
        self.assertIn('Al dia', texto)
        self.assertIn(self.meses[-1].periodo_fin.strftime('%d/%m/%Y'), texto)

    def test_el_que_no_tiene_nada_lo_dice(self):
        nuevo = self.crear_jugador('sinnada', 2, cobro_activo=False)
        self.assertEqual(nuevo.estado_de_cuenta(), 'Todavia no tiene mensualidades.')


class ListaDeJugadoresConDeudaTest(BaseCobro):
    """Desde la lista de jugadores se ve quien debe y se le cobra el mes."""

    def setUp(self):
        self.client.force_login(self.admin)
        self.debe = self.crear_jugador('debe', 70)
        self.al_dia = self.crear_jugador('aldia', 70)
        poner_al_dia()

        for mensualidad in self.al_dia.mensualidades.all():
            mensualidad.estado = MENSUALIDAD_PAGADO
            mensualidad.fecha_pago = HOY
            mensualidad.save()

    def jugadores_de(self, url):
        return {j.id: j for j in self.client.get(url).context['jugadores']}

    def test_la_lista_dice_cuanto_debe_cada_uno(self):
        jugadores = self.jugadores_de('/sistema/adm_jugador')

        self.assertGreater(jugadores[self.debe.id].meses_pendientes, 0)
        self.assertEqual(jugadores[self.debe.id].deuda, self.debe.total_que_debe())
        self.assertEqual(jugadores[self.al_dia.id].meses_pendientes, 0)

    def test_se_puede_ver_solo_a_los_que_deben(self):
        jugadores = self.jugadores_de('/sistema/adm_jugador?cuenta=debe')
        self.assertIn(self.debe.id, jugadores)
        self.assertNotIn(self.al_dia.id, jugadores)

    def test_se_puede_ver_solo_a_los_que_estan_al_dia(self):
        jugadores = self.jugadores_de('/sistema/adm_jugador?cuenta=aldia')
        self.assertIn(self.al_dia.id, jugadores)
        self.assertNotIn(self.debe.id, jugadores)

    def test_cuenta_cuantos_deben(self):
        respuesta = self.client.get('/sistema/adm_jugador')
        self.assertEqual(respuesta.context['cuantos_deben'], 1)

    def test_el_entrenador_ni_siquiera_entra_a_la_lista(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/adm_jugador')
        self.assertEqual(respuesta.status_code, 302)
