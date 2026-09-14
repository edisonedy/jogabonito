# coding=utf-8
"""Pruebas de acceso: cada rol solo ve y modifica lo que le corresponde."""
import json
from datetime import date, time

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase

from jogabonito.models import (
    ROL_ADMINISTRADOR, ROL_ENTRENADOR, Categoria, Entrenador, Jugador, Modulo, PerfilUsuario,
)

CLAVE = 'clave-de-prueba-2026'


class BaseSeguridad(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('cargar_base', '--admin-clave', CLAVE, verbosity=0)

        cls.admin = User.objects.get(username='admin')

        # Entrenador con acceso al sistema.
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

        cls.mi_jugador = Jugador.objects.create(
            nombres='pedro', apellidos='vera', fecha_nacimiento=date(2013, 3, 3), categoria=cls.mi_categoria
        )
        cls.jugador_ajeno = Jugador.objects.create(
            nombres='sofia', apellidos='ruiz', fecha_nacimiento=date(2013, 4, 4), categoria=cls.otra_categoria
        )


class AccesoAnonimoTest(BaseSeguridad):
    def test_el_panel_exige_login(self):
        respuesta = self.client.get('/sistema/')
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/sistema/login/', respuesta['Location'])

    def test_los_modulos_exigen_login(self):
        for url in ('/sistema/adm_jugador', '/sistema/adm_categoria',
                    '/sistema/adm_entrenador', '/sistema/adm_representante'):
            respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 302, url)
            self.assertIn('/sistema/login/', respuesta['Location'], url)

    def test_post_anonimo_no_crea_nada(self):
        respuesta = self.client.post('/sistema/adm_categoria', {'action': 'add', 'nombre': 'PIRATA'})
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Categoria.objects.filter(nombre='PIRATA').exists())


