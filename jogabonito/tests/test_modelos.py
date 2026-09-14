# coding=utf-8
from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from jogabonito.funciones import validar_cedula
from jogabonito.models import Categoria, Entrenador, Jugador, Representante


class RequestFalso:
    def __init__(self, usuario):
        self.user = usuario


class ModeloBaseTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('tester', password='clave12345')

    def test_save_con_request_guarda_auditoria(self):
        categoria = Categoria(nombre='manana', hora_inicio=time(7, 0), hora_fin=time(9, 0))
        categoria.save(RequestFalso(self.usuario))

        categoria.refresh_from_db()
        self.assertEqual(categoria.usuario_creacion_id, self.usuario.id)
        self.assertIsNotNone(categoria.fecha_creacion)
        self.assertIsNone(categoria.usuario_modificacion_id)

    def test_save_de_actualizacion_no_duplica_el_registro(self):
        """save(request) sobre un registro existente debe hacer UPDATE, no INSERT."""
        categoria = Categoria(nombre='tarde', hora_inicio=time(15, 0), hora_fin=time(17, 0))
        categoria.save(RequestFalso(self.usuario))

        categoria.valor_mensual = Decimal('30.00')
        categoria.save(RequestFalso(self.usuario))

        self.assertEqual(Categoria.objects.count(), 1)
        categoria.refresh_from_db()
        self.assertEqual(categoria.usuario_modificacion_id, self.usuario.id)


class CategoriaTest(TestCase):
    def test_nombre_se_guarda_en_mayusculas(self):
        categoria = Categoria.objects.create(nombre='sub 12 manana', hora_inicio=time(7, 0), hora_fin=time(9, 0))
        self.assertEqual(categoria.nombre, 'SUB 12 MANANA')

    def test_dias_se_normalizan_y_descartan_basura(self):
        categoria = Categoria.objects.create(
            nombre='noche', dias='5,1,1,99,x,3', hora_inicio=time(18, 0), hora_fin=time(20, 0)
        )
        self.assertEqual(categoria.dias, '1,3,5')
        self.assertEqual(categoria.dias_nombres(), ['Lunes', 'Miercoles', 'Viernes'])

    def test_entrena_hoy(self):
        categoria = Categoria.objects.create(
            nombre='lunes', dias='1', hora_inicio=time(7, 0), hora_fin=time(9, 0)
        )
        self.assertTrue(categoria.entrena_hoy(date(2026, 9, 7)))   # lunes
        self.assertFalse(categoria.entrena_hoy(date(2026, 9, 8)))  # martes


class JugadorTest(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(
            nombre='manana', dias='1,3', hora_inicio=time(7, 0), hora_fin=time(9, 0),
            valor_mensual=Decimal('25.00')
        )

    def crear_jugador(self, **extra):
        datos = dict(
            nombres='juan carlos', apellidos='perez lopez',
            fecha_nacimiento=date(2014, 5, 20), categoria=self.categoria
        )
        datos.update(extra)
        return Jugador.objects.create(**datos)

    def test_nombre_completo_en_mayusculas(self):
        jugador = self.crear_jugador()
        self.assertEqual(jugador.nombre_completo(), 'PEREZ LOPEZ JUAN CARLOS')

    def test_edad_se_calcula_a_una_fecha(self):
        jugador = self.crear_jugador()
        self.assertEqual(jugador.edad(date(2026, 5, 19)), 11)
        self.assertEqual(jugador.edad(date(2026, 5, 20)), 12)

    def test_valor_mensual_toma_el_de_la_categoria(self):
        jugador = self.crear_jugador()
        self.assertEqual(jugador.valor_mensual_vigente(), Decimal('25.00'))

    def test_el_descuento_del_jugador_baja_el_valor(self):
        jugador = self.crear_jugador(descuento=Decimal('40.00'),
                                     motivo_descuento='hermano en la academia')
        self.assertEqual(jugador.valor_mensual_vigente(), Decimal('15.00'))

    def test_representante_puede_tener_varios_jugadores(self):
        representante = Representante.objects.create(
            nombres='maria', apellidos='lopez', telefono='0987654321'
        )
        self.crear_jugador(representante=representante)
        self.crear_jugador(nombres='ana', apellidos='perez lopez', representante=representante)
        self.assertEqual(representante.total_jugadores(), 2)


class EntrenadorTest(TestCase):
    def test_total_jugadores_cuenta_solo_activos_de_sus_categorias(self):
        entrenador = Entrenador.objects.create(nombres='luis', apellidos='mora', telefono='0999999999')
        categoria = Categoria.objects.create(nombre='tarde', hora_inicio=time(15, 0), hora_fin=time(17, 0))
        categoria.entrenadores.add(entrenador)

        Jugador.objects.create(nombres='a', apellidos='a', fecha_nacimiento=date(2012, 1, 1), categoria=categoria)
        Jugador.objects.create(nombres='b', apellidos='b', fecha_nacimiento=date(2012, 1, 1),
                               categoria=categoria, estado=3)

        self.assertEqual(entrenador.total_jugadores(), 1)


class CedulaTest(TestCase):
    def test_cedulas_validas_e_invalidas(self):
        self.assertTrue(validar_cedula('1804822797'))
        self.assertFalse(validar_cedula('1804822798'))
        self.assertFalse(validar_cedula('123'))
        self.assertFalse(validar_cedula('abcdefghij'))
