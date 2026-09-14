# coding=utf-8
"""Pruebas de lo que hace que la academia se sienta familia.

Apodos, notas del profe sobre cada ninio, a quien le toca cada grupo esta
semana y quien viene bajando en sus mediciones.
"""
import json
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from jogabonito.adm_turno import grupos_a_cargo_de, grupos_con_encargado, grupos_de_hoy
from jogabonito.dashboard import quienes_estan_bajando
from jogabonito.models import (
    AREA_FISICA, AREA_TECNICA, MEDIDA_ESCALA, MEDIDA_TIEMPO, NOTA_ATENCION, NOTA_FELICITACION,
    NOTA_GENERAL, ROL_ENTRENADOR, Categoria, Entrenador, Evaluacion, Indicador, Jugador,
    Medicion, Nota,
    PerfilUsuario, quien_dirige,
)

CLAVE = 'clave-de-prueba-2026'
HOY = date.today()


class BaseFamilia(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('cargar_base', '--admin-clave', CLAVE, verbosity=0)
        cls.admin = User.objects.get(username='admin')

        cls.usuario_entrenador = User.objects.create_user('profe1', password=CLAVE)
        cls.usuario_entrenador.groups.add(Group.objects.get(name='ENTRENADOR'))
        PerfilUsuario.objects.create(usuario=cls.usuario_entrenador, rol=ROL_ENTRENADOR)
        cls.profe = Entrenador.objects.create(
            nombres='luis', apellidos='mora', telefono='0999999999', usuario=cls.usuario_entrenador
        )
        cls.otro_profe = Entrenador.objects.create(
            nombres='ana', apellidos='paz', telefono='0988888888'
        )

        cls.categoria = Categoria.objects.create(
            nombre='manana', dias='1,3,5', hora_inicio=time(7, 0), hora_fin=time(9, 0),
            valor_mensual=Decimal('25.00')
        )
        cls.categoria.entrenadores.add(cls.profe, cls.otro_profe)

        cls.ajena = Categoria.objects.create(
            nombre='tarde', dias='2,4', hora_inicio=time(15, 0), hora_fin=time(17, 0),
            valor_mensual=Decimal('25.00')
        )

        cls.jugador = Jugador.objects.create(
            nombres='juan carlos', apellidos='vera', fecha_nacimiento=date(2013, 3, 3),
            categoria=cls.categoria
        )
        cls.otro = Jugador.objects.create(
            nombres='maria', apellidos='pozo', fecha_nacimiento=date(2014, 5, 5),
            categoria=cls.categoria
        )


class ApodoTest(BaseFamilia):
    def test_se_guarda_en_mayusculas_y_limpio(self):
        self.jugador.apodo = '  el  chino '
        self.jugador.save()
        self.jugador.refresh_from_db()
        self.assertEqual(self.jugador.apodo, 'EL CHINO')

    def test_como_le_dicen_usa_el_apodo(self):
        self.jugador.apodo = 'CHINO'
        self.jugador.save()
        self.assertEqual(self.jugador.como_le_dicen(), 'CHINO')
        self.assertEqual(self.jugador.nombre_con_apodo(), 'VERA JUAN CARLOS (CHINO)')

    def test_sin_apodo_le_dicen_por_su_primer_nombre(self):
        self.assertEqual(self.jugador.como_le_dicen(), 'JUAN')
        self.assertEqual(self.jugador.nombre_con_apodo(), 'VERA JUAN CARLOS')

    def test_se_puede_poner_desde_el_formulario(self):
        self.client.force_login(self.admin)
        self.client.post('/sistema/adm_jugador', {
            'action': 'edit', 'id': self.jugador.id,
            'nombres': 'juan carlos', 'apellidos': 'vera', 'apodo': 'chino',
            'fecha_nacimiento': '2013-03-03', 'fecha_ingreso': HOY.strftime('%Y-%m-%d'),
            'categoria': self.categoria.id, 'estado': 1,
        })
        self.jugador.refresh_from_db()
        self.assertEqual(self.jugador.apodo, 'CHINO')


class NotasDelProfeTest(BaseFamilia):
    def escribir(self, usuario, texto='se le ve mas suelto con el balon', **extra):
        self.client.force_login(usuario)
        datos = {
            'action': 'nota', 'jugador': self.jugador.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'tipo': NOTA_FELICITACION, 'texto': texto,
        }
        datos.update(extra)
        return self.client.post('/sistema/adm_evaluacion', datos)

    def test_el_entrenador_puede_anotar_a_sus_jugadores(self):
        self.categoria.entrenadores.add(self.profe)
        respuesta = self.escribir(self.usuario_entrenador)
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        nota = Nota.objects.get()
        self.assertEqual(nota.jugador, self.jugador)
        self.assertEqual(nota.entrenador, self.profe)
        self.assertEqual(nota.firma(), self.profe.nombre_completo())

    def test_la_nota_del_administrador_queda_firmada_por_administracion(self):
        self.escribir(self.admin)
        self.assertEqual(Nota.objects.get().firma(), 'ADMINISTRACION')

    def test_no_deja_anotar_a_un_jugador_de_otro_grupo(self):
        ajeno = Jugador.objects.create(
            nombres='sofia', apellidos='ruiz', fecha_nacimiento=date(2013, 4, 4),
            categoria=self.ajena
        )
        self.client.force_login(self.usuario_entrenador)
        self.client.post('/sistema/adm_evaluacion', {
            'action': 'nota', 'jugador': ajeno.id, 'fecha': HOY.strftime('%Y-%m-%d'),
            'tipo': NOTA_ATENCION, 'texto': 'no deberia poder',
        })
        self.assertEqual(Nota.objects.count(), 0)

    def test_no_acepta_una_nota_de_dos_letras(self):
        respuesta = self.escribir(self.admin, texto='ok')
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertEqual(Nota.objects.count(), 0)

    def test_no_acepta_una_fecha_futura(self):
        respuesta = self.escribir(self.admin, fecha=(HOY + timedelta(days=2)).strftime('%Y-%m-%d'))
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')

    def test_se_ven_en_la_ficha_y_se_pueden_borrar(self):
        self.escribir(self.admin)
        nota = Nota.objects.get()

        respuesta = self.client.get('/sistema/adm_jugador?action=view&id=%s' % self.jugador.id)
        self.assertEqual(respuesta.context['total_notas'], 1)
        self.assertIn(nota, list(respuesta.context['notas']))

        self.client.post('/sistema/adm_evaluacion', {'action': 'borrarnota', 'id': nota.id})
        self.assertEqual(Nota.objects.count(), 0)

    def test_el_texto_se_guarda_sin_espacios_de_mas(self):
        self.escribir(self.admin, texto='  le  cuesta   pedir la pelota  ')
        self.assertEqual(Nota.objects.get().texto, 'le cuesta pedir la pelota')


class EncargadoDelGrupoTest(BaseFamilia):
    """Un grupo, un profe a cargo. Lo mas simple que se puede."""

    def setUp(self):
        self.client.force_login(self.admin)

    def asignar(self, entrenador=None, categoria=None):
        return self.client.post('/sistema/adm_turno', {
            'action': 'asignar',
            'categoria': (categoria or self.categoria).id,
            'entrenador': entrenador.id if entrenador else '',
        })

    def test_se_pone_el_encargado_del_grupo(self):
        respuesta = self.asignar(self.profe)
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        self.categoria.refresh_from_db()
        self.assertEqual(self.categoria.encargado, self.profe)
        self.assertEqual(quien_dirige(self.categoria), self.profe)

    def test_se_puede_cambiar_cuando_haga_falta(self):
        self.asignar(self.profe)
        self.asignar(self.otro_profe)

        self.categoria.refresh_from_db()
        self.assertEqual(self.categoria.encargado, self.otro_profe)

    def test_se_puede_dejar_sin_encargado(self):
        self.asignar(self.profe)
        self.asignar(None)

        self.categoria.refresh_from_db()
        self.assertIsNone(self.categoria.encargado)

    def test_solo_deja_poner_a_un_profe_del_grupo(self):
        """Quien da clases en el grupo se define en Categorias, no aqui."""
        suelto = Entrenador.objects.create(nombres='pepe', apellidos='luna', telefono='0977777777')
        respuesta = self.asignar(suelto)
        datos = json.loads(respuesta.content)

        self.assertEqual(datos['result'], 'bad')
        self.assertIn('no da clases en', datos['mensaje'])
        self.categoria.refresh_from_db()
        self.assertIsNone(self.categoria.encargado)

    def test_no_deja_poner_a_uno_inactivo(self):
        guardado = Entrenador.objects.create(nombres='raul', apellidos='paz',
                                             telefono='0966666666', activo=False)
        respuesta = self.asignar(guardado)
        datos = json.loads(respuesta.content)

        self.assertEqual(datos['result'], 'bad')
        self.assertIn('no esta activo', datos['mensaje'])

    def test_la_lista_solo_ofrece_a_los_del_grupo(self):
        Entrenador.objects.create(nombres='pepe', apellidos='luna', telefono='0977777777')
        filas = grupos_con_encargado([self.categoria])
        nombres = [e.nombre_completo() for e in filas[0]['candidatos']]

        self.assertNotIn('LUNA PEPE', nombres)
        self.assertIn(self.profe.nombre_completo(), nombres)

    def test_avisa_cuantos_grupos_quedan_sin_encargado(self):
        respuesta = self.client.get('/sistema/adm_turno')
        self.assertEqual(respuesta.context['sin_encargado'], len(respuesta.context['grupos']))

        self.asignar(self.profe)
        respuesta = self.client.get('/sistema/adm_turno')
        self.assertEqual(respuesta.context['sin_encargado'],
                         len(respuesta.context['grupos']) - 1)

    def test_los_grupos_de_hoy_dicen_quien_esta_a_cargo(self):
        self.asignar(self.profe)
        de_hoy = grupos_de_hoy([self.categoria], HOY)

        if self.categoria.entrena_hoy(HOY):
            self.assertEqual(de_hoy[0]['encargado'], self.profe)
        else:
            self.assertEqual(de_hoy, [])

    def test_el_profe_sabe_de_que_grupos_esta_a_cargo(self):
        self.asignar(self.profe)
        self.categoria.refresh_from_db()

        suyos = grupos_a_cargo_de(self.profe, [self.categoria, self.ajena])
        self.assertEqual(suyos, [self.categoria])
        self.assertEqual(grupos_a_cargo_de(self.otro_profe, [self.categoria]), [])
        self.assertEqual(grupos_a_cargo_de(None, [self.categoria]), [])

    def test_la_pantalla_trae_solo_los_profes_del_grupo(self):
        filas = grupos_con_encargado([self.categoria])
        nombres = [e.nombre_completo() for e in filas[0]['candidatos']]

        self.assertIn(self.profe.nombre_completo(), nombres)
        self.assertIn(self.otro_profe.nombre_completo(), nombres)

    def test_el_entrenador_no_cambia_encargados(self):
        self.asignar(self.profe)

        self.client.force_login(self.usuario_entrenador)
        self.assertEqual(self.client.get('/sistema/adm_turno').status_code, 302)

        self.asignar(self.otro_profe)
        self.categoria.refresh_from_db()
        self.assertEqual(self.categoria.encargado, self.profe)

    def test_el_entrenador_lo_ve_al_tomar_lista(self):
        self.categoria.encargado = self.profe
        self.categoria.save()

        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/adm_asistencia')

        if self.categoria.entrena_hoy(HOY):
            self.assertEqual(len(respuesta.context['mis_clases']), 1)
        else:
            self.assertEqual(respuesta.context['mis_clases'], [])


class QuienVieneBajandoTest(BaseFamilia):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.control = Indicador.objects.create(
            nombre='control del balon', area=AREA_TECNICA, tipo_medida=MEDIDA_ESCALA, orden=1
        )
        cls.velocidad = Indicador.objects.create(
            nombre='velocidad 30m', area=AREA_FISICA, tipo_medida=MEDIDA_TIEMPO,
            unidad='seg', orden=1
        )

        cls.primera = Evaluacion.objects.create(
            categoria=cls.categoria, fecha=HOY - timedelta(days=14), titulo='prueba 1'
        )
        cls.primera.indicadores.set([cls.control, cls.velocidad])
        cls.segunda = Evaluacion.objects.create(
            categoria=cls.categoria, fecha=HOY, titulo='prueba 2'
        )
        cls.segunda.indicadores.set([cls.control, cls.velocidad])

    def medir(self, jugador, indicador, antes, ahora):
        Medicion.objects.create(evaluacion=self.primera, jugador=jugador,
                                indicador=indicador, valor=Decimal(antes))
        Medicion.objects.create(evaluacion=self.segunda, jugador=jugador,
                                indicador=indicador, valor=Decimal(ahora))

    def test_detecta_al_que_bajo_su_nota(self):
        self.medir(self.jugador, self.control, '9', '6')
        bajas = self.jugador.retrocesos()

        self.assertEqual(len(bajas), 1)
        self.assertEqual(bajas[0]['indicador'], self.control)
        self.assertIn('9', bajas[0]['desde'])
        self.assertIn('6', bajas[0]['hasta'])

    def test_en_los_tiempos_subir_es_empeorar(self):
        self.medir(self.jugador, self.velocidad, '5.20', '5.60')
        self.assertEqual(len(self.jugador.retrocesos()), 1)

    def test_el_que_mejora_no_sale(self):
        self.medir(self.jugador, self.control, '6', '9')
        self.medir(self.jugador, self.velocidad, '5.60', '5.20')
        self.assertEqual(self.jugador.retrocesos(), [])

    def test_el_que_se_mantiene_igual_no_sale(self):
        self.medir(self.jugador, self.control, '8', '8')
        self.assertEqual(self.jugador.retrocesos(), [])

    def test_con_una_sola_toma_no_se_puede_comparar(self):
        Medicion.objects.create(evaluacion=self.segunda, jugador=self.jugador,
                                indicador=self.control, valor=Decimal('4'))
        self.assertEqual(self.jugador.retrocesos(), [])

    def test_la_pantalla_los_ordena_por_cuantas_bajas(self):
        self.medir(self.jugador, self.control, '9', '6')
        self.medir(self.jugador, self.velocidad, '5.20', '5.90')
        self.medir(self.otro, self.control, '7', '6')

        self.client.force_login(self.admin)
        respuesta = self.client.get('/sistema/adm_evaluacion?action=bajando')
        filas = respuesta.context['filas']

        self.assertEqual(filas[0]['jugador'], self.jugador)
        self.assertEqual(filas[0]['cuantos'], 2)
        self.assertEqual(filas[1]['jugador'], self.otro)

    def test_el_tablero_muestra_a_los_que_bajan(self):
        self.medir(self.jugador, self.control, '9', '6')
        filas = quienes_estan_bajando([self.jugador, self.otro])

        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['jugador'], self.jugador)

    def test_el_entrenador_solo_ve_a_los_suyos(self):
        ajeno = Jugador.objects.create(
            nombres='sofia', apellidos='ruiz', fecha_nacimiento=date(2013, 4, 4),
            categoria=self.ajena
        )
        otra_prueba = Evaluacion.objects.create(
            categoria=self.ajena, fecha=HOY - timedelta(days=14), titulo='ajena 1')
        otra_prueba.indicadores.set([self.control])
        ultima = Evaluacion.objects.create(categoria=self.ajena, fecha=HOY, titulo='ajena 2')
        ultima.indicadores.set([self.control])
        Medicion.objects.create(evaluacion=otra_prueba, jugador=ajeno,
                                indicador=self.control, valor=Decimal('9'))
        Medicion.objects.create(evaluacion=ultima, jugador=ajeno,
                                indicador=self.control, valor=Decimal('5'))
        self.medir(self.jugador, self.control, '9', '6')

        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/adm_evaluacion?action=bajando')
        jugadores = [f['jugador'] for f in respuesta.context['filas']]

        self.assertIn(self.jugador, jugadores)
        self.assertNotIn(ajeno, jugadores)


