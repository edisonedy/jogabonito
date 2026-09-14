# coding=utf-8
"""Pruebas de la pagina publica y de las solicitudes de inscripcion (FASE 5)."""
import json
from datetime import date, time

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase, override_settings

from jogabonito.models import (
    ROL_ENTRENADOR, SOLICITUD_CONTACTADO, SOLICITUD_NUEVA, Categoria, Entrenador, Jugador,
    PerfilUsuario, SolicitudInscripcion,
)

CLAVE = 'clave-de-prueba-2026'


class BaseLanding(TestCase):
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
            nombre='manana', dias='1,3,5', hora_inicio=time(7, 0), hora_fin=time(9, 0), valor_mensual=25
        )
        cls.inactiva = Categoria.objects.create(
            nombre='grupo cerrado', dias='6', hora_inicio=time(10, 0), hora_fin=time(11, 0), activo=False
        )
        cls.jugador = Jugador.objects.create(
            nombres='pedro', apellidos='vera', fecha_nacimiento=date(2013, 3, 3), categoria=cls.categoria
        )

    def datos(self, **extra):
        valores = {
            'nombre': 'Juan Perez',
            'telefono': '0987654321',
            'edad': 11,
            'categoria': self.categoria.id,
            'mensaje': 'Quiero informacion',
            'apellido_confirmacion': '',
        }
        valores.update(extra)
        return valores


class PaginaPublicaTest(BaseLanding):
    def test_la_landing_abre_sin_login(self):
        respuesta = self.client.get('/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, 'landing/index.html')

    def test_muestra_academia_director_y_fortalezas(self):
        respuesta = self.client.get('/')
        self.assertContains(respuesta, 'Joga Bonito')
        self.assertContains(respuesta, 'Kevyn Supe')
        self.assertContains(respuesta, 'ATFA')
        self.assertEqual(len(respuesta.context['fortalezas']), 6)

    def test_solo_lista_las_categorias_activas(self):
        respuesta = self.client.get('/')
        nombres = [c.nombre for c in respuesta.context['categorias']]
        self.assertIn('MANANA', nombres)
        self.assertNotIn('GRUPO CERRADO', nombres)

    def test_no_publica_datos_de_los_jugadores(self):
        """La pagina es publica: no puede exponer nombres de ninos."""
        respuesta = self.client.get('/')
        self.assertNotContains(respuesta, 'VERA PEDRO')
        self.assertNotContains(respuesta, 'PEDRO')


class SolicitudPublicaTest(BaseLanding):
    def test_envia_una_solicitud_valida(self):
        respuesta = self.client.post('/', self.datos())

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context['enviado'])

        solicitud = SolicitudInscripcion.objects.get()
        self.assertEqual(solicitud.nombre, 'JUAN PEREZ')
        self.assertEqual(solicitud.estado, SOLICITUD_NUEVA)
        self.assertEqual(solicitud.categoria, self.categoria)
        self.assertIsNotNone(solicitud.origen_ip)

    def test_la_solicitud_puede_no_indicar_horario(self):
        self.client.post('/', self.datos(categoria=''))
        self.assertIsNone(SolicitudInscripcion.objects.get().categoria)

    def test_rechaza_una_edad_imposible(self):
        respuesta = self.client.post('/', self.datos(edad=150))
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(SolicitudInscripcion.objects.count(), 0)

    def test_rechaza_un_nombre_vacio(self):
        respuesta = self.client.post('/', self.datos(nombre='  '))
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(SolicitudInscripcion.objects.count(), 0)

    def test_rechaza_un_telefono_invalido(self):
        respuesta = self.client.post('/', self.datos(telefono='no-es-telefono'))
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(SolicitudInscripcion.objects.count(), 0)

    def test_el_campo_trampa_frena_a_los_robots(self):
        respuesta = self.client.post('/', self.datos(apellido_confirmacion='robot'))
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(SolicitudInscripcion.objects.count(), 0)

    @override_settings(SOLICITUDES_MAXIMAS_POR_HORA=2)
    def test_frena_el_spam_desde_la_misma_ip(self):
        self.client.post('/', self.datos())
        self.client.post('/', self.datos(nombre='Otro Nombre'))
        respuesta = self.client.post('/', self.datos(nombre='Tercer Nombre'))

        self.assertEqual(respuesta.status_code, 429)
        self.assertEqual(SolicitudInscripcion.objects.count(), 2)

    def test_el_numero_de_whatsapp_se_normaliza(self):
        self.client.post('/', self.datos(telefono='0987654321'))
        self.assertEqual(SolicitudInscripcion.objects.get().numero_whatsapp(), '593987654321')


