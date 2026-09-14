# coding=utf-8
"""Pruebas de las evaluaciones: que se mide, quien puede medir y como se calcula el progreso."""
import json
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from jogabonito.models import (
    AREA_FISICA, AREA_TECNICA, MEDIDA_ESCALA, MEDIDA_TIEMPO, MEJOR_MENOR, ROL_ENTRENADOR,
    Categoria, Entrenador, Evaluacion, Indicador, Jugador, Medicion, PerfilUsuario, Posicion,
)

CLAVE = 'clave-de-prueba-2026'
HOY = date.today()
HACE_UNA_SEMANA = HOY - timedelta(days=7)


class BaseEvaluacion(TestCase):
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

        cls.control = Indicador.objects.create(
            nombre='control del balon', area=AREA_TECNICA, tipo_medida=MEDIDA_ESCALA, orden=1
        )
        cls.velocidad = Indicador.objects.create(
            nombre='velocidad 30m', area=AREA_FISICA, tipo_medida=MEDIDA_TIEMPO, unidad='seg', orden=1
        )

        cls.evaluacion = Evaluacion.objects.create(
            categoria=cls.mi_categoria, fecha=HACE_UNA_SEMANA, titulo='prueba 1'
        )
        cls.evaluacion.indicadores.set([cls.control, cls.velocidad])

        cls.evaluacion2 = Evaluacion.objects.create(
            categoria=cls.mi_categoria, fecha=HOY, titulo='prueba 2'
        )
        cls.evaluacion2.indicadores.set([cls.control, cls.velocidad])

    def medir(self, evaluacion, jugador, indicador, valor):
        return self.client.post('/sistema/adm_evaluacion', {
            'action': 'medir', 'evaluacion': evaluacion.id, 'jugador': jugador.id,
            'indicador': indicador.id, 'valor': valor,
        })


class IndicadorTest(BaseEvaluacion):
    def test_la_escala_se_configura_sola(self):
        indicador = Indicador.objects.create(nombre='pase de prueba', tipo_medida=MEDIDA_ESCALA)
        self.assertEqual(indicador.valor_minimo, 1)
        self.assertEqual(indicador.valor_maximo, 10)
        self.assertEqual(indicador.sufijo(), '/ 10')

    def test_en_el_tiempo_mejorar_es_bajar(self):
        self.assertEqual(self.velocidad.mejor_es, MEJOR_MENOR)
        self.assertTrue(self.velocidad.es_mejora(Decimal('5.20'), Decimal('4.90')))
        self.assertFalse(self.velocidad.es_mejora(Decimal('4.90'), Decimal('5.20')))

    def test_en_la_escala_mejorar_es_subir(self):
        self.assertTrue(self.control.es_mejora(Decimal('6'), Decimal('8')))
        self.assertFalse(self.control.es_mejora(Decimal('8'), Decimal('6')))

    def test_respeta_el_rango(self):
        self.assertTrue(self.control.rango_valido(Decimal('7')))
        self.assertFalse(self.control.rango_valido(Decimal('11')))
        self.assertFalse(self.control.rango_valido(Decimal('0')))

    def test_el_catalogo_base_queda_cargado(self):
        self.assertGreaterEqual(Indicador.objects.count(), 13)
        self.assertEqual(Posicion.objects.filter(activo=True).count(), 10)


class MedicionTest(BaseEvaluacion):
    def test_no_se_repite_el_mismo_dato(self):
        Medicion.objects.create(evaluacion=self.evaluacion, jugador=self.jugador,
                                indicador=self.control, valor=Decimal('7'))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Medicion.objects.create(evaluacion=self.evaluacion, jugador=self.jugador,
                                        indicador=self.control, valor=Decimal('8'))

    def test_compara_contra_la_toma_anterior(self):
        Medicion.objects.create(evaluacion=self.evaluacion, jugador=self.jugador,
                                indicador=self.control, valor=Decimal('6'))
        segunda = Medicion.objects.create(evaluacion=self.evaluacion2, jugador=self.jugador,
                                          indicador=self.control, valor=Decimal('8'))

        self.assertEqual(segunda.diferencia(), Decimal('2'))
        self.assertTrue(segunda.mejoro())

    def test_en_tiempo_bajar_el_numero_es_mejorar(self):
        Medicion.objects.create(evaluacion=self.evaluacion, jugador=self.jugador,
                                indicador=self.velocidad, valor=Decimal('5.40'))
        segunda = Medicion.objects.create(evaluacion=self.evaluacion2, jugador=self.jugador,
                                          indicador=self.velocidad, valor=Decimal('5.10'))
        self.assertTrue(segunda.mejoro())