class NovedadEnLaAsistenciaTest(BaseFamilia):
    """Al tomar lista se ve con que viene cada chico y se anota lo de hoy."""

    def setUp(self):
        self.client.force_login(self.admin)

    def test_sin_notas_no_muestra_nada(self):
        respuesta = self.client.get('/sistema/adm_asistencia?categoria=%s' % self.categoria.id)
        for fila in respuesta.context['filas']:
            self.assertIsNone(fila['nota'])

    def test_muestra_la_ultima_novedad_de_cada_uno(self):
        Nota.objects.create(jugador=self.jugador, fecha=HOY - timedelta(days=10),
                            tipo=NOTA_GENERAL, texto='le cuesta el pase largo')
        reciente = Nota.objects.create(jugador=self.jugador, fecha=HOY,
                                       tipo=NOTA_ATENCION, texto='vino desanimado')

        respuesta = self.client.get('/sistema/adm_asistencia?categoria=%s' % self.categoria.id)
        filas = {f['jugador'].id: f for f in respuesta.context['filas']}

        self.assertEqual(filas[self.jugador.id]['nota'], reciente)
        self.assertIsNone(filas[self.otro.id]['nota'])

    def test_la_novedad_se_ve_en_la_pantalla(self):
        Nota.objects.create(jugador=self.jugador, fecha=HOY, tipo=NOTA_ATENCION,
                            texto='hay que cuidarle el tobillo')

        respuesta = self.client.get('/sistema/adm_asistencia?categoria=%s' % self.categoria.id)
        self.assertContains(respuesta, 'hay que cuidarle el tobillo')

    def test_desde_ahi_se_anota_una_nueva(self):
        self.client.post('/sistema/adm_evaluacion', {
            'action': 'nota', 'jugador': self.jugador.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'tipo': NOTA_GENERAL,
            'texto': 'hoy jugo muy suelto por la banda',
        })

        respuesta = self.client.get('/sistema/adm_asistencia?categoria=%s' % self.categoria.id)
        filas = {f['jugador'].id: f for f in respuesta.context['filas']}
        self.assertEqual(filas[self.jugador.id]['nota'].texto, 'hoy jugo muy suelto por la banda')


