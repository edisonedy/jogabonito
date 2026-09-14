# coding=utf-8
"""Pruebas de lo del dia a dia: divisiones por edad, pruebas que duran varios
dias, la fecha de pago que viene puesta y desactivar a un jugador.
"""
import json
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase

from jogabonito.models import (
    AREA_TECNICA, MEDIDA_ESCALA, MENSUALIDAD_PAGADO, ROL_ENTRENADOR, Categoria, Division,
    Entrenador, Evaluacion, Indicador, Jugador, Medicion, Mensualidad, PerfilUsuario,
    restar_anios,
)

CLAVE = 'clave-de-prueba-2026'
HOY = date.today()


class BaseDiaADia(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('cargar_base', '--admin-clave', CLAVE, verbosity=0)
        cls.admin = User.objects.get(username='admin')

        cls.usuario_entrenador = User.objects.create_user('profe2', password=CLAVE)
        cls.usuario_entrenador.groups.add(Group.objects.get(name='ENTRENADOR'))
        PerfilUsuario.objects.create(usuario=cls.usuario_entrenador, rol=ROL_ENTRENADOR)
        cls.profe = Entrenador.objects.create(
            nombres='luis', apellidos='mora', telefono='0999999999', usuario=cls.usuario_entrenador
        )

        cls.categoria = Categoria.objects.create(
            nombre='tarde', dias='2,4', hora_inicio=time(15, 0), hora_fin=time(17, 0),
            valor_mensual=Decimal('25.00')
        )
        cls.categoria.entrenadores.add(cls.profe)

        cls.jugador = Jugador.objects.create(
            nombres='pedro', apellidos='vera', fecha_nacimiento=date(2013, 3, 3),
            categoria=cls.categoria
        )

    def crear_de_edad(self, nombre, anios):
        """Un jugador que hoy tiene justo esos anios."""
        return Jugador.objects.create(
            nombres=nombre, apellidos='edad',
            fecha_nacimiento=restar_anios(HOY, anios) + timedelta(days=1),
            categoria=self.categoria
        )


class DivisionPorEdadTest(BaseDiaADia):
    """El grupo dice cuando entrena; la division, contra quien juega."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.sub10 = Division.objects.get(nombre='SUB-10')
        cls.sub14 = Division.objects.get(nombre='SUB-14')

    def test_cada_uno_cae_en_la_suya_por_la_edad(self):
        chico = self.crear_de_edad('chico', 10)
        grande = self.crear_de_edad('grande', 14)

        self.assertEqual(chico.division(), self.sub10)
        self.assertEqual(grande.division(), self.sub14)
        self.assertEqual(chico.division_texto(), 'SUB-10')

    def test_en_el_mismo_grupo_hay_edades_mezcladas(self):
        self.crear_de_edad('chico', 10)
        self.crear_de_edad('grande', 14)

        divisiones = {j.division_texto() for j in self.categoria.jugadores.all()}
        self.assertIn('SUB-10', divisiones)
        self.assertIn('SUB-14', divisiones)

    def test_el_rango_de_nacimiento_filtra_en_la_base(self):
        chico = self.crear_de_edad('chico', 10)
        self.crear_de_edad('grande', 14)

        desde, hasta = self.sub10.rango_de_nacimiento()
        encontrados = Jugador.objects.filter(
            fecha_nacimiento__gte=desde, fecha_nacimiento__lte=hasta)

        self.assertIn(chico, encontrados)
        self.assertEqual(encontrados.count(), 1)

    def test_la_lista_se_puede_filtrar_por_division(self):
        chico = self.crear_de_edad('chico', 10)
        grande = self.crear_de_edad('grande', 14)

        self.client.force_login(self.admin)
        respuesta = self.client.get('/sistema/adm_jugador?division=%s' % self.sub10.id)
        jugadores = list(respuesta.context['jugadores'])

        self.assertIn(chico, jugadores)
        self.assertNotIn(grande, jugadores)

    def test_no_deja_dos_divisiones_que_se_pisen(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_categoria', {
            'action': 'adddivision', 'nombre': 'sub-11', 'edad_minima': 10,
            'edad_maxima': 11, 'orden': 9, 'activo': 'on',
        })
        datos = json.loads(respuesta.content)

        self.assertEqual(datos['result'], 'bad')
        self.assertIn('se cruza', datos['mensaje'])

    def test_se_puede_crear_una_que_no_se_pisa(self):
        Division.objects.all().delete()
        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_categoria', {
            'action': 'adddivision', 'nombre': 'sub-9', 'edad_minima': 8,
            'edad_maxima': 9, 'orden': 1, 'activo': 'on',
        })

        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertEqual(Division.objects.get().nombre, 'SUB-9')

    def test_la_edad_maxima_no_puede_ser_menor(self):
        Division.objects.all().delete()
        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_categoria', {
            'action': 'adddivision', 'nombre': 'rara', 'edad_minima': 12,
            'edad_maxima': 8, 'orden': 1, 'activo': 'on',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')

    def test_el_que_no_entra_en_ninguna_lo_dice(self):
        Division.objects.all().delete()
        self.assertEqual(self.jugador.division_texto(), 'SIN DIVISION')

    def test_el_entrenador_no_puede_tocar_las_divisiones(self):
        self.client.force_login(self.usuario_entrenador)
        self.client.post('/sistema/adm_categoria', {
            'action': 'adddivision', 'nombre': 'suya', 'edad_minima': 30,
            'edad_maxima': 40, 'orden': 20, 'activo': 'on',
        })
        self.assertFalse(Division.objects.filter(nombre='SUYA').exists())


class PruebaEnVariosDiasTest(BaseDiaADia):
    """Al que falto el dia de la prueba se le mide otro dia, con SU fecha."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.control = Indicador.objects.create(
            nombre='control del balon', area=AREA_TECNICA, tipo_medida=MEDIDA_ESCALA, orden=1
        )

    def setUp(self):
        self.prueba = Evaluacion.objects.create(
            categoria=self.categoria, fecha=HOY - timedelta(days=2),
            fecha_fin=HOY + timedelta(days=2), titulo='prueba semanal'
        )
        self.prueba.indicadores.set([self.control])
        self.client.force_login(self.admin)

    def test_sabe_que_dura_varios_dias(self):
        self.assertTrue(self.prueba.dura_varios_dias())
        self.assertTrue(self.prueba.abarca(HOY))
        self.assertFalse(self.prueba.abarca(HOY + timedelta(days=5)))
        self.assertIn(' al ', self.prueba.texto_fechas())

    def test_al_que_se_le_mide_hoy_le_queda_hoy(self):
        self.client.post('/sistema/adm_evaluacion', {
            'action': 'medir', 'evaluacion': self.prueba.id, 'jugador': self.jugador.id,
            'indicador': self.control.id, 'valor': '8',
        })

        medicion = Medicion.objects.get()
        self.assertEqual(medicion.fecha, HOY)
        self.assertEqual(medicion.dia(), HOY)

    def test_si_la_prueba_ya_paso_queda_con_el_dia_en_que_arranco(self):
        vieja = Evaluacion.objects.create(
            categoria=self.categoria, fecha=HOY - timedelta(days=20), titulo='prueba vieja'
        )
        vieja.indicadores.set([self.control])

        self.client.post('/sistema/adm_evaluacion', {
            'action': 'medir', 'evaluacion': vieja.id, 'jugador': self.jugador.id,
            'indicador': self.control.id, 'valor': '7',
        })
        self.assertEqual(Medicion.objects.get().fecha, vieja.fecha)

    def test_sin_fecha_propia_vale_la_de_la_prueba(self):
        medicion = Medicion.objects.create(
            evaluacion=self.prueba, jugador=self.jugador, indicador=self.control,
            valor=Decimal('6')
        )
        self.assertEqual(medicion.dia(), self.prueba.fecha)

    def test_el_progreso_ordena_por_el_dia_real(self):
        otra = Evaluacion.objects.create(
            categoria=self.categoria, fecha=HOY - timedelta(days=10), titulo='anterior'
        )
        otra.indicadores.set([self.control])

        Medicion.objects.create(evaluacion=otra, jugador=self.jugador,
                                indicador=self.control, valor=Decimal('5'))
        Medicion.objects.create(evaluacion=self.prueba, jugador=self.jugador,
                                indicador=self.control, valor=Decimal('9'), fecha=HOY)

        fila = self.jugador.progreso()[0]
        self.assertEqual(fila['primera'].valor, Decimal('5'))
        self.assertEqual(fila['ultima'].valor, Decimal('9'))
        self.assertEqual(fila['ultima'].dia(), HOY)

    def test_no_acepta_que_termine_antes_de_empezar(self):
        respuesta = self.client.post('/sistema/adm_evaluacion', {
            'action': 'add', 'categoria': self.categoria.id,
            'fecha': HOY.strftime('%Y-%m-%d'),
            'fecha_fin': (HOY - timedelta(days=3)).strftime('%Y-%m-%d'),
            'titulo': 'al reves', 'indicadores': [self.control.id],
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')

    def test_se_puede_crear_con_rango(self):
        respuesta = self.client.post('/sistema/adm_evaluacion', {
            'action': 'add', 'categoria': self.categoria.id,
            'fecha': (HOY - timedelta(days=1)).strftime('%Y-%m-%d'),
            'fecha_fin': HOY.strftime('%Y-%m-%d'),
            'titulo': 'con rango', 'indicadores': [self.control.id],
        })

        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertTrue(Evaluacion.objects.get(titulo='con rango').dura_varios_dias())

    def test_la_prueba_de_un_solo_dia_sigue_igual(self):
        suelta = Evaluacion.objects.create(
            categoria=self.categoria, fecha=HOY, titulo='de un dia'
        )
        self.assertFalse(suelta.dura_varios_dias())
        self.assertEqual(suelta.ultimo_dia(), HOY)
        self.assertEqual(suelta.texto_fechas(), HOY.strftime('%d/%m/%Y'))


class DetallesDelDiaADiaTest(BaseDiaADia):
    """La fecha de pago que viene puesta y el boton de desactivar."""

    def test_el_cobro_viene_con_la_fecha_de_hoy(self):
        from jogabonito.forms import MensualidadForm

        mensualidad = Mensualidad.objects.create(
            jugador=self.jugador, mes=HOY.month, anio=HOY.year, valor=Decimal('25.00'),
            fecha_vencimiento=HOY, periodo_inicio=HOY, periodo_fin=HOY + timedelta(days=29)
        )
        form = MensualidadForm(instance=mensualidad)
        self.assertEqual(form.initial['fecha_pago'], HOY)

    def test_si_ya_tiene_fecha_de_pago_se_respeta(self):
        from jogabonito.forms import MensualidadForm

        ayer = HOY - timedelta(days=1)
        mensualidad = Mensualidad.objects.create(
            jugador=self.jugador, mes=HOY.month, anio=HOY.year, valor=Decimal('25.00'),
            fecha_vencimiento=HOY, estado=MENSUALIDAD_PAGADO, fecha_pago=ayer
        )
        form = MensualidadForm(instance=mensualidad)
        self.assertEqual(form.initial['fecha_pago'], ayer)

    def test_se_desactiva_al_jugador_desde_la_lista(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_jugador', {
            'action': 'estado', 'id': self.jugador.id, 'estado': 2,
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        self.jugador.refresh_from_db()
        self.assertEqual(self.jugador.estado, 2)
        self.assertFalse(self.jugador.se_le_cobra())

    def test_se_vuelve_a_activar(self):
        self.jugador.estado = 2
        self.jugador.save()

        self.client.force_login(self.admin)
        self.client.post('/sistema/adm_jugador', {
            'action': 'estado', 'id': self.jugador.id, 'estado': 1,
        })
        self.jugador.refresh_from_db()
        self.assertTrue(self.jugador.se_le_cobra())

    def test_el_entrenador_no_puede_desactivar(self):
        self.client.force_login(self.usuario_entrenador)
        self.client.post('/sistema/adm_jugador', {
            'action': 'estado', 'id': self.jugador.id, 'estado': 2,
        })
        self.jugador.refresh_from_db()
        self.assertEqual(self.jugador.estado, 1)