class ProgresoTest(BaseEvaluacion):
    def setUp(self):
        Medicion.objects.create(evaluacion=self.evaluacion, jugador=self.jugador,
                                indicador=self.control, valor=Decimal('6'))
        Medicion.objects.create(evaluacion=self.evaluacion2, jugador=self.jugador,
                                indicador=self.control, valor=Decimal('9'))
        Medicion.objects.create(evaluacion=self.evaluacion, jugador=self.jugador,
                                indicador=self.velocidad, valor=Decimal('5.40'))
        Medicion.objects.create(evaluacion=self.evaluacion2, jugador=self.jugador,
                                indicador=self.velocidad, valor=Decimal('5.80'))
        # El companiero solo tiene la ultima toma, para poder comparar.
        Medicion.objects.create(evaluacion=self.evaluacion2, jugador=self.companiero,
                                indicador=self.control, valor=Decimal('5'))
        Medicion.objects.create(evaluacion=self.evaluacion2, jugador=self.companiero,
                                indicador=self.velocidad, valor=Decimal('5.00'))

    def test_resume_primera_ultima_y_mejor_marca(self):
        progreso = {p['indicador'].id: p for p in self.jugador.progreso()}

        control = progreso[self.control.id]
        self.assertEqual(control['tomas'], 2)
        self.assertEqual(control['primera'].valor, Decimal('6'))
        self.assertEqual(control['ultima'].valor, Decimal('9'))
        self.assertEqual(control['mejor'], Decimal('9'))
        self.assertTrue(control['mejoro'])

        velocidad = progreso[self.velocidad.id]
        self.assertEqual(velocidad['mejor'], Decimal('5.40'))  # en tiempo, la mejor es la menor
        self.assertFalse(velocidad['mejoro'])

    def test_fortalezas_y_aspectos_a_mejorar(self):
        fortalezas = [x['indicador'].id for x in self.jugador.fortalezas()]
        a_mejorar = [x['indicador'].id for x in self.jugador.aspectos_a_mejorar()]

        # Control: 9 contra 5 del grupo -> fortaleza.
        self.assertIn(self.control.id, fortalezas)
        # Velocidad: 5.80 seg contra 5.00 del grupo -> hay que mejorar.
        self.assertIn(self.velocidad.id, a_mejorar)

    def test_sin_mediciones_el_progreso_esta_vacio(self):
        self.assertEqual(self.companiero.progreso()[0]['tomas'], 1)
        self.assertEqual(self.jugador_ajeno.progreso(), [])