class AdministradorTest(BaseSeguridad):
    def setUp(self):
        self.client.force_login(self.admin)

    def test_ve_los_cuatro_modulos_en_el_panel(self):
        respuesta = self.client.get('/sistema/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context['mismodulos']), Modulo.objects.filter(activo=True).count())

    def test_crea_un_jugador(self):
        respuesta = self.client.post('/sistema/adm_jugador', {
            'action': 'add',
            'nombre1': 'carlos',
            'nombre2': 'andres',
            'apellido1': 'jimenez',
            'apellido2': 'vaca',
            'cedula': '',
            'fecha_nacimiento': '2014-02-10',
            'fecha_ingreso': '2026-01-15',
            'categoria': self.mi_categoria.id,
            'estado': 1,
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        creado = Jugador.objects.get(apellido1='JIMENEZ')
        self.assertEqual(creado.nombres, 'CARLOS ANDRES')
        self.assertEqual(creado.apellidos, 'JIMENEZ VACA')
        self.assertEqual(creado.nombre_completo(), 'JIMENEZ VACA CARLOS ANDRES')

    def test_no_elimina_una_categoria_con_jugadores(self):
        respuesta = self.client.post('/sistema/adm_categoria', {
            'action': 'delete', 'id': self.mi_categoria.id
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertTrue(Categoria.objects.filter(pk=self.mi_categoria.pk).exists())

    def test_rechaza_una_categoria_con_horario_invertido(self):
        respuesta = self.client.post('/sistema/adm_categoria', {
            'action': 'add', 'nombre': 'INVERTIDA',
            'hora_inicio': '18:00', 'hora_fin': '17:00', 'valor_mensual': '25',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.assertFalse(Categoria.objects.filter(nombre='INVERTIDA').exists())


class EntrenadorTest(BaseSeguridad):
    def setUp(self):
        self.client.force_login(self.usuario_entrenador)

    def test_solo_ve_los_modulos_de_su_rol(self):
        from jogabonito.management.commands.cargar_base import MODULOS_ENTRENADOR
        respuesta = self.client.get('/sistema/')
        urls = sorted(m.url for m in respuesta.context['mismodulos'])
        self.assertEqual(urls, sorted(MODULOS_ENTRENADOR))

    def test_no_entra_a_los_modulos_del_administrador(self):
        for url in ('/sistema/adm_categoria', '/sistema/adm_entrenador', '/sistema/adm_representante',
                    '/sistema/adm_solicitud', '/sistema/adm_indicador'):
            respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 302, url)
            self.assertEqual(respuesta['Location'], '/sistema/', url)

    def test_no_entra_al_modulo_de_jugadores(self):
        """Su trabajo es tomar lista y medir; las fichas son del administrador."""
        respuesta = self.client.get('/sistema/adm_jugador')
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], '/sistema/')

    def test_no_entra_a_la_plata_ni_a_los_turnos(self):
        for url in ('/sistema/adm_mensualidad', '/sistema/adm_turno', '/sistema/dashboard'):
            respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 302, url)

    def test_sigue_viendo_solo_a_sus_jugadores(self):
        """El alcance por categoria no cambia: se revisa donde el si entra."""
        respuesta = self.client.get('/sistema/adm_asistencia?categoria=%s' % self.mi_categoria.id)
        self.assertEqual(respuesta.status_code, 200)

        nombres = [f['jugador'].nombre_completo() for f in respuesta.context['filas']]
        self.assertIn('VERA PEDRO', nombres)
        self.assertNotIn('RUIZ SOFIA', nombres)

    def test_no_abre_el_progreso_de_un_jugador_de_otra_categoria(self):
        """IDOR: aunque mande el id a mano, no debe recibir sus datos."""
        respuesta = self.client.get(
            '/sistema/adm_evaluacion?action=progreso&id=%s' % self.jugador_ajeno.id)
        # url_back devuelve la misma ruta, sin datos del jugador ajeno.
        self.assertNotContains(respuesta, 'RUIZ SOFIA')
        self.assertIsNone(respuesta.context)

    def test_si_abre_el_progreso_de_su_jugador(self):
        respuesta = self.client.get(
            '/sistema/adm_evaluacion?action=progreso&id=%s' % self.mi_jugador.id)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'VERA PEDRO')

    def test_no_puede_crear_jugadores(self):
        respuesta = self.client.post('/sistema/adm_jugador', {
            'action': 'add', 'nombres': 'intruso', 'apellidos': 'intruso',
            'fecha_nacimiento': '2014-01-01', 'fecha_ingreso': '2026-01-01',
            'categoria': self.mi_categoria.id, 'estado': 1,
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Jugador.objects.filter(apellidos='INTRUSO').exists())

    def test_no_puede_eliminar_a_un_jugador(self):
        respuesta = self.client.post('/sistema/adm_jugador',
                                     {'action': 'delete', 'id': self.mi_jugador.id})
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Jugador.objects.filter(pk=self.mi_jugador.pk).exists())

    def test_si_puede_anotar_y_medir_a_los_suyos(self):
        """Las notas y las medidas viven en evaluaciones, que si tiene."""
        respuesta = self.client.post('/sistema/adm_evaluacion', {
            'action': 'nota', 'jugador': self.mi_jugador.id,
            'fecha': date.today().strftime('%Y-%m-%d'), 'tipo': 1,
            'texto': 'lo vi bien parado en la cancha',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

    def test_pero_no_a_los_de_otro_grupo(self):
        respuesta = self.client.post('/sistema/adm_evaluacion', {
            'action': 'nota', 'jugador': self.jugador_ajeno.id,
            'fecha': date.today().strftime('%Y-%m-%d'), 'tipo': 1,
            'texto': 'no deberia poder anotarle',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')


class PerfilInactivoTest(BaseSeguridad):
    def test_un_perfil_desactivado_no_entra(self):
        perfil = PerfilUsuario.objects.get(usuario=self.usuario_entrenador)
        perfil.activo = False
        perfil.save()

        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/')
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/sistema/login/', respuesta['Location'])


class CargarBaseTest(TestCase):
    def test_crea_modulos_grupos_y_administrador(self):
        call_command('cargar_base', '--admin-clave', CLAVE, verbosity=0)

        from jogabonito.management.commands.cargar_base import MODULOS
        self.assertEqual(Modulo.objects.count(), len(MODULOS))
        self.assertTrue(Group.objects.filter(name='ADMINISTRADOR').exists())
        self.assertTrue(Group.objects.filter(name='ENTRENADOR').exists())

        admin = User.objects.get(username='admin')
        self.assertTrue(admin.is_superuser)
        self.assertEqual(PerfilUsuario.objects.get(usuario=admin).rol, ROL_ADMINISTRADOR)
