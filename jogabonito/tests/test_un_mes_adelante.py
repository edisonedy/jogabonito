# coding=utf-8
"""De un clic solo se adelanta UN mes.

Estando en septiembre lo que se abre es octubre. Si octubre ya esta abierto,
el boton avisa en vez de crear noviembre: cobrarle dos meses adelante casi
siempre es un dedazo. Con fechas a mano (el boton "+") si se puede, porque
ahi es a proposito.
"""
import json
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from jogabonito.models import Categoria, Jugador, Mensualidad

CLAVE = 'clave-de-prueba-2026'
HOY = date.today()


class UnMesAdelanteTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command('cargar_base', '--admin-clave', CLAVE, verbosity=0)
        cls.admin = User.objects.get(username='admin')

        cls.categoria = Categoria.objects.create(
            nombre='noche', dias='2,4', hora_inicio=time(18, 0), hora_fin=time(20, 0),
            valor_mensual=Decimal('25.00')
        )
        # Entro hace dos meses: tiene su mes corriendo y le toca el siguiente.
        cls.jugador = Jugador.objects.create(
            nombres='ana', apellidos='pena', fecha_nacimiento=date(2012, 4, 10),
            categoria=cls.categoria, fecha_ingreso=HOY - timedelta(days=60)
        )

    def setUp(self):
        self.client.force_login(self.admin)
        # Al entrar al modulo se abren solos los meses vencidos.
        self.client.get('/sistema/adm_mensualidad')

    def siguiente(self):
        return self.client.post('/sistema/adm_mensualidad',
                                {'action': 'siguiente', 'id': self.jugador.id})

    def test_el_primer_clic_abre_el_mes_que_sigue(self):
        antes = self.jugador.mensualidades.count()
        respuesta = self.siguiente()

        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertEqual(self.jugador.mensualidades.count(), antes + 1)

        adelantado = self.jugador.mes_ya_adelantado()
        self.assertIsNotNone(adelantado)
        self.assertGreater(adelantado.periodo_inicio, HOY)

    def test_el_segundo_clic_avisa_en_vez_de_cobrar_dos_meses(self):
        self.siguiente()
        cuantas = self.jugador.mensualidades.count()

        respuesta = self.siguiente()
        datos = json.loads(respuesta.content)

        self.assertEqual(datos['result'], 'bad')
        self.assertIn('ya se le abrio el mes que sigue', datos['mensaje'])
        self.assertIn('"+"', datos['mensaje'])
        self.assertEqual(self.jugador.mensualidades.count(), cuantas)

    def test_a_mano_si_se_puede_ir_mas_adelante(self):
        """El que quiere cobrar dos meses por adelantado, lo hace a proposito."""

        self.siguiente()
        adelantado = self.jugador.mes_ya_adelantado()
        desde = adelantado.periodo_fin + timedelta(days=1)
        hasta = desde + timedelta(days=29)

        respuesta = self.client.post('/sistema/adm_mensualidad', {
            'action': 'add', 'jugador': self.jugador.id,
            'periodo_inicio': desde.strftime('%Y-%m-%d'),
            'periodo_fin': hasta.strftime('%Y-%m-%d'),
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertTrue(
            Mensualidad.objects.filter(jugador=self.jugador, periodo_inicio=desde).exists())

    def test_el_boton_se_apaga_en_la_ficha(self):
        respuesta = self.client.get('/sistema/adm_jugador?action=view&id=%s' % self.jugador.id)
        self.assertIsNone(respuesta.context['mes_adelantado'])

        self.siguiente()

        respuesta = self.client.get('/sistema/adm_jugador?action=view&id=%s' % self.jugador.id)
        self.assertIsNotNone(respuesta.context['mes_adelantado'])
        self.assertContains(respuesta, 'Siguiente mes listo')

    def test_el_cobro_automatico_no_adelanta_meses(self):
        """Lo que se abre solo es lo vencido, nunca lo que todavia no empieza."""
        self.client.post('/sistema/adm_mensualidad', {'action': 'aldia'})

        self.assertIsNone(self.jugador.mes_ya_adelantado())

    def test_si_el_mes_adelantado_ya_empezo_se_puede_abrir_el_siguiente(self):
        """Cuando llega la fecha deja de contar como adelantado."""
        self.siguiente()
        adelantado = self.jugador.mes_ya_adelantado()

        # Ese mes ya arranco: ahora es el mes que corre, no uno adelantado.
        self.assertIsNone(self.jugador.mes_ya_adelantado(adelantado.periodo_inicio))