class PlanillaTest(BaseEvaluacion):
    def setUp(self):
        self.client.force_login(self.usuario_entrenador)

    def test_el_entrenador_anota_un_valor(self):
        respuesta = self.medir(self.evaluacion2, self.jugador, self.control, '8')
        datos = json.loads(respuesta.content)

        self.assertEqual(datos['result'], 'ok')
        self.assertEqual(datos['texto'], '8 / 10')
        self.assertEqual(Medicion.objects.get(jugador=self.jugador, indicador=self.control).valor,
                         Decimal('8'))

    def test_anotar_dos_veces_actualiza(self):
        self.medir(self.evaluacion2, self.jugador, self.control, '8')
        self.medir(self.evaluacion2, self.jugador, self.control, '9')

        mediciones = Medicion.objects.filter(evaluacion=self.evaluacion2, jugador=self.jugador,
                                             indicador=self.control)
        self.assertEqual(mediciones.count(), 1)
        self.assertEqual(mediciones.first().valor, Decimal('9'))

    def test_dejar_el_campo_vacio_borra_la_marca(self):
        self.medir(self.evaluacion2, self.jugador, self.control, '8')
        respuesta = self.medir(self.evaluacion2, self.jugador, self.control, '')

        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertEqual(Medicion.objects.count(), 0)

    def test_rechaza_un_valor_fuera_de_rango(self):
        respuesta = self.medir(self.evaluacion2, self.jugador, self.control, '15')
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertEqual(Medicion.objects.count(), 0)

    def test_rechaza_texto(self):
        respuesta = self.medir(self.evaluacion2, self.jugador, self.control, 'bien')
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertEqual(Medicion.objects.count(), 0)

    def test_acepta_coma_decimal(self):
        respuesta = self.medir(self.evaluacion2, self.jugador, self.velocidad, '5,40')
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertEqual(Medicion.objects.get(indicador=self.velocidad).valor, Decimal('5.40'))

    def test_no_mide_a_un_jugador_de_otro_grupo(self):
        respuesta = self.medir(self.evaluacion2, self.jugador_ajeno, self.control, '8')
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertEqual(Medicion.objects.count(), 0)

    def test_no_mide_a_un_retirado(self):
        respuesta = self.medir(self.evaluacion2, self.retirado, self.control, '8')
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertEqual(Medicion.objects.count(), 0)

    def test_no_mide_un_indicador_que_no_entra_en_esa_prueba(self):
        suelto = Indicador.objects.create(nombre='salto vertical prueba', tipo_medida=MEDIDA_ESCALA)
        respuesta = self.medir(self.evaluacion2, self.jugador, suelto, '8')
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertEqual(Medicion.objects.count(), 0)

    def test_una_evaluacion_cerrada_no_admite_cambios(self):
        self.evaluacion2.cerrada = True
        self.evaluacion2.save()

        respuesta = self.medir(self.evaluacion2, self.jugador, self.control, '8')
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertEqual(Medicion.objects.count(), 0)

    def test_el_avance_se_calcula_sobre_los_activos(self):
        # 2 jugadores activos x 2 indicadores = 4 datos.
        self.medir(self.evaluacion2, self.jugador, self.control, '8')
        respuesta = self.medir(self.evaluacion2, self.jugador, self.velocidad, '5.2')
        self.assertEqual(json.loads(respuesta.content)['avance'], 50)


