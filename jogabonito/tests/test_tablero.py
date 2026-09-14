# coding=utf-8
"""Pruebas del tablero, del rango de edad, de los tipos de prueba y de la tela de arania."""
import json
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase

from jogabonito.models import (
    AREA_FISICA, AREA_TECNICA, ASISTENCIA_FALTA, ASISTENCIA_PRESENTE, MEDIDA_ESCALA,
    MEDIDA_TIEMPO, ROL_ENTRENADOR, Asistencia, Categoria, Entrenador, Evaluacion, Indicador,
    Jugador, Medicion, PerfilUsuario, TipoEvaluacion,
)

CLAVE = 'clave-de-prueba-2026'
HOY = date.today()


class BaseTablero(TestCase):
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

        # Grupo que entrena todos los dias, para que el tablero siempre lo cuente.
        cls.mi_categoria = Categoria.objects.create(
            nombre='mi grupo', dias='1,2,3,4,5,6,7', hora_inicio=time(7, 0), hora_fin=time(9, 0),
            valor_mensual=25, edad_minima=10, edad_maxima=12
        )
        cls.mi_categoria.entrenadores.add(cls.entrenador)
        cls.otra_categoria = Categoria.objects.create(
            nombre='otro grupo', dias='2,4', hora_inicio=time(18, 0), hora_fin=time(20, 0)
        )

        cls.jugador = Jugador.objects.create(
            nombres='pedro', apellidos='vera', fecha_nacimiento=date(HOY.year - 11, 3, 3),
            categoria=cls.mi_categoria
        )
        cls.companiero = Jugador.objects.create(
            nombres='ana', apellidos='pozo', fecha_nacimiento=date(HOY.year - 11, 6, 6),
            categoria=cls.mi_categoria
        )
        cls.jugador_ajeno = Jugador.objects.create(
            nombres='sofia', apellidos='ruiz', fecha_nacimiento=date(HOY.year - 11, 4, 4),
            categoria=cls.otra_categoria
        )

        cls.control = Indicador.objects.create(
            nombre='control de prueba', area=AREA_TECNICA, tipo_medida=MEDIDA_ESCALA, orden=1
        )
        cls.velocidad = Indicador.objects.create(
            nombre='velocidad de prueba', area=AREA_FISICA, tipo_medida=MEDIDA_TIEMPO,
            unidad='seg', orden=1
        )


