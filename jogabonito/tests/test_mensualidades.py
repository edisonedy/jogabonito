# coding=utf-8
"""Pruebas de mensualidades: precios, descuentos, atrasos y afinidad de posicion."""
import json
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from jogabonito.adm_mensualidad import fecha_de_vencimiento
from jogabonito.models import (
    AREA_FISICA, AREA_TECNICA, MEDIDA_ESCALA, MENSUALIDAD_PAGADO, MENSUALIDAD_PENDIENTE,
    PAGO_EFECTIVO, ROL_ENTRENADOR, Categoria, Entrenador, Evaluacion, Indicador, Jugador,
    Medicion, Mensualidad, PerfilUsuario, Posicion,
)

CLAVE = 'clave-de-prueba-2026'
HOY = date.today()


class BaseMensualidad(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('cargar_base', '--admin-clave', CLAVE, verbosity=0)
        cls.admin = User.objects.get(username='admin')

        cls.usuario_entrenador = User.objects.create_user('entrenador1', password=CLAVE)
        cls.usuario_entrenador.groups.add(Group.objects.get(name='ENTRENADOR'))
        PerfilUsuario.objects.create(usuario=cls.usuario_entrenador, rol=ROL_ENTRENADOR)
        Entrenador.objects.create(nombres='luis', apellidos='mora', telefono='0999999999',
                                  usuario=cls.usuario_entrenador)

        cls.categoria = Categoria.objects.create(
            nombre='manana', dias='1,3,5', hora_inicio=time(7, 0), hora_fin=time(9, 0),
            valor_mensual=Decimal('25.00')
        )
        cls.jugador = Jugador.objects.create(
            nombres='pedro', apellidos='vera', fecha_nacimiento=date(2013, 3, 3),
            categoria=cls.categoria
        )
        cls.hermano = Jugador.objects.create(
            nombres='luis', apellidos='vera', fecha_nacimiento=date(2015, 5, 5),
            categoria=cls.categoria
        )
        cls.retirado = Jugador.objects.create(
            nombres='raul', apellidos='cruz', fecha_nacimiento=date(2013, 7, 7),
            categoria=cls.categoria, estado=3
        )


class PrecioDelJugadorTest(BaseMensualidad):
    def test_todos_pagan_lo_que_cuesta_su_grupo(self):
        self.assertEqual(self.jugador.precio_base(), Decimal('25.00'))
        self.assertEqual(self.jugador.valor_mensual_vigente(), Decimal('25.00'))

    def test_el_descuento_se_resta(self):
        self.jugador.descuento = Decimal('20.00')
        self.jugador.motivo_descuento = 'hermano en la academia'
        self.jugador.save()

        self.assertEqual(self.jugador.valor_descuento(), Decimal('5.00'))
        self.assertEqual(self.jugador.valor_mensual_vigente(), Decimal('20.00'))

    def test_si_sube_el_precio_del_grupo_les_sube_a_todos(self):
        self.categoria.valor_mensual = Decimal('35.00')
        self.categoria.save()

        self.jugador.refresh_from_db()
        self.hermano.refresh_from_db()
        self.assertEqual(self.jugador.valor_mensual_vigente(), Decimal('35.00'))
        self.assertEqual(self.hermano.valor_mensual_vigente(), Decimal('35.00'))

    def test_al_que_tiene_descuento_le_sube_proporcional(self):
        self.jugador.descuento = Decimal('50.00')
        self.jugador.motivo_descuento = 'beca'
        self.jugador.save()

        self.categoria.valor_mensual = Decimal('30.00')
        self.categoria.save()
        self.jugador.refresh_from_db()
        self.assertEqual(self.jugador.valor_mensual_vigente(), Decimal('15.00'))

    def test_lo_ya_generado_no_cambia_aunque_suba_el_grupo(self):
        """El valor se copia al generar: subir precios no toca el pasado."""
        self.client.force_login(self.admin)
        self.client.post('/sistema/adm_mensualidad', {'action': 'generar', 'mes': 9, 'anio': 2026})

        self.categoria.valor_mensual = Decimal('40.00')
        self.categoria.save()

        mensualidad = Mensualidad.objects.get(jugador=self.jugador, mes=9, anio=2026)
        self.assertEqual(mensualidad.valor, Decimal('25.00'))

    def test_un_descuento_del_cien_deja_el_mes_en_cero(self):
        self.jugador.descuento = Decimal('100.00')
        self.jugador.motivo_descuento = 'beca completa'
        self.jugador.save()
        self.assertEqual(self.jugador.valor_mensual_vigente(), Decimal('0.00'))

    def test_explica_de_donde_sale_el_precio(self):
        self.assertIn('valor de MANANA', self.jugador.explicacion_precio())

        self.jugador.descuento = Decimal('10.00')
        self.jugador.motivo_descuento = 'convenio'
        self.jugador.save()

        texto = self.jugador.explicacion_precio()
        self.assertIn('valor de MANANA', texto)
        self.assertIn('10% de descuento', texto)
        self.assertIn('convenio', texto)

    def test_el_formulario_exige_el_motivo_del_descuento(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_mensualidad', {
            'action': 'precio', 'id': self.jugador.id, 'descuento': '20', 'motivo_descuento': '',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')

    def test_el_formulario_rechaza_un_descuento_mayor_a_cien(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_mensualidad', {
            'action': 'precio', 'id': self.jugador.id, 'descuento': '150', 'motivo_descuento': 'x',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')


class GenerarMensualidadesTest(BaseMensualidad):
    def setUp(self):
        self.client.force_login(self.admin)

    def test_genera_una_por_jugador_activo(self):
        respuesta = self.client.post('/sistema/adm_mensualidad', {
            'action': 'generar', 'mes': 9, 'anio': 2026,
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        # El retirado no entra.
        self.assertEqual(Mensualidad.objects.count(), 2)
        self.assertFalse(Mensualidad.objects.filter(jugador=self.retirado).exists())

    def test_no_duplica_si_se_corre_dos_veces(self):
        self.client.post('/sistema/adm_mensualidad', {'action': 'generar', 'mes': 9, 'anio': 2026})
        self.client.post('/sistema/adm_mensualidad', {'action': 'generar', 'mes': 9, 'anio': 2026})
        self.assertEqual(Mensualidad.objects.filter(mes=9, anio=2026).count(), 2)

    def test_la_base_impide_repetir_el_mismo_periodo(self):
        Mensualidad.objects.create(jugador=self.jugador, mes=9, anio=2026, valor=Decimal('25.00'),
                                   fecha_vencimiento=date(2026, 9, 10),
                                   periodo_inicio=date(2026, 9, 10), periodo_fin=date(2026, 10, 9))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Mensualidad.objects.create(jugador=self.jugador, mes=9, anio=2026,
                                           valor=Decimal('25.00'),
                                           fecha_vencimiento=date(2026, 9, 10),
                                           periodo_inicio=date(2026, 9, 10),
                                           periodo_fin=date(2026, 10, 9))

    def test_si_le_corrigen_las_fechas_puede_haber_dos_en_el_mismo_mes(self):
        """El que entra a fin de mes puede tener un periodo corto y otro normal."""
        Mensualidad.objects.create(jugador=self.jugador, mes=9, anio=2026, valor=Decimal('10.00'),
                                   fecha_vencimiento=date(2026, 9, 1),
                                   periodo_inicio=date(2026, 9, 1), periodo_fin=date(2026, 9, 9))
        Mensualidad.objects.create(jugador=self.jugador, mes=9, anio=2026, valor=Decimal('25.00'),
                                   fecha_vencimiento=date(2026, 9, 10),
                                   periodo_inicio=date(2026, 9, 10), periodo_fin=date(2026, 10, 9))

        self.assertEqual(Mensualidad.objects.filter(jugador=self.jugador, mes=9, anio=2026).count(), 2)

    def test_copia_el_valor_del_momento(self):
        self.jugador.descuento = Decimal('20.00')
        self.jugador.motivo_descuento = 'hermano'
        self.jugador.save()

        self.client.post('/sistema/adm_mensualidad', {'action': 'generar', 'mes': 9, 'anio': 2026})
        mensualidad = Mensualidad.objects.get(jugador=self.jugador, mes=9)
        self.assertEqual(mensualidad.valor, Decimal('20.00'))
        self.assertEqual(mensualidad.descuento_aplicado, Decimal('20.00'))

        # Si despues sube el grupo, la mensualidad vieja no cambia.
        self.categoria.valor_mensual = Decimal('40.00')
        self.categoria.save()
        mensualidad.refresh_from_db()
        self.assertEqual(mensualidad.valor, Decimal('20.00'))

    def test_puede_generar_solo_un_grupo(self):
        otra = Categoria.objects.create(nombre='tarde', hora_inicio=time(15, 0), hora_fin=time(17, 0),
                                        valor_mensual=Decimal('25.00'))
        Jugador.objects.create(nombres='ana', apellidos='pozo', fecha_nacimiento=date(2013, 1, 1),
                               categoria=otra)

        self.client.post('/sistema/adm_mensualidad', {
            'action': 'generar', 'mes': 9, 'anio': 2026, 'categoria': otra.id,
        })
        self.assertEqual(Mensualidad.objects.count(), 1)
        self.assertEqual(Mensualidad.objects.first().jugador.categoria, otra)

    def test_el_vencimiento_cae_el_dia_diez(self):
        self.assertEqual(fecha_de_vencimiento(9, 2026), date(2026, 9, 10))
        # Febrero corto no rompe nada.
        self.assertEqual(fecha_de_vencimiento(2, 2026, dia=31), date(2026, 2, 28))


class AtrasosTest(BaseMensualidad):
    def crear(self, mes, anio, vencimiento, estado=MENSUALIDAD_PENDIENTE):
        return Mensualidad.objects.create(
            jugador=self.jugador, mes=mes, anio=anio, valor=Decimal('25.00'),
            fecha_vencimiento=vencimiento, estado=estado
        )

    def test_una_pendiente_vencida_esta_atrasada(self):
        mensualidad = self.crear(1, 2026, HOY - timedelta(days=5))
        self.assertTrue(mensualidad.esta_atrasada())
        self.assertEqual(mensualidad.dias_de_atraso(), 5)
        self.assertEqual(mensualidad.estado_visible(), 'ATRASADO')
        self.assertEqual(mensualidad.color(), 'danger')

    def test_una_pendiente_que_no_vence_no_esta_atrasada(self):
        mensualidad = self.crear(1, 2026, HOY + timedelta(days=5))
        self.assertFalse(mensualidad.esta_atrasada())
        self.assertEqual(mensualidad.estado_visible(), 'PENDIENTE')

    def test_una_pagada_nunca_esta_atrasada(self):
        mensualidad = self.crear(1, 2026, HOY - timedelta(days=30), estado=MENSUALIDAD_PAGADO)
        self.assertFalse(mensualidad.esta_atrasada())
        self.assertEqual(mensualidad.dias_de_atraso(), 0)

    def test_cuenta_cuantos_meses_debe_y_cuanto(self):
        self.crear(1, 2026, HOY - timedelta(days=40))
        self.crear(2, 2026, HOY - timedelta(days=10))
        self.crear(3, 2026, HOY + timedelta(days=20))
        self.crear(4, 2026, HOY - timedelta(days=5), estado=MENSUALIDAD_PAGADO)

        self.assertEqual(self.jugador.meses_que_debe(), 3)
        self.assertEqual(self.jugador.total_que_debe(), Decimal('75.00'))
        self.assertEqual(len(self.jugador.mensualidades_atrasadas()), 2)
        self.assertEqual(self.jugador.dias_de_atraso(), 40)
        self.assertFalse(self.jugador.esta_al_dia())

    def test_sin_deudas_esta_al_dia(self):
        self.crear(1, 2026, HOY - timedelta(days=10), estado=MENSUALIDAD_PAGADO)
        self.assertTrue(self.jugador.esta_al_dia())
        self.assertEqual(self.jugador.total_que_debe(), Decimal('0.00'))

    def test_la_pantalla_de_deudores_los_ordena_por_atraso(self):
        self.crear(1, 2026, HOY - timedelta(days=40))
        Mensualidad.objects.create(jugador=self.hermano, mes=1, anio=2026, valor=Decimal('25.00'),
                                   fecha_vencimiento=HOY - timedelta(days=2))

        self.client.force_login(self.admin)
        deudores = self.client.get('/sistema/adm_mensualidad?action=deudores').context['deudores']

        self.assertEqual(len(deudores), 2)
        self.assertEqual(deudores[0]['jugador'], self.jugador)
        self.assertEqual(deudores[0]['dias'], 40)


class CobroTest(BaseMensualidad):
    def setUp(self):
        self.mensualidad = Mensualidad.objects.create(
            jugador=self.jugador, mes=9, anio=2026, valor=Decimal('25.00'),
            fecha_vencimiento=HOY - timedelta(days=3)
        )
        self.client.force_login(self.admin)

    def test_registra_el_pago(self):
        respuesta = self.client.post('/sistema/adm_mensualidad', {
            'action': 'pagar', 'id': self.mensualidad.id, 'estado': MENSUALIDAD_PAGADO,
            'valor': '25.00', 'forma_pago': PAGO_EFECTIVO, 'comprobante': 'rec-001',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        self.mensualidad.refresh_from_db()
        self.assertTrue(self.mensualidad.esta_pagada())
        self.assertEqual(self.mensualidad.fecha_pago, HOY)
        self.assertEqual(self.mensualidad.usuario_modificacion, self.admin)

    def test_no_deja_marcar_pagado_sin_decir_como(self):
        respuesta = self.client.post('/sistema/adm_mensualidad', {
            'action': 'pagar', 'id': self.mensualidad.id, 'estado': MENSUALIDAD_PAGADO,
            'valor': '25.00',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.mensualidad.refresh_from_db()
        self.assertFalse(self.mensualidad.esta_pagada())

    def test_no_acepta_una_fecha_de_pago_futura(self):
        respuesta = self.client.post('/sistema/adm_mensualidad', {
            'action': 'pagar', 'id': self.mensualidad.id, 'estado': MENSUALIDAD_PAGADO,
            'valor': '25.00', 'forma_pago': PAGO_EFECTIVO,
            'fecha_pago': (HOY + timedelta(days=2)).strftime('%Y-%m-%d'),
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')

    def test_no_borra_una_mensualidad_pagada(self):
        self.mensualidad.estado = MENSUALIDAD_PAGADO
        self.mensualidad.save()

        respuesta = self.client.post('/sistema/adm_mensualidad',
                                     {'action': 'delete', 'id': self.mensualidad.id})
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertTrue(Mensualidad.objects.filter(pk=self.mensualidad.pk).exists())

    def test_el_entrenador_no_entra_al_modulo(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/adm_mensualidad')
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], '/sistema/')

    def test_el_resumen_del_mes_suma_bien(self):
        Mensualidad.objects.create(jugador=self.hermano, mes=9, anio=2026, valor=Decimal('20.00'),
                                   fecha_vencimiento=HOY, estado=MENSUALIDAD_PAGADO)
        respuesta = self.client.get('/sistema/adm_mensualidad?mes=9&anio=2026')
        resumen = respuesta.context['resumen']

        self.assertEqual(resumen['cobrado'], Decimal('20.00'))
        self.assertEqual(resumen['por_cobrar'], Decimal('25.00'))
        self.assertEqual(resumen['atrasadas'], 1)


class AfinidadPosicionTest(BaseMensualidad):
    def setUp(self):
        self.control = Indicador.objects.create(
            nombre='control de prueba', area=AREA_TECNICA, tipo_medida=MEDIDA_ESCALA, orden=1
        )
        self.fuerza = Indicador.objects.create(
            nombre='fuerza de prueba', area=AREA_FISICA, tipo_medida=MEDIDA_ESCALA, orden=1
        )
        evaluacion = Evaluacion.objects.create(categoria=self.categoria, fecha=HOY, titulo='p1')
        evaluacion.indicadores.set([self.control, self.fuerza])

        # Muy bueno con el balon, flojo en lo fisico.
        Medicion.objects.create(evaluacion=evaluacion, jugador=self.jugador,
                                indicador=self.control, valor=Decimal('10'))
        Medicion.objects.create(evaluacion=evaluacion, jugador=self.jugador,
                                indicador=self.fuerza, valor=Decimal('2'))

    def test_sugiere_primero_los_puestos_que_piden_lo_que_el_tiene(self):
        afinidades = self.jugador.afinidad_posiciones()
        self.assertTrue(afinidades)

        mejor = afinidades[0]['posicion'].nombre
        peor = afinidades[-1]['posicion'].nombre
        # Tecnica alta y fisico bajo: el volante ofensivo le queda mejor que el arquero.
        self.assertIn(mejor, ('VOLANTE OFENSIVO', 'DELANTERO', 'VOLANTE MIXTO'))
        self.assertIn(peor, ('ARQUERO', 'DEFENSA CENTRAL'))

    def test_marca_cual_es_la_que_le_gusta(self):
        arquero = Posicion.objects.get(nombre='ARQUERO')
        self.jugador.posicion = arquero
        self.jugador.save()

        elegida = [a for a in self.jugador.afinidad_posiciones() if a['es_la_que_le_gusta']]
        self.assertEqual(len(elegida), 1)
        self.assertEqual(elegida[0]['posicion'], arquero)

    def test_sin_mediciones_no_sugiere_nada(self):
        self.assertEqual(self.hermano.afinidad_posiciones(), [])
        self.assertIsNone(self.hermano.posicion_sugerida())

    def test_los_pesos_de_la_posicion_se_pueden_cambiar(self):
        arquero = Posicion.objects.get(nombre='ARQUERO')
        self.assertEqual(arquero.peso_fisica, 3)
        self.assertIn('fisica x3', arquero.pesos_texto())


class CobroDesdeElIngresoTest(BaseMensualidad):
    def setUp(self):
        self.client.force_login(self.admin)

    def test_vence_el_mismo_dia_en_que_ingreso(self):
        self.jugador.fecha_ingreso = date(2026, 3, 22)
        self.jugador.save()
        self.assertEqual(self.jugador.dia_de_cobro(), 22)

        self.client.post('/sistema/adm_mensualidad', {'action': 'generar', 'mes': 9, 'anio': 2026})
        mensualidad = Mensualidad.objects.get(jugador=self.jugador, mes=9)
        self.assertEqual(mensualidad.fecha_vencimiento, date(2026, 9, 22))

    def test_el_dia_31_se_ajusta_en_los_meses_cortos(self):
        self.jugador.fecha_ingreso = date(2026, 1, 31)
        self.jugador.save()

        self.client.post('/sistema/adm_mensualidad', {'action': 'generar', 'mes': 2, 'anio': 2026})
        mensualidad = Mensualidad.objects.get(jugador=self.jugador, mes=2)
        self.assertEqual(mensualidad.fecha_vencimiento, date(2026, 2, 28))

    def test_no_cobra_meses_anteriores_al_ingreso(self):
        self.jugador.fecha_ingreso = date(2026, 6, 5)
        self.jugador.save()
        self.hermano.fecha_ingreso = date(2026, 1, 5)
        self.hermano.save()

        self.assertFalse(self.jugador.ya_estaba_en(3, 2026))
        self.assertTrue(self.jugador.ya_estaba_en(6, 2026))

        self.client.post('/sistema/adm_mensualidad', {'action': 'generar', 'mes': 3, 'anio': 2026})
        self.assertFalse(Mensualidad.objects.filter(jugador=self.jugador, mes=3).exists())
        self.assertTrue(Mensualidad.objects.filter(jugador=self.hermano, mes=3).exists())


class DiasQueNoVieneTest(BaseMensualidad):
    def setUp(self):
        # Periodo del 10 de septiembre al 9 de octubre: 30 dias.
        self.mensualidad = Mensualidad.objects.create(
            jugador=self.jugador, mes=9, anio=2026, valor=Decimal('30.00'),
            valor_completo=Decimal('30.00'), fecha_vencimiento=date(2026, 9, 10),
            periodo_inicio=date(2026, 9, 10), periodo_fin=date(2026, 10, 9)
        )
        self.client.force_login(self.admin)

    def test_sabe_cuantos_dias_cubre(self):
        self.assertEqual(self.mensualidad.dias_del_periodo(), 30)
        self.assertEqual(self.mensualidad.valor_por_dia(), Decimal('1.00'))

    def test_cobra_solo_los_dias_que_viene(self):
        self.mensualidad.dias_ausente = 7
        self.assertEqual(self.mensualidad.recalcular_por_ausencia(), Decimal('23.00'))
        self.assertEqual(self.mensualidad.dias_cobrados(), 23)

    def test_el_periodo_entero_fuera_no_cobra_nada(self):
        self.mensualidad.dias_ausente = 30
        self.assertEqual(self.mensualidad.recalcular_por_ausencia(), Decimal('0.00'))

    def test_se_registra_desde_el_cobro(self):
        respuesta = self.client.post('/sistema/adm_mensualidad', {
            'action': 'pagar', 'id': self.mensualidad.id, 'estado': MENSUALIDAD_PENDIENTE,
            'dias_ausente': 7, 'motivo_ajuste': 'viaje con la familia',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.valor, Decimal('23.00'))
        self.assertEqual(self.mensualidad.valor_completo, Decimal('30.00'))
        self.assertTrue(self.mensualidad.tiene_ajuste())
        self.assertIn('7 dias de 30', self.mensualidad.texto_ajuste())

    def test_exige_el_motivo(self):
        respuesta = self.client.post('/sistema/adm_mensualidad', {
            'action': 'pagar', 'id': self.mensualidad.id, 'estado': MENSUALIDAD_PENDIENTE,
            'dias_ausente': 5, 'motivo_ajuste': '',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.valor, Decimal('30.00'))

    def test_no_acepta_mas_dias_que_el_periodo(self):
        respuesta = self.client.post('/sistema/adm_mensualidad', {
            'action': 'pagar', 'id': self.mensualidad.id, 'estado': MENSUALIDAD_PENDIENTE,
            'dias_ausente': 45, 'motivo_ajuste': 'se va del pais',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')

    def test_volver_a_cero_devuelve_el_valor_completo(self):
        self.client.post('/sistema/adm_mensualidad', {
            'action': 'pagar', 'id': self.mensualidad.id, 'estado': MENSUALIDAD_PENDIENTE,
            'dias_ausente': 10, 'motivo_ajuste': 'viaje',
        })
        self.client.post('/sistema/adm_mensualidad', {
            'action': 'pagar', 'id': self.mensualidad.id, 'estado': MENSUALIDAD_PENDIENTE,
            'dias_ausente': 0, 'motivo_ajuste': '',
        })
        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.valor, Decimal('30.00'))


class RepresentanteDesdeElJugadorTest(BaseMensualidad):
    def setUp(self):
        self.client.force_login(self.admin)

    def test_crea_y_asigna_uno_nuevo(self):
        respuesta = self.client.post('/sistema/adm_jugador', {
            'action': 'representante', 'id': self.jugador.id,
            'nombres': 'maria', 'apellidos': 'lopez', 'telefono': '0991122334',
            'whatsapp': '593991122334', 'parentesco': 2,
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        self.jugador.refresh_from_db()
        self.assertIsNotNone(self.jugador.representante)
        self.assertEqual(self.jugador.representante.nombre_completo(), 'LOPEZ MARIA')

    def test_asigna_uno_que_ya_existe(self):
        from jogabonito.models import Representante
        existente = Representante.objects.create(nombres='juan', apellidos='paz', telefono='0987777777')

        self.client.post('/sistema/adm_jugador', {
            'action': 'representante', 'id': self.jugador.id, 'existente': existente.id,
        })
        self.jugador.refresh_from_db()
        self.assertEqual(self.jugador.representante, existente)

    def test_exige_telefono_al_crear_uno_nuevo(self):
        respuesta = self.client.post('/sistema/adm_jugador', {
            'action': 'representante', 'id': self.jugador.id,
            'nombres': 'sin', 'apellidos': 'telefono',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.jugador.refresh_from_db()
        self.assertIsNone(self.jugador.representante)

    def test_el_entrenador_no_puede_asignarlo(self):
        """Ya ni entra al modulo de jugadores: el representante es del admin."""
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.post('/sistema/adm_jugador', {
            'action': 'representante', 'id': self.jugador.id,
            'nombres': 'pirata', 'apellidos': 'pirata', 'telefono': '0999999999',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.jugador.refresh_from_db()
        self.assertIsNone(self.jugador.representante)


class PeriodosSegunCuandoEntroCadaUnoTest(BaseMensualidad):
    """Cada jugador entra un dia distinto, asi que cada uno tiene su propio periodo."""

    def setUp(self):
        self.client.force_login(self.admin)
        self.categoria.valor_mensual = Decimal('30.00')
        self.categoria.save()

    def crear_jugador(self, nombre, fecha_ingreso):
        return Jugador.objects.create(
            nombres=nombre, apellidos='prueba', fecha_nacimiento=date(2013, 1, 1),
            categoria=self.categoria, fecha_ingreso=fecha_ingreso
        )

    def test_cada_uno_cobra_desde_el_dia_en_que_entro(self):
        casos = [
            # (dia de ingreso, inicio del periodo, fin del periodo, dias que cubre)
            (date(2026, 4, 1), date(2026, 9, 1), date(2026, 9, 30), 30),
            (date(2026, 4, 13), date(2026, 9, 13), date(2026, 10, 12), 30),
            (date(2026, 4, 22), date(2026, 9, 22), date(2026, 10, 21), 30),
            (date(2026, 4, 30), date(2026, 9, 30), date(2026, 10, 29), 30),
        ]
        for indice, (ingreso, inicio, fin, dias) in enumerate(casos):
            jugador = self.crear_jugador('jugador%s' % indice, ingreso)
            self.client.post('/sistema/adm_mensualidad', {
                'action': 'generar', 'mes': 9, 'anio': 2026, 'categoria': self.categoria.id,
            })
            mensualidad = Mensualidad.objects.get(jugador=jugador, mes=9, anio=2026)

            self.assertEqual(mensualidad.periodo_inicio, inicio, ingreso)
            self.assertEqual(mensualidad.periodo_fin, fin, ingreso)
            self.assertEqual(mensualidad.dias_del_periodo(), dias, ingreso)
            self.assertEqual(mensualidad.fecha_vencimiento, inicio, ingreso)

    def test_los_periodos_no_siempre_tienen_los_mismos_dias(self):
        jugador = self.crear_jugador('febrerito', date(2026, 1, 15))

        # Del 15 de enero al 14 de febrero: 31 dias.
        self.client.post('/sistema/adm_mensualidad', {
            'action': 'generar', 'mes': 1, 'anio': 2026, 'categoria': self.categoria.id})
        enero = Mensualidad.objects.get(jugador=jugador, mes=1, anio=2026)
        self.assertEqual(enero.periodo_inicio, date(2026, 1, 15))
        self.assertEqual(enero.periodo_fin, date(2026, 2, 14))
        self.assertEqual(enero.dias_del_periodo(), 31)

        # Del 15 de febrero al 14 de marzo: 28 dias.
        self.client.post('/sistema/adm_mensualidad', {
            'action': 'generar', 'mes': 2, 'anio': 2026, 'categoria': self.categoria.id})
        febrero = Mensualidad.objects.get(jugador=jugador, mes=2, anio=2026)
        self.assertEqual(febrero.periodo_fin, date(2026, 3, 14))
        self.assertEqual(febrero.dias_del_periodo(), 28)

    def test_el_periodo_de_diciembre_salta_de_anio(self):
        jugador = self.crear_jugador('navideno', date(2026, 5, 20))
        self.client.post('/sistema/adm_mensualidad', {
            'action': 'generar', 'mes': 12, 'anio': 2026, 'categoria': self.categoria.id})

        mensualidad = Mensualidad.objects.get(jugador=jugador, mes=12, anio=2026)
        self.assertEqual(mensualidad.periodo_inicio, date(2026, 12, 20))
        self.assertEqual(mensualidad.periodo_fin, date(2027, 1, 19))

    def test_el_que_entro_un_31_cobra_el_ultimo_dia_de_los_meses_cortos(self):
        jugador = self.crear_jugador('ultimo', date(2026, 1, 31))
        self.client.post('/sistema/adm_mensualidad', {
            'action': 'generar', 'mes': 2, 'anio': 2026, 'categoria': self.categoria.id})

        mensualidad = Mensualidad.objects.get(jugador=jugador, mes=2, anio=2026)
        self.assertEqual(mensualidad.periodo_inicio, date(2026, 2, 28))
        self.assertEqual(mensualidad.periodo_fin, date(2026, 3, 30))

    def test_el_prorrateo_usa_los_dias_reales_de_cada_periodo(self):
        # Dos jugadores con el mismo precio pero periodos de distinto largo.
        largo = self.crear_jugador('largo', date(2026, 1, 15))     # enero: 31 dias
        corto = self.crear_jugador('corto', date(2026, 2, 15))     # febrero: 28 dias

        self.client.post('/sistema/adm_mensualidad', {
            'action': 'generar', 'mes': 1, 'anio': 2026, 'categoria': self.categoria.id})
        self.client.post('/sistema/adm_mensualidad', {
            'action': 'generar', 'mes': 2, 'anio': 2026, 'categoria': self.categoria.id})

        mes_largo = Mensualidad.objects.get(jugador=largo, mes=1)
        mes_corto = Mensualidad.objects.get(jugador=corto, mes=2)

        mes_largo.dias_ausente = 7
        mes_corto.dias_ausente = 7

        # 30 dolares: 7 dias de 31 pesan menos que 7 dias de 28.
        self.assertEqual(mes_largo.recalcular_por_ausencia(), Decimal('23.23'))
        self.assertEqual(mes_corto.recalcular_por_ausencia(), Decimal('22.50'))

    def test_el_texto_del_periodo_se_entiende(self):
        jugador = self.crear_jugador('textual', date(2026, 3, 13))
        self.client.post('/sistema/adm_mensualidad', {
            'action': 'generar', 'mes': 9, 'anio': 2026, 'categoria': self.categoria.id})

        mensualidad = Mensualidad.objects.get(jugador=jugador, mes=9)
        self.assertEqual(mensualidad.texto_periodo(), 'del 13/09/2026 al 12/10/2026')


class CobrarAUnSoloJugadorTest(BaseMensualidad):
    """El boton "Agregar a uno": para el que entra suelto, sin tocar al resto."""

    def setUp(self):
        self.client.force_login(self.admin)
        self.jugador.fecha_ingreso = date(2026, 6, 18)
        self.jugador.save()

    def crear(self, **extra):
        datos = {'action': 'add', 'jugador': self.jugador.id, 'mes': 9, 'anio': 2026}
        datos.update(extra)
        return self.client.post('/sistema/adm_mensualidad', datos)

    def test_el_modal_se_abre_con_el_jugador_ya_elegido(self):
        respuesta = self.client.get(
            '/sistema/adm_mensualidad?action=add&mes=9&anio=2026&jugador=%s' % self.jugador.id)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['form'].initial['periodo_inicio'], date(2026, 9, 18))
        self.assertEqual(respuesta.context['form'].initial['periodo_fin'], date(2026, 10, 17))

    def test_crea_la_de_uno_solo_sin_tocar_a_los_demas(self):
        respuesta = self.crear()
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        self.assertEqual(Mensualidad.objects.filter(mes=9, anio=2026).count(), 1)
        mensualidad = Mensualidad.objects.get(jugador=self.jugador, mes=9)
        self.assertEqual(mensualidad.valor, Decimal('25.00'))
        self.assertEqual(mensualidad.estado, MENSUALIDAD_PENDIENTE)

    def test_sin_fechas_usa_las_del_ingreso(self):
        self.crear()
        mensualidad = Mensualidad.objects.get(jugador=self.jugador, mes=9)
        self.assertEqual(mensualidad.periodo_inicio, date(2026, 9, 18))
        self.assertEqual(mensualidad.periodo_fin, date(2026, 10, 17))
        self.assertEqual(mensualidad.fecha_vencimiento, date(2026, 9, 18))

    def test_se_pueden_poner_otras_fechas(self):
        self.crear(periodo_inicio='2026-09-05', periodo_fin='2026-09-25')
        mensualidad = Mensualidad.objects.get(jugador=self.jugador, mes=9)
        self.assertEqual(mensualidad.periodo_inicio, date(2026, 9, 5))
        self.assertEqual(mensualidad.periodo_fin, date(2026, 9, 25))
        self.assertEqual(mensualidad.fecha_vencimiento, date(2026, 9, 5))
        self.assertEqual(mensualidad.dias_del_periodo(), 21)

    def test_se_puede_cobrar_otro_valor(self):
        self.crear(valor='12.50')
        mensualidad = Mensualidad.objects.get(jugador=self.jugador, mes=9)
        self.assertEqual(mensualidad.valor, Decimal('12.50'))
        self.assertEqual(mensualidad.valor_completo, Decimal('12.50'))

    def test_no_deja_repetirle_el_mes(self):
        self.crear()
        respuesta = self.crear()
        datos = json.loads(respuesta.content)
        self.assertEqual(datos['result'], 'bad')
        self.assertIn('ya tiene la mensualidad', datos['mensaje'])
        self.assertEqual(Mensualidad.objects.filter(jugador=self.jugador, mes=9).count(), 1)

    def test_las_fechas_al_reves_no_pasan(self):
        respuesta = self.crear(periodo_inicio='2026-09-25', periodo_fin='2026-09-05')
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertFalse(Mensualidad.objects.filter(jugador=self.jugador, mes=9).exists())

    def test_el_entrenador_no_puede_cobrar(self):
        self.client.force_login(self.usuario_entrenador)
        self.crear()
        self.assertFalse(Mensualidad.objects.filter(jugador=self.jugador, mes=9).exists())


class CorregirLasFechasDelCobroTest(BaseMensualidad):
    """Si el periodo quedo mal, se arregla desde el mismo cobro."""

    def setUp(self):
        self.mensualidad = Mensualidad.objects.create(
            jugador=self.jugador, mes=9, anio=2026, valor=Decimal('30.00'),
            valor_completo=Decimal('30.00'), fecha_vencimiento=date(2026, 9, 10),
            periodo_inicio=date(2026, 9, 10), periodo_fin=date(2026, 10, 9)
        )
        self.client.force_login(self.admin)

    def cobrar(self, **extra):
        datos = {'action': 'pagar', 'id': self.mensualidad.id,
                 'estado': MENSUALIDAD_PENDIENTE}
        datos.update(extra)
        return self.client.post('/sistema/adm_mensualidad', datos)

    def test_cambia_el_periodo_y_el_vencimiento(self):
        respuesta = self.cobrar(periodo_inicio='2026-09-15', periodo_fin='2026-10-14',
                                fecha_vencimiento='2026-09-20')
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.periodo_inicio, date(2026, 9, 15))
        self.assertEqual(self.mensualidad.periodo_fin, date(2026, 10, 14))
        self.assertEqual(self.mensualidad.fecha_vencimiento, date(2026, 9, 20))

    def test_sin_vencimiento_se_usa_el_inicio_del_periodo(self):
        self.cobrar(periodo_inicio='2026-09-15', periodo_fin='2026-10-14')
        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.fecha_vencimiento, date(2026, 9, 15))

    def test_dejar_las_fechas_vacias_no_las_borra(self):
        self.cobrar()
        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.periodo_inicio, date(2026, 9, 10))
        self.assertEqual(self.mensualidad.periodo_fin, date(2026, 10, 9))

    def test_el_periodo_nuevo_manda_en_el_prorrateo(self):
        # 20 dias de periodo: 5 dias que no viene valen la cuarta parte.
        self.cobrar(periodo_inicio='2026-09-01', periodo_fin='2026-09-20',
                    dias_ausente=5, motivo_ajuste='viaje')
        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.dias_del_periodo(), 20)
        self.assertEqual(self.mensualidad.valor, Decimal('22.50'))

    def test_no_acepta_un_periodo_al_reves(self):
        respuesta = self.cobrar(periodo_inicio='2026-10-14', periodo_fin='2026-09-15')
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.mensualidad.refresh_from_db()
        self.assertEqual(self.mensualidad.periodo_inicio, date(2026, 9, 10))