class ModuloSolicitudesTest(BaseLanding):
    def setUp(self):
        self.solicitud = SolicitudInscripcion.objects.create(
            nombre='ANA LOPEZ', telefono='0987111222', edad=9, categoria=self.categoria
        )

    def test_el_administrador_ve_el_listado(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get('/sistema/adm_solicitud')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['total_nuevas'], 1)

    def test_el_entrenador_no_entra(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.get('/sistema/adm_solicitud')
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], '/sistema/')

    def test_anonimo_no_entra(self):
        respuesta = self.client.get('/sistema/adm_solicitud')
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/sistema/login/', respuesta['Location'])

    def test_el_administrador_cambia_el_estado(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_solicitud', {
            'action': 'estado', 'id': self.solicitud.id,
            'estado': SOLICITUD_CONTACTADO, 'nota_interna': 'llamada el lunes',
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')

        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, SOLICITUD_CONTACTADO)
        self.assertEqual(self.solicitud.nota_interna, 'llamada el lunes')
        self.assertEqual(self.solicitud.usuario_modificacion, self.admin)

    def test_no_acepta_un_estado_inventado(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_solicitud', {
            'action': 'estado', 'id': self.solicitud.id, 'estado': 77,
        })
        self.assertEqual(json.loads(respuesta.content)['result'], 'bad')
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, SOLICITUD_NUEVA)

    def test_el_entrenador_no_puede_cambiar_estados(self):
        self.client.force_login(self.usuario_entrenador)
        respuesta = self.client.post('/sistema/adm_solicitud', {
            'action': 'estado', 'id': self.solicitud.id, 'estado': SOLICITUD_CONTACTADO,
        })
        self.assertIn(respuesta.status_code, (302, 200))
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, SOLICITUD_NUEVA)

    def test_el_administrador_elimina_una_solicitud(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post('/sistema/adm_solicitud',
                                     {'action': 'delete', 'id': self.solicitud.id})
        self.assertEqual(json.loads(respuesta.content)['result'], 'ok')
        self.assertEqual(SolicitudInscripcion.objects.count(), 0)


class CreditoDesarrolladorTest(BaseLanding):
    def test_la_landing_muestra_quien_desarrolla_el_sistema(self):
        respuesta = self.client.get('/')
        self.assertContains(respuesta, 'Sistema desarrollado por')
        self.assertContains(respuesta, 'HORUS')

    def test_el_login_tambien_lo_muestra(self):
        respuesta = self.client.get('/sistema/login/')
        self.assertContains(respuesta, 'HORUS')

    def test_el_sistema_lo_muestra_en_el_sidebar(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get('/sistema/')
        self.assertContains(respuesta, 'Desarrollado por')
        self.assertContains(respuesta, 'HORUS')

    @override_settings(DESARROLLADOR_NOMBRE='')
    def test_sin_nombre_el_credito_desaparece(self):
        respuesta = self.client.get('/')
        self.assertNotContains(respuesta, 'Sistema desarrollado por')


class IdentidadVisualTest(BaseLanding):
    def test_muestra_los_cuatro_valores_de_la_academia(self):
        respuesta = self.client.get('/')
        for valor in ('Disciplina', 'Respeto', 'Trabajo en equipo', 'Pasion'):
            self.assertContains(respuesta, valor)

    def test_muestra_el_cuerpo_tecnico_activo(self):
        respuesta = self.client.get('/')
        self.assertContains(respuesta, 'Mora Luis')
        self.assertEqual(respuesta.context['total_entrenadores'], 1)

    def test_no_publica_el_telefono_de_los_entrenadores(self):
        """El cuerpo tecnico sale con nombre y foto, nada mas."""
        respuesta = self.client.get('/')
        self.assertNotContains(respuesta, '0999999999')

    def test_no_habla_de_aniversario(self):
        """El usuario pidio no publicar aniversario: no sabemos la fecha."""
        respuesta = self.client.get('/')
        self.assertNotContains(respuesta, 'niversario')