class EnlacesDeWhatsappTest(BaseFamilia):
    """Un toque en el numero y se abre WhatsApp: la app en el celular, la web
    en la computadora. Eso lo hace wa.me con el numero en formato internacional.
    """

    def setUp(self):
        self.client.force_login(self.admin)
        self.jugador.telefono = '0999955936'
        self.jugador.save()

    def test_el_numero_del_jugador_queda_listo_para_wa_me(self):
        self.assertEqual(self.jugador.numero_whatsapp(), '593999955936')

    def test_sin_telefono_no_hay_enlace(self):
        self.otro.telefono = ''
        self.otro.save()
        self.assertEqual(self.otro.numero_whatsapp(), '')

    def test_si_tiene_representante_se_le_escribe_a_el(self):
        from jogabonito.models import Representante

        papa = Representante.objects.create(
            nombres='maria', apellidos='torres', telefono='0988888888', parentesco=1)
        self.jugador.representante = papa
        self.jugador.save()

        self.assertEqual(self.jugador.whatsapp_de_contacto(), '593988888888')

    def test_sin_representante_se_le_escribe_al_jugador(self):
        self.assertEqual(self.jugador.whatsapp_de_contacto(), '593999955936')

    def test_el_enlace_sale_en_la_ficha(self):
        respuesta = self.client.get('/sistema/adm_jugador?action=view&id=%s' % self.jugador.id)
        self.assertContains(respuesta, 'https://wa.me/593999955936')

    def test_y_en_la_lista_de_jugadores(self):
        respuesta = self.client.get('/sistema/adm_jugador')
        self.assertContains(respuesta, 'https://wa.me/593999955936')


