# coding=utf-8
"""El comando que deja la base lista en un servidor recien instalado.

Es la prueba que importa para el despliegue: sobre una base VACIA tiene que
dejar el sistema usable, y correrlo dos veces no puede duplicar nada.
"""
import io
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from jogabonito.models import (
    Asistencia, Categoria, ControlFisico, Entrenador, Evaluacion, Indicador, Jugador,
    Medicion, Mensualidad, Modulo, Nota, Posicion,
)

CLAVE = 'clave-de-prueba-2026'


class SembrarTodoTest(TestCase):
    """Se corre sobre la base vacia de cada test: es el caso del servidor."""

    def sembrar(self, **extra):
        salida = io.StringIO()
        call_command('sembrar_todo', admin_clave=CLAVE, stdout=salida, **extra)
        return salida.getvalue()

    def test_deja_el_sistema_usable_desde_cero(self):
        self.sembrar()

        # Lo que hace falta para entrar y moverse.
        self.assertTrue(Modulo.objects.exists())
        self.assertTrue(User.objects.filter(username='admin').exists())

        # Los catalogos con que se trabaja.
        self.assertEqual(Posicion.objects.filter(activo=True).count(), 17)
        self.assertTrue(Indicador.objects.count() >= 30)

        # La academia de verdad.
        self.assertTrue(Categoria.objects.filter(nombre='NOCHE').exists())
        self.assertTrue(Entrenador.objects.filter(apellidos='SUPE').exists())
        self.assertEqual(Jugador.objects.count(), 3)

    def test_trae_datos_para_probar_todas_las_pantallas(self):
        self.sembrar()

        self.assertTrue(Evaluacion.objects.exists(), 'sin pruebas no hay tela de arania')
        self.assertTrue(Medicion.objects.exists())
        self.assertTrue(Asistencia.objects.exists(), 'sin asistencias no hay historial')
        self.assertTrue(Mensualidad.objects.exists())
        self.assertTrue(Nota.objects.exists())

        # El que lleva mas tiempo tiene historial largo y debe el mes de ahora.
        christian = Jugador.objects.get(nombre1='CHRISTIAN')
        self.assertGreaterEqual(christian.mensualidades.count(), 6)
        self.assertGreater(christian.asistencias.count(), 40)
        self.assertGreater(christian.total_que_debe(), 0)

        # Y tiene meses con rebaja, que es lo que hay que poder revisar.
        self.assertTrue(
            [m for m in christian.mensualidades.all() if m.tiene_descuento()],
            'deberia quedar algun mes con descuento para probarlo'
        )

    def test_correrlo_dos_veces_no_duplica_nada(self):
        self.sembrar()
        cuentas = {
            'jugadores': Jugador.objects.count(),
            'pruebas': Evaluacion.objects.count(),
            'mediciones': Medicion.objects.count(),
            'asistencias': Asistencia.objects.count(),
            'mensualidades': Mensualidad.objects.count(),
            'notas': Nota.objects.count(),
            'posiciones': Posicion.objects.count(),
        }

        self.sembrar()

        self.assertEqual(Jugador.objects.count(), cuentas['jugadores'])
        self.assertEqual(Evaluacion.objects.count(), cuentas['pruebas'])
        self.assertEqual(Medicion.objects.count(), cuentas['mediciones'])
        self.assertEqual(Asistencia.objects.count(), cuentas['asistencias'])
        self.assertEqual(Mensualidad.objects.count(), cuentas['mensualidades'])
        self.assertEqual(Nota.objects.count(), cuentas['notas'])
        self.assertEqual(Posicion.objects.count(), cuentas['posiciones'])

    def test_kevyn_entra_con_su_propio_usuario(self):
        """Es el duenio y ademas entrena: entra como administrador."""
        self.sembrar(clave_kevyn='kevinsupe')

        self.assertTrue(self.client.login(username='ksupe', password='kevinsupe'))

        kevyn = User.objects.get(username='ksupe')
        self.assertTrue(kevyn.perfil.es_administrador())
        self.assertEqual(Entrenador.objects.get(apellidos='SUPE').usuario, kevyn)

        # Y ve lo que un entrenador no ve: la plata.
        self.assertEqual(self.client.get('/sistema/adm_mensualidad').status_code, 200)

    def test_sin_clave_no_se_le_inventa_acceso_a_kevyn(self):
        self.sembrar()
        self.assertFalse(User.objects.filter(username='ksupe').exists())

    def test_correrlo_otro_dia_tampoco_duplica(self):
        """Las notas y las medidas van contadas desde hoy: si el comando se
        corre maniana caerian en fechas nuevas. No deben repetirse."""
        self.sembrar()
        notas = Nota.objects.count()
        controles = ControlFisico.objects.count()

        with patch('jogabonito.management.commands.cargar_academia.HOY',
                   date.today() + timedelta(days=40)):
            self.sembrar()

        self.assertEqual(Nota.objects.count(), notas)
        self.assertEqual(ControlFisico.objects.count(), controles)

    def test_el_resumen_dice_como_quedo(self):
        salida = self.sembrar()
        self.assertIn('Asi quedo la base', salida)
        self.assertIn('Deuda total de la academia', salida)

    def test_se_puede_entrar_con_la_clave_que_se_le_dio(self):
        self.sembrar()
        self.assertTrue(self.client.login(username='admin', password=CLAVE))

    def test_el_administrador_abre_las_pantallas_con_esos_datos(self):
        """Lo sembrado tiene que poder verse, no solo estar en la base."""
        self.sembrar()
        self.client.login(username='admin', password=CLAVE)

        christian = Jugador.objects.get(nombre1='CHRISTIAN')
        for url in [
            '/sistema/',
            '/sistema/adm_jugador',
            '/sistema/adm_jugador?action=view&id=%s' % christian.id,
            '/sistema/adm_mensualidad',
            '/sistema/adm_mensualidad?action=historial&id=%s' % christian.id,
            '/sistema/adm_mensualidad?action=proximos',
            '/sistema/adm_asistencia?action=todas',
            '/sistema/adm_asistencia?action=historial&id=%s' % christian.id,
        ]:
            respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 200, 'no abrio %s' % url)
