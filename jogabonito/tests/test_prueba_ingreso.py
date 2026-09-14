# coding=utf-8
"""La prueba de ingreso: se le toma a UNO, el dia que venga.

El chico llega, el profe lo coge aparte y lo mide. No espera a la jornada del
grupo y casi nunca cae el mismo dia que la de los demas. Eso queda como su
punto de partida y contra eso se compara todo lo que venga despues.
"""
import json
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase

from jogabonito.models import (
    AREA_TECNICA, MEDIDA_ESCALA, ROL_ENTRENADOR, Categoria, Entrenador, Evaluacion, Indicador,
    Jugador, Medicion, PerfilUsuario, TipoEvaluacion,
)

CLAVE = 'clave-de-prueba-2026'
HOY = date.today()


class BaseIngreso(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('cargar_base', '--admin-clave', CLAVE, verbosity=0)
        cls.admin = User.objects.get(username='admin')

        cls.usuario_entrenador = User.objects.create_user('profeing', password=CLAVE)
        cls.usuario_entrenador.groups.add(Group.objects.get(name='ENTRENADOR'))
        PerfilUsuario.objects.create(usuario=cls.usuario_entrenador, rol=ROL_ENTRENADOR)
        cls.profe = Entrenador.objects.create(
            nombres='luis', apellidos='mora', telefono='0999999999', usuario=cls.usuario_entrenador
        )

        cls.categoria = Categoria.objects.create(
            nombre='noche', dias='2,4', hora_inicio=time(18, 0), hora_fin=time(20, 0),
            valor_mensual=Decimal('25.00')
        )
        cls.categoria.entrenadores.add(cls.profe)

        cls.ajena = Categoria.objects.create(
            nombre='manana', dias='1,3', hora_inicio=time(7, 0), hora_fin=time(9, 0),
            valor_mensual=Decimal('25.00')
        )

        cls.jugador = Jugador.objects.create(
            nombre1='edison', nombre2='rolando', apellido1='moyolema', apellido2='moyolema',
            fecha_nacimiento=date(1989, 3, 13), categoria=cls.categoria
        )
        cls.companiero = Jugador.objects.create(
            nombres='luis', apellidos='sailema', fecha_nacimiento=date(1993, 2, 25),
            categoria=cls.categoria
        )


class PruebaDeIngresoTest(BaseIngreso):
    def setUp(self):
        self.client.force_login(self.admin)

    def tomar(self, jugador=None, **extra):
        datos = {'action': 'ingreso', 'jugador': (jugador or self.jugador).id}
        datos.update(extra)
        return self.client.post('/sistema/adm_evaluacion', datos)

    def test_crea_una_prueba_solo_para_el(self):
        respuesta = self.tomar()
        datos = json.loads(respuesta.content)
        self.assertEqual(datos['result'], 'ok')
        self.assertIn('planilla', datos['redirect_url'])

        evaluacion = Evaluacion.objects.get()
        self.assertTrue(evaluacion.es_individual())
        self.assertEqual(evaluacion.jugador, self.jugador)
        self.assertEqual(list(evaluacion.jugadores()), [self.jugador])
        self.assertEqual(evaluacion.fecha, HOY)

    def test_queda_marcada_como_la_inicial(self):
        self.tomar()
        evaluacion = Evaluacion.objects.get()

        self.assertIsNotNone(evaluacion.tipo)
        self.assertTrue(evaluacion.tipo.es_inicial)

    def test_abre_todos_los_indicadores_activos(self):
        activos = Indicador.objects.filter(activo=True).count()
        self.tomar()
        self.assertEqual(Evaluacion.objects.get().indicadores.count(), activos)

    def test_puede_ser_de_otro_dia(self):
        hace_una_semana = HOY - timedelta(days=7)
        self.tomar(fecha=hace_una_semana.strftime('%Y-%m-%d'))
        self.assertEqual(Evaluacion.objects.get().fecha, hace_una_semana)

    def test_no_acepta_una_fecha_futura(self):
        respuesta = self.tomar(fecha=(HOY + timedelta(days=3)).strftime('%Y-%m-%d'))
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertEqual(Evaluacion.objects.count(), 0)

    def test_cada_uno_tiene_la_suya_y_en_su_dia(self):
        self.tomar(fecha=(HOY - timedelta(days=10)).strftime('%Y-%m-%d'))
        self.tomar(jugador=self.companiero)

        self.assertEqual(Evaluacion.objects.count(), 2)
        for evaluacion in Evaluacion.objects.all():
            self.assertEqual(list(evaluacion.jugadores()), [evaluacion.jugador])

    def test_se_convierte_en_su_linea_base(self):
        self.tomar()
        evaluacion = Evaluacion.objects.get()
        indicador = evaluacion.indicadores.first()

        self.client.post('/sistema/adm_evaluacion', {
            'action': 'medir', 'evaluacion': evaluacion.id, 'jugador': self.jugador.id,
            'indicador': indicador.id, 'valor': '5',
        })

        base = self.jugador.linea_base()
        self.assertIn(indicador.id, base)
        self.assertEqual(base[indicador.id].valor, Decimal('5'))

    def test_lo_de_despues_se_compara_contra_ella(self):
        self.tomar(fecha=(HOY - timedelta(days=30)).strftime('%Y-%m-%d'))
        ingreso = Evaluacion.objects.get()
        indicador = ingreso.indicadores.filter(tipo_medida=MEDIDA_ESCALA).first()

        Medicion.objects.create(evaluacion=ingreso, jugador=self.jugador,
                                indicador=indicador, valor=Decimal('5'),
                                fecha=ingreso.fecha)

        despues = Evaluacion.objects.create(
            categoria=self.categoria, fecha=HOY, titulo='control del mes')
        despues.indicadores.set([indicador])
        Medicion.objects.create(evaluacion=despues, jugador=self.jugador,
                                indicador=indicador, valor=Decimal('8'), fecha=HOY)

        filas = self.jugador.como_llego_y_como_va()
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['llego'].valor, Decimal('5'))
        self.assertEqual(filas[0]['ahora'].valor, Decimal('8'))
        self.assertTrue(filas[0]['mejoro'])

    def test_sin_indicadores_avisa(self):
        Indicador.objects.all().delete()
        respuesta = self.tomar()
        datos = json.loads(respuesta.content)

        self.assertEqual(datos['result'], 'bad')
        self.assertIn('indicadores', datos['mensaje'])

    def test_sin_tipo_inicial_igual_se_crea(self):
        """Si nadie marco el tipo inicial, la prueba se toma igual."""
        TipoEvaluacion.objects.update(es_inicial=False)
        self.tomar()

        evaluacion = Evaluacion.objects.get()
        self.assertIsNone(evaluacion.tipo)
        # Sin tipo inicial, la base es la primera marca que tenga.
        self.assertEqual(self.jugador.linea_base(), {})

    def test_el_modal_avisa_si_ya_tiene_marcas(self):
        self.tomar()
        evaluacion = Evaluacion.objects.get()
        Medicion.objects.create(evaluacion=evaluacion, jugador=self.jugador,
                                indicador=evaluacion.indicadores.first(), valor=Decimal('6'))

        respuesta = self.client.get(
            '/sistema/adm_evaluacion?action=ingreso&jugador=%s' % self.jugador.id)
        self.assertTrue(respuesta.context['ya_tiene'])

    def test_el_entrenador_puede_tomarsela_a_los_suyos(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.tomar()
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

    def test_pero_no_a_los_de_otro_grupo(self):
        ajeno = Jugador.objects.create(
            nombres='sofia', apellidos='ruiz', fecha_nacimiento=date(2013, 4, 4),
            categoria=self.ajena
        )
        self.client.force_login(self.usuario_entrenador)
        self.tomar(jugador=ajeno)
        self.assertEqual(Evaluacion.objects.count(), 0)