class AccesoEvaluacionTest(BaseEvaluacion):
    def test_anonimo_no_entra(self):
        respuesta = self.client.get('/sistema/adm_evaluacion')
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/sistema/login/', respuesta['Location'])

    def test_el_entrenador_solo_ve_las_evaluaciones_de_sus_grupos(self):
        ajena = Evaluacion.objects.create(categoria=self.otra_categoria, fecha=HOY, titulo='ajena')
        ajena.indicadores.set([self.control])

        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/adm_evaluacion')
        titulos = [e.titulo for e in respuesta.context['evaluaciones']]

        self.assertIn('prueba 1', titulos)
        self.assertNotIn('ajena', titulos)

    def test_el_entrenador_no_abre_una_planilla_ajena(self):
        ajena = Evaluacion.objects.create(categoria=self.otra_categoria, fecha=HOY, titulo='ajena')
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/adm_evaluacion?action=planilla&id=%s' % ajena.id)
        self.assertIsNone(respuesta.context)

    def test_el_entrenador_no_elimina_evaluaciones(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.post('/sistema/adm_evaluacion',
                                     {'action': 'delete', 'id': self.evaluacion.id})
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertTrue(Evaluacion.objects.filter(pk=self.evaluacion.pk).exists())

    def test_el_administrador_si_elimina(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_evaluacion',
                                     {'action': 'delete', 'id': self.evaluacion.id})
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertFalse(Evaluacion.objects.filter(pk=self.evaluacion.pk).exists())

    def test_el_entrenador_no_ve_el_progreso_de_un_jugador_ajeno(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/adm_evaluacion?action=progreso&id=%s' % self.jugador_ajeno.id)
        self.assertIsNone(respuesta.context)

    def test_el_entrenador_si_ve_el_progreso_de_su_jugador(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/adm_evaluacion?action=progreso&id=%s' % self.jugador.id)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'VERA PEDRO')


class CrearEvaluacionTest(BaseEvaluacion):
    def test_el_entrenador_crea_una_prueba_en_su_grupo(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.post('/sistema/adm_evaluacion', {
            'action': 'add', 'categoria': self.mi_categoria.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'titulo': 'prueba semanal 3',
            'indicadores': [self.control.id],
        })
        datos = json.loads(respuesta.content)

        self.assertEqual(datos['result'], 'ok')
        self.assertIn('action=planilla', datos['redirect_url'])
        self.assertTrue(Evaluacion.objects.filter(titulo='prueba semanal 3').exists())

    def test_se_crea_sin_indicadores_y_manda_a_elegirlos(self):
        """Que se mide se elige en la pantalla siguiente, no en el modal."""
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.post('/sistema/adm_evaluacion', {
            'action': 'add', 'categoria': self.mi_categoria.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'titulo': 'sin nada',
        })
        datos = json.loads(respuesta.content)

        self.assertEqual(datos['result'], 'ok')
        self.assertIn('action=elegir', datos['redirect_url'])

        evaluacion = Evaluacion.objects.get(titulo='sin nada')
        self.assertEqual(evaluacion.indicadores.count(), 0)

    def test_elegir_que_se_mide_manda_a_la_planilla(self):
        self.client.force_login(self.usuario_entrenador)
        evaluacion = Evaluacion.objects.create(
            categoria=self.mi_categoria, fecha=HOY, titulo='para elegir')

        respuesta = self.client.post('/sistema/adm_evaluacion', {
            'action': 'elegir', 'id': evaluacion.id,
            'indicadores': [self.control.id, self.velocidad.id],
        })
        datos = json.loads(respuesta.content)

        self.assertEqual(datos['result'], 'ok')
        self.assertIn('action=planilla', datos['redirect_url'])
        self.assertEqual(evaluacion.indicadores.count(), 2)

    def test_no_deja_dejarla_sin_nada_que_medir(self):
        self.client.force_login(self.usuario_entrenador)
        evaluacion = Evaluacion.objects.create(
            categoria=self.mi_categoria, fecha=HOY, titulo='vacia')
        evaluacion.indicadores.set([self.control])

        respuesta = self.client.post('/sistema/adm_evaluacion', {
            'action': 'elegir', 'id': evaluacion.id,
        })
        datos = json.loads(respuesta.content)

        self.assertEqual(datos['result'], 'bad')
        self.assertIn('al menos una cosa', datos['mensaje'])
        self.assertEqual(evaluacion.indicadores.count(), 1)

    def test_avisa_si_al_quitar_algo_se_pierden_marcas_de_la_planilla(self):
        from decimal import Decimal
        from jogabonito.models import Medicion

        self.client.force_login(self.usuario_entrenador)
        evaluacion = Evaluacion.objects.create(
            categoria=self.mi_categoria, fecha=HOY, titulo='con datos')
        evaluacion.indicadores.set([self.control, self.velocidad])
        Medicion.objects.create(evaluacion=evaluacion, jugador=self.jugador,
                                indicador=self.velocidad, valor=Decimal('5.5'))

        respuesta = self.client.post('/sistema/adm_evaluacion', {
            'action': 'elegir', 'id': evaluacion.id, 'indicadores': [self.control.id],
        })
        datos = json.loads(respuesta.content)

        self.assertEqual(datos['result'], 'ok')
        self.assertIn('dejan de verse', datos['mensaje'])

    def test_no_crea_una_prueba_con_fecha_futura(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.post('/sistema/adm_evaluacion', {
            'action': 'add', 'categoria': self.mi_categoria.id,
            'fecha': (HOY + timedelta(days=3)).strftime('%Y-%m-%d'), 'titulo': 'futura',
            'indicadores': [self.control.id],
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertFalse(Evaluacion.objects.filter(titulo='futura').exists())

    def test_el_entrenador_no_crea_pruebas_en_un_grupo_ajeno(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.post('/sistema/adm_evaluacion', {
            'action': 'add', 'categoria': self.otra_categoria.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'titulo': 'invasion',
            'indicadores': [self.control.id],
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertFalse(Evaluacion.objects.filter(titulo='invasion').exists())


class CatalogoIndicadoresTest(BaseEvaluacion):
    def test_el_entrenador_no_entra_al_catalogo(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/adm_indicador')
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], '/sistema/')

    def test_el_administrador_crea_un_indicador(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_indicador', {
            'action': 'add', 'nombre': 'cabeceo', 'area': AREA_TECNICA,
            'tipo_medida': MEDIDA_ESCALA, 'mejor_es': 1, 'orden': 9, 'activo': 'on',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertTrue(Indicador.objects.filter(nombre='CABECEO').exists())

    def test_no_elimina_un_indicador_con_mediciones(self):
        Medicion.objects.create(evaluacion=self.evaluacion, jugador=self.jugador,
                                indicador=self.control, valor=Decimal('7'))
        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_indicador',
                                     {'action': 'delete', 'id': self.control.id})
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertTrue(Indicador.objects.filter(pk=self.control.pk).exists())

    def test_el_administrador_crea_una_posicion(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_indicador', {
            'action': 'addposicion', 'nombre': 'carrilero', 'abreviatura': 'car',
            'peso_tecnica': 2, 'peso_fisica': 3, 'peso_tactica': 2, 'peso_actitud': 2,
            'orden': 11, 'activo': 'on',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertTrue(Posicion.objects.filter(nombre='CARRILERO').exists())


class MedicionesPorRangoTest(BaseEvaluacion):
    """Ver todas las tomas de un jugador, o solo las de un tramo de fechas."""

    def setUp(self):
        self.vieja = Evaluacion.objects.create(
            categoria=self.mi_categoria, fecha=HOY - timedelta(days=90), titulo='prueba vieja'
        )
        self.vieja.indicadores.set([self.control])

        Medicion.objects.create(evaluacion=self.vieja, jugador=self.jugador,
                                indicador=self.control, valor=Decimal('5'))
        Medicion.objects.create(evaluacion=self.evaluacion, jugador=self.jugador,
                                indicador=self.control, valor=Decimal('7'))
        Medicion.objects.create(evaluacion=self.evaluacion2, jugador=self.jugador,
                                indicador=self.control, valor=Decimal('9'))
        self.client.force_login(self.admin)

    def test_sin_filtro_trae_todas_las_tomas(self):
        progreso = self.jugador.progreso()
        self.assertEqual(len(progreso), 1)
        self.assertEqual(progreso[0]['tomas'], 3)
        self.assertEqual(len(progreso[0]['historial']), 3)
        self.assertEqual(self.jugador.cuantas_mediciones(), 3)

    def test_el_rango_deja_solo_las_de_esas_fechas(self):
        progreso = self.jugador.progreso(desde=HOY - timedelta(days=30))
        self.assertEqual(progreso[0]['tomas'], 2)
        self.assertEqual(progreso[0]['primera'].valor, Decimal('7'))

        progreso = self.jugador.progreso(hasta=HOY - timedelta(days=30))
        self.assertEqual(progreso[0]['tomas'], 1)
        self.assertEqual(progreso[0]['ultima'].valor, Decimal('5'))

    def test_el_rango_cambia_si_mejoro(self):
        completo = self.jugador.progreso()[0]
        self.assertTrue(completo['mejoro'])
        self.assertEqual(completo['diferencia'], Decimal('4'))

        tramo = self.jugador.progreso(desde=HACE_UNA_SEMANA)[0]
        self.assertEqual(tramo['diferencia'], Decimal('2'))

    def test_sabe_desde_cuando_hay_historia(self):
        self.assertEqual(self.jugador.primera_medicion().evaluacion.fecha, self.vieja.fecha)
        self.assertEqual(self.jugador.ultima_medicion().evaluacion.fecha, HOY)

    def test_la_pantalla_filtra_por_fechas(self):
        url = '/sistema/adm_evaluacion?action=progreso&id=%s&desde=%s' % (
            self.jugador.id, (HOY - timedelta(days=30)).strftime('%Y-%m-%d'))
        respuesta = self.client.get(url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context['hay_filtro'])
        self.assertEqual(respuesta.context['progreso'][0]['tomas'], 2)
        self.assertEqual(respuesta.context['total_mediciones'], 3)

    def test_una_fecha_mal_escrita_se_ignora(self):
        respuesta = self.client.get(
            '/sistema/adm_evaluacion?action=progreso&id=%s&desde=maniana' % self.jugador.id)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context['hay_filtro'])
        self.assertEqual(respuesta.context['progreso'][0]['tomas'], 3)