class LaNotaNoTocaLaAsistenciaTest(BaseFamilia):
    """Abrir la lista no guarda nada: la novedad es solo lectura.

    La nota vive en su propia tabla y esta atada al JUGADOR, no al dia. Por eso
    se ve siempre, aunque ese dia no se tome lista, y por eso abrir la pantalla
    no crea ni una fila de asistencia.
    """

    def setUp(self):
        self.client.force_login(self.admin)
        self.nota = Nota.objects.create(
            jugador=self.jugador, fecha=HOY - timedelta(days=20),
            tipo=NOTA_GENERAL, texto='le cuesta el pase largo'
        )

    def test_abrir_la_lista_no_crea_asistencias(self):
        from jogabonito.models import Asistencia

        for _ in range(3):
            self.client.get('/sistema/adm_asistencia?categoria=%s' % self.categoria.id)

        self.assertEqual(Asistencia.objects.count(), 0)

    def test_verla_en_otro_dia_tampoco_guarda_nada(self):
        from jogabonito.models import Asistencia

        otro_dia = (HOY - timedelta(days=5)).strftime('%Y-%m-%d')
        respuesta = self.client.get(
            '/sistema/adm_asistencia?categoria=%s&fecha=%s' % (self.categoria.id, otro_dia))

        filas = {f['jugador'].id: f for f in respuesta.context['filas']}
        self.assertEqual(filas[self.jugador.id]['nota'], self.nota)
        self.assertIsNone(filas[self.jugador.id]['asistencia'])
        self.assertEqual(Asistencia.objects.count(), 0)

    def test_la_nota_no_se_borra_ni_se_repite_al_marcar(self):
        from jogabonito.models import ASISTENCIA_PRESENTE, Asistencia

        self.client.post('/sistema/adm_asistencia', {
            'action': 'marcar', 'categoria': self.categoria.id,
            'fecha': HOY.strftime('%Y-%m-%d'), 'jugador': self.jugador.id,
            'estado': ASISTENCIA_PRESENTE,
        })

        self.assertEqual(Asistencia.objects.count(), 1)
        self.assertEqual(Nota.objects.count(), 1)

    def test_la_fecha_que_sale_es_la_de_la_nota(self):
        respuesta = self.client.get('/sistema/adm_asistencia?categoria=%s' % self.categoria.id)
        self.assertContains(respuesta, self.nota.fecha.strftime('%d/%m/%Y'))