class RangoEdadTest(BaseTablero):
    def test_texto_del_rango(self):
        self.assertEqual(self.mi_categoria.rango_edad_texto(), '10 a 12 anios')
        self.assertEqual(self.otra_categoria.rango_edad_texto(), 'Todas las edades')

        solo_max = Categoria.objects.create(
            nombre='sub 8', hora_inicio=time(8, 0), hora_fin=time(9, 0), edad_maxima=8
        )
        self.assertEqual(solo_max.rango_edad_texto(), 'Hasta 8 anios')

    def test_sabe_que_edad_encaja(self):
        self.assertTrue(self.mi_categoria.edad_encaja(11))
        self.assertFalse(self.mi_categoria.edad_encaja(9))
        self.assertFalse(self.mi_categoria.edad_encaja(13))
        # Sin rango entra cualquiera.
        self.assertTrue(self.otra_categoria.edad_encaja(30))

    def test_detecta_a_los_que_se_pasaron_de_edad(self):
        self.assertEqual(self.mi_categoria.jugadores_fuera_de_rango(), [])

        grande = Jugador.objects.create(
            nombres='mario', apellidos='paz', fecha_nacimiento=date(HOY.year - 17, 1, 1),
            categoria=self.mi_categoria
        )
        fuera = [j.id for j in self.mi_categoria.jugadores_fuera_de_rango()]
        self.assertIn(grande.id, fuera)
        self.assertNotIn(self.jugador.id, fuera)

    def test_el_formulario_rechaza_un_rango_invertido(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_categoria', {
            'action': 'add', 'nombre': 'RANGO MALO', 'hora_inicio': '07:00', 'hora_fin': '09:00',
            'valor_mensual': '25', 'edad_minima': 12, 'edad_maxima': 8,
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertFalse(Categoria.objects.filter(nombre='RANGO MALO').exists())


class TipoEvaluacionTest(BaseTablero):
    def test_el_catalogo_base_trae_la_prueba_inicial(self):
        inicial = TipoEvaluacion.objects.filter(es_inicial=True)
        self.assertEqual(inicial.count(), 1)
        self.assertEqual(inicial.first().nombre, 'DIAGNOSTICA INICIAL')

    def test_solo_un_tipo_puede_ser_el_inicial(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_indicador', {
            'action': 'addtipo', 'nombre': 'otra inicial', 'color': 'info',
            'es_inicial': 'on', 'orden': 9, 'activo': 'on',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertEqual(TipoEvaluacion.objects.filter(es_inicial=True).count(), 1)
        self.assertEqual(TipoEvaluacion.objects.get(es_inicial=True).nombre, 'OTRA INICIAL')

    def test_la_evaluacion_guarda_su_tipo(self):
        tipo = TipoEvaluacion.objects.get(es_inicial=True)
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.post('/sistema/adm_evaluacion', {
            'action': 'add', 'categoria': self.mi_categoria.id, 'tipo': tipo.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'titulo': 'diagnostico de ingreso',
            'indicadores': [self.control.id],
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertEqual(Evaluacion.objects.get(titulo='diagnostico de ingreso').tipo, tipo)

    def test_no_elimina_un_tipo_en_uso(self):
        tipo = TipoEvaluacion.objects.get(es_inicial=True)
        evaluacion = Evaluacion.objects.create(categoria=self.mi_categoria, fecha=HOY,
                                               titulo='usada', tipo=tipo)
        evaluacion.indicadores.set([self.control])

        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_indicador', {'action': 'deltipo', 'id': tipo.id})
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertTrue(TipoEvaluacion.objects.filter(pk=tipo.pk).exists())

    def test_el_entrenador_no_administra_tipos(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.post('/sistema/adm_indicador', {
            'action': 'addtipo', 'nombre': 'pirata', 'color': 'info', 'orden': 1, 'activo': 'on',
        })
        self.assertIn(respuesta.status_code, (200, 302))
        self.assertFalse(TipoEvaluacion.objects.filter(nombre='PIRATA').exists())


class RadarTest(BaseTablero):
    def setUp(self):
        evaluacion = Evaluacion.objects.create(categoria=self.mi_categoria, fecha=HOY, titulo='p1')
        evaluacion.indicadores.set([self.control, self.velocidad])

        # El jugador saca 9/10 y el companiero 5/10.
        Medicion.objects.create(evaluacion=evaluacion, jugador=self.jugador,
                                indicador=self.control, valor=Decimal('9'))
        Medicion.objects.create(evaluacion=evaluacion, jugador=self.companiero,
                                indicador=self.control, valor=Decimal('5'))
        # En velocidad el jugador es el mas lento del grupo (menos es mejor).
        Medicion.objects.create(evaluacion=evaluacion, jugador=self.jugador,
                                indicador=self.velocidad, valor=Decimal('6.00'))
        Medicion.objects.create(evaluacion=evaluacion, jugador=self.companiero,
                                indicador=self.velocidad, valor=Decimal('5.00'))

    def test_la_escala_se_normaliza_contra_su_maximo(self):
        radar = self.jugador.radar()
        tecnica = [e for e in radar['ejes'] if e['etiqueta'] == 'TECNICA'][0]
        # 9 sobre un rango de 1 a 10 -> (9-1)/9 = 88.9
        self.assertAlmostEqual(tecnica['puntaje'], 88.9, places=1)

    def test_en_el_tiempo_el_mas_lento_saca_cero(self):
        radar = self.jugador.radar()
        fisica = [e for e in radar['ejes'] if e['etiqueta'] == 'FISICA'][0]
        self.assertEqual(fisica['puntaje'], 0.0)

        radar_companiero = self.companiero.radar()
        fisica_c = [e for e in radar_companiero['ejes'] if e['etiqueta'] == 'FISICA'][0]
        self.assertEqual(fisica_c['puntaje'], 100.0)

    def test_las_areas_sin_medir_quedan_en_cero(self):
        radar = self.jugador.radar()
        tactica = [e for e in radar['ejes'] if e['etiqueta'] == 'TACTICA'][0]
        self.assertEqual(tactica['medidos'], 0)
        self.assertEqual(tactica['puntaje'], 0.0)
        self.assertEqual(radar['areas_medidas'], 2)

    def test_siempre_devuelve_los_cuatro_ejes_de_campo(self):
        """Portero y mental solo aparecen si se le midieron."""
        self.assertEqual(len(self.jugador.radar()['ejes']), 4)
        self.assertEqual(len(self.jugador_ajeno.radar()['ejes']), 4)

    def test_al_arquero_se_le_agrega_su_eje(self):
        from decimal import Decimal
        from jogabonito.models import AREA_PORTERO, MEDIDA_ESCALA, Indicador, Medicion

        from jogabonito.models import Evaluacion

        blocaje = Indicador.objects.create(
            nombre='blocaje', area=AREA_PORTERO, tipo_medida=MEDIDA_ESCALA, orden=1)
        prueba = Evaluacion.objects.create(
            categoria=self.mi_categoria, fecha=HOY, titulo='prueba de arquero')
        prueba.indicadores.set([blocaje])
        Medicion.objects.create(evaluacion=prueba, jugador=self.jugador,
                                indicador=blocaje, valor=Decimal('8'))

        areas = [e['etiqueta'] for e in self.jugador.radar()['ejes']]
        self.assertIn('PORTERO', areas)
        self.assertEqual(len(areas), 5)

    def test_sin_companieros_no_se_puede_normalizar_un_tiempo(self):
        """Con un solo jugador medido no hay contra que comparar el tiempo."""
        radar = self.jugador_ajeno.radar()
        self.assertEqual(radar['areas_medidas'], 0)

    def test_el_detalle_viene_ordenado_de_peor_a_mejor(self):
        detalle = self.jugador.radar()['detalle']
        self.assertEqual(detalle[0]['indicador'], self.velocidad)
        self.assertEqual(detalle[-1]['indicador'], self.control)


class TableroTest(BaseTablero):
    def test_anonimo_no_entra(self):
        respuesta = self.client.get('/sistema/dashboard')
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/sistema/login/', respuesta['Location'])

    def test_el_administrador_ve_toda_la_academia(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get('/sistema/dashboard')

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['total_jugadores'], 3)
        self.assertEqual(respuesta.context['total_categorias'], 2)
        self.assertIn('solicitudes_nuevas', respuesta.context)

    def test_el_entrenador_ya_no_tiene_tablero(self):
        """Su menu quedo en asistencia y evaluaciones."""
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/dashboard')
        self.assertEqual(respuesta.status_code, 302)

    def sin_uso_el_entrenador_solo_ve_lo_suyo(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/dashboard')

        self.assertEqual(respuesta.context['total_jugadores'], 2)
        self.assertEqual(respuesta.context['total_categorias'], 1)
        self.assertIsNone(respuesta.context.get('solicitudes_nuevas'))

    def test_cuenta_laasistencia_del_dia(self):
        Asistencia.objects.create(jugador=self.jugador, categoria=self.mi_categoria,
                                  fecha=HOY, estado=ASISTENCIA_PRESENTE)
        Asistencia.objects.create(jugador=self.companiero, categoria=self.mi_categoria,
                                  fecha=HOY, estado=ASISTENCIA_FALTA)

        self.client.force_login(self.admin)
        asistencia = self.client.get('/sistema/dashboard').context['asistencia']

        self.assertEqual(asistencia['presentes'], 1)
        self.assertEqual(asistencia['faltas'], 1)
        # El administrador ve toda la academia, asi que los esperados son los
        # de todos los grupos que entrenan hoy.
        self.assertGreaterEqual(asistencia['esperados'], 2)

    def test_avisa_de_los_jugadores_con_asistencia_baja(self):
        for indice in range(4):
            Asistencia.objects.create(
                jugador=self.jugador, categoria=self.mi_categoria,
                fecha=HOY - timedelta(days=indice + 1), estado=ASISTENCIA_FALTA
            )

        self.client.force_login(self.admin)
        alertas = self.client.get('/sistema/dashboard').context['en_alerta']

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0]['jugador'], self.jugador)
        self.assertEqual(alertas[0]['resumen']['porcentaje'], 0.0)

    def test_cuenta_los_jugadores_sin_medir(self):
        self.client.force_login(self.admin)
        # Los tres jugadores de la academia, ninguno con mediciones.
        self.assertEqual(self.client.get('/sistema/dashboard').context['sin_evaluar'], 3)

    def test_lista_loscumpleanios_proximos_cercanos(self):
        proximo = HOY + timedelta(days=5)
        Jugador.objects.create(
            nombres='hugo', apellidos='cumple',
            fecha_nacimiento=date(HOY.year - 12, proximo.month, proximo.day),
            categoria=self.mi_categoria
        )
        self.client.force_login(self.admin)
        cumples = self.client.get('/sistema/dashboard').context['cumpleanios']

        self.assertTrue(any(c['jugador'].apellidos == 'CUMPLE' and c['faltan'] == 5 for c in cumples))
