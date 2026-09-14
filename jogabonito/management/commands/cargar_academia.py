# coding=utf-8
"""Deja la academia con sus datos reales de arranque.

Kevyn Supe es el duenio Y entrena, asi que tambien tiene ficha de entrenador.
Los alumnos con los que arranca el sistema son tres, en el grupo de la noche.

    python manage.py cargar_academia            # crea/actualiza lo real
    python manage.py cargar_academia --limpiar  # ademas borra los de prueba

Con --limpiar se van los jugadores que NO son estos tres (y todo lo que cuelga
de ellos: asistencias, mediciones, mensualidades, notas). Es para dejar la base
lista para mostrarla, no para usarla con datos de verdad ya cargados.
"""
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction

from jogabonito.cobros import poner_al_dia_jugador
from jogabonito.models import (
    ASISTENCIA_ATRASO, ASISTENCIA_FALTA, ASISTENCIA_JUSTIFICADO, ASISTENCIA_PRESENTE,
    JUGADOR_ACTIVO, MENSUALIDAD_PAGADO, NOTA_ATENCION, NOTA_FELICITACION, NOTA_GENERAL,
    PAGO_EFECTIVO, ROL_ADMINISTRADOR, Asistencia, Categoria, ControlFisico, Entrenador,
    Evaluacion, Indicador, Jugador, Medicion, Nota, PerfilUsuario, Posicion, Representante,
    TipoEvaluacion,
)

# El acceso de Kevyn al sistema. La clave se pasa por --clave-kevyn; si no se
# pasa y el usuario ya existe, no se le toca.
USUARIO_KEVYN = 'ksupe'

HOY = date.today()

# El grupo con el que arranca: la noche.
GRUPO = {
    'nombre': 'NOCHE',
    'descripcion': 'Grupo de adultos, en la noche.',
    'dias': '2,4',
    'hora_inicio': time(18, 0),
    'hora_fin': time(20, 0),
    'valor_mensual': Decimal('25.00'),
    'edad_minima': 18,
    'edad_maxima': 60,
}

# Los de la noche son ADULTOS, no una categoria formativa (hay ninios y
# jovenes en los otros horarios). La fecha de Edison es la real; las otras dos
# son de relleno para que salgan como adultos: corregirlas en su ficha.
# (nombre1, nombre2, apellido1, apellido2, cedula, telefono, direccion,
#  nacimiento, ingreso, posicion, pie)
ALUMNOS = [
    ('EDISON', 'ROLANDO', 'MOYOLEMA', 'MOYOLEMA', '1804290490', '0999955936',
     'Picaihua, Tangaiche', date(1989, 3, 13), date(2026, 9, 2), 'VOLANTE MIXTO', 1),
    # El que lleva mas tiempo entrenando: por el se ve un historial largo
    # de pagos y de asistencias, que es como se ve un alumno al anio.
    ('CHRISTIAN', '', 'MOYOLEMA', '', '', '', '',
     date(1998, 8, 9), HOY - timedelta(days=190), 'DELANTERO', 1),
    ('LUIS', 'MIGUEL', 'SAILEMA', 'MORALES', '1804358925', '0984538221', '',
     date(1993, 9, 23), HOY - timedelta(days=40), 'DEFENSA CENTRAL', 2),
]

APODOS = {0: 'EDY'}

# Lo que hay que saberle a cada uno antes de exigirle en la cancha.
# (alumno, que tiene, que se le cuida, alergias, tipo de sangre)
SALUD = [
    (0, 'Condromalacia rotuliana en la rodilla derecha y fascitis plantar.',
     'Nada de saltos repetidos ni correr en piso duro. Estirar la planta antes '
     'y despues. Si le duele el talon, para.',
     '', 'O+'),
    (1, 'Asma leve desde ninio. Usa inhalador.',
     'Que traiga el inhalador a cada clase. En los trabajos de resistencia, '
     'pausas mas seguido. Si le silba el pecho, sale.',
     'Polen', 'A+'),
]

# Que se le midio a cada uno en cada prueba: (indicador, valor de cada alumno).
# Hay huecos a proposito: no a todos se les toma todo el mismo dia.
PRUEBAS = [
    # (dias atras, titulo, tipo, [(indicador, [valor edison, christian, luis])])
    (60, 'PRUEBA DE INGRESO', 'DIAGNOSTICA INICIAL', [
        ('CONTROL Y DOMINIO DEL BALON', ['6', '5', '7']),
        ('PASE CORTO', ['6', '6', '7']),
        ('VELOCIDAD 30 METROS', ['5.90', '6.20', '5.60']),
        ('LECTURA DE JUEGO', ['5', '6', '7']),
        ('ACTITUD Y COMPROMISO', ['8', '9', '7']),
    ]),
    (30, 'CONTROL DEL MES', 'EVALUACION MENSUAL', [
        ('CONTROL Y DOMINIO DEL BALON', ['7', '6', '7']),
        ('PASE CORTO', ['7', '7', None]),          # Luis falto ese dia
        ('VELOCIDAD 30 METROS', ['5.75', '6.05', '5.62']),
        ('LECTURA DE JUEGO', ['6', '7', '7']),
        ('ACTITUD Y COMPROMISO', ['9', '9', '6']),
    ]),
    (5, 'SEGUIMIENTO DE LA SEMANA', 'SEGUIMIENTO SEMANAL', [
        ('CONTROL Y DOMINIO DEL BALON', ['8', '7', '7']),
        ('VELOCIDAD 30 METROS', ['5.60', '5.95', '5.70']),
        ('ACTITUD Y COMPROMISO', ['9', '10', '6']),
    ]),
]

# (alumno, dias atras, peso, estatura)
MEDIDAS = [
    (0, 60, '38.50', 148), (0, 5, '39.20', 150),
    (1, 180, '69.00', 173), (1, 60, '70.50', 174), (1, 5, '71.20', 174),
    (2, 60, '45.00', 158), (2, 5, '45.40', 159),
]

# (alumno, dias atras, tipo, texto)
NOTAS = [
    (0, 45, NOTA_FELICITACION, 'Se le nota mas seguro con el balon y ayuda a los mas pequenios.'),
    (1, 20, NOTA_GENERAL, 'Le esta costando el pase largo; hay que trabajarlo en la semana.'),
    (2, 8, NOTA_ATENCION, 'Vino desanimado las ultimas dos clases. Conversar con la familia.'),
    (1, 150, NOTA_GENERAL, 'Entro con miedo al contacto; de a poco se esta soltando.'),
    (1, 60, NOTA_FELICITACION, 'De los mas constantes del grupo. Casi no falta.'),
]

# Como viene cada uno a entrenar. Es de cada 10 clases, cuantas falta y
# cuantas llega tarde: asi el historial no sale perfecto, que no es real.
# (alumno, de cada cuantas clases falta, de cada cuantas llega tarde)
RITMO_ASISTENCIA = [
    (0, 9, 5),    # Edison: falta poco, a veces llega tarde del trabajo
    (1, 11, 9),   # Christian: casi no falta, por eso lleva tanto tiempo
    (2, 5, 8),    # Luis: el que mas falta
]


class Command(BaseCommand):
    help = 'Carga los datos reales de arranque: Kevyn como entrenador y los tres alumnos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpiar', action='store_true',
            help='Borra los jugadores de prueba que no sean estos tres.'
        )
        parser.add_argument(
            '--clave-kevyn', default='',
            help='Clave del usuario %s. Vacio = no se le crea ni se le cambia.' % USUARIO_KEVYN
        )

    @transaction.atomic
    def handle(self, *args, **opciones):
        kevyn = self.crear_entrenador()
        self.crear_acceso_de_kevyn(kevyn, opciones.get('clave_kevyn') or '')
        grupo = self.crear_grupo(kevyn)
        alumnos = self.crear_alumnos(grupo)

        if opciones['limpiar']:
            self.limpiar(alumnos)

        self.crear_pruebas(grupo, alumnos)
        self.crear_medidas(alumnos)
        self.crear_notas(alumnos, kevyn)
        self.crear_asistencias(grupo, alumnos)
        self.crear_mensualidades(alumnos)

        self.stdout.write(self.style.SUCCESS(
            'Academia lista: %s con %s alumnos.' % (grupo.nombre, len(alumnos))))

    # ------------------------------------------------------------------
    def crear_entrenador(self):
        """Kevyn es el duenio y ademas dirige, asi que tiene las dos cosas."""
        kevyn, creado = Entrenador.objects.get_or_create(
            nombres='KEVYN', apellidos='SUPE',
            defaults={'telefono': '0980137922', 'email': 'ksupe07@gmail.com'}
        )
        self.stdout.write('  entrenador %s %s' % (kevyn.nombre_completo(),
                                                  '(creado)' if creado else '(ya estaba)'))
        return kevyn

    def crear_acceso_de_kevyn(self, kevyn, clave):
        """Su usuario para entrar al sistema.

        Va como ADMINISTRADOR porque es el duenio: necesita ver la plata y
        los jugadores, no solo marcar asistencia.
        """
        if not clave and not User.objects.filter(username=USUARIO_KEVYN).exists():
            return  # sin clave no se inventa un acceso

        usuario, creado = User.objects.get_or_create(
            username=USUARIO_KEVYN,
            defaults={'first_name': kevyn.nombres, 'last_name': kevyn.apellidos,
                      'email': kevyn.email or ''}
        )
        if clave:
            usuario.set_password(clave)
            usuario.save()

        grupo = Group.objects.filter(name='ADMINISTRADOR').first()
        if grupo:
            usuario.groups.add(grupo)

        perfil = PerfilUsuario.objects.filter(usuario=usuario).first() or PerfilUsuario(usuario=usuario)
        perfil.rol = ROL_ADMINISTRADOR
        perfil.telefono = kevyn.telefono or ''
        perfil.activo = True
        perfil.save()

        if kevyn.usuario_id is None:
            kevyn.usuario = usuario
            kevyn.save()

        self.stdout.write('  acceso de %s: usuario %s %s' % (
            kevyn.nombre_completo(), USUARIO_KEVYN,
            '(creado)' if creado else '(clave actualizada)' if clave else '(ya estaba)'))

    def crear_grupo(self, kevyn):
        grupo, creado = Categoria.objects.get_or_create(
            nombre=GRUPO['nombre'], defaults=GRUPO)

        grupo.entrenadores.add(kevyn)
        if grupo.encargado_id is None:
            grupo.encargado = kevyn
            grupo.save()

        self.stdout.write('  grupo %s %s' % (grupo.nombre, '(creado)' if creado else '(ya estaba)'))
        return grupo

    def crear_alumnos(self, grupo):
        alumnos = []
        for datos in ALUMNOS:
            (nombre1, nombre2, apellido1, apellido2, cedula, telefono,
             direccion, nacimiento, ingreso, posicion, pie) = datos

            jugador, creado = Jugador.objects.get_or_create(
                nombre1=nombre1, apellido1=apellido1,
                defaults={
                    'nombre2': nombre2,
                    'apellido2': apellido2,
                    'cedula': cedula,
                    'telefono': telefono,
                    'direccion': direccion,
                    'fecha_nacimiento': nacimiento,
                    'fecha_ingreso': ingreso,
                    'categoria': grupo,
                    'estado': JUGADOR_ACTIVO,
                    'pie_habil': pie,
                    'posicion': Posicion.objects.filter(nombre=posicion).first(),
                }
            )
            if not creado:
                jugador.categoria = grupo
                jugador.estado = JUGADOR_ACTIVO
                jugador.save()

            alumnos.append(jugador)
            self.stdout.write('  alumno %s %s' % (jugador.nombre_completo(),
                                                  '(creado)' if creado else '(ya estaba)'))

        self.ponerles_apodo(alumnos)
        self.ponerles_salud(alumnos)
        self.crear_representante(alumnos)
        return alumnos

    def ponerles_apodo(self, alumnos):
        """Como le dicen en la cancha; es lo primero que pregunta el profe."""
        for posicion, apodo in APODOS.items():
            if posicion < len(alumnos) and not alumnos[posicion].apodo:
                alumnos[posicion].apodo = apodo
                alumnos[posicion].save()

    def ponerles_salud(self, alumnos):
        """Lo que tiene cada uno y que hay que cuidarle en la cancha."""
        for posicion, condicion, cuidados, alergias, sangre in SALUD:
            if posicion >= len(alumnos):
                continue
            jugador = alumnos[posicion]
            if jugador.condicion_medica:
                continue  # ya lo llenaron a mano: no se pisa
            jugador.condicion_medica = condicion
            jugador.cuidados = cuidados
            jugador.alergias = alergias
            jugador.tipo_sangre = sangre
            jugador.save()
        self.stdout.write('  fichas de salud puestas')

    def crear_representante(self, alumnos):
        """Los dos Moyolema comparten representante; es lo normal en hermanos."""
        papa, _ = Representante.objects.get_or_create(
            nombres='EDISON', apellidos='MOYOLEMA LEMA',
            defaults={'telefono': '0980137922', 'whatsapp': '0980137922',
                      'parentesco': 1}
        )
        for jugador in alumnos[:2]:
            if jugador.representante_id is None:
                jugador.representante = papa
                jugador.save()

    def limpiar(self, alumnos):
        """Se van los de prueba: no queremos mostrar datos inventados."""
        sobrantes = Jugador.objects.exclude(pk__in=[j.pk for j in alumnos])
        cuantos = sobrantes.count()

        for jugador in sobrantes:
            jugador.mensualidades.all().delete()
            jugador.asistencias.all().delete()
            jugador.mediciones.all().delete()
            jugador.notas.all().delete()
            jugador.controles.all().delete()
            jugador.evaluaciones_propias.all().delete()
            jugador.delete()

        if cuantos:
            self.stdout.write(self.style.WARNING('  se borraron %s jugadores de prueba' % cuantos))

        # Las pruebas que quedaron sin ninguna medicion eran de esos jugadores.
        vacias = Evaluacion.objects.filter(mediciones__isnull=True)
        cuantas = vacias.count()
        if cuantas:
            for evaluacion in vacias:
                evaluacion.indicadores.clear()
            vacias.delete()
            self.stdout.write(self.style.WARNING('  se borraron %s pruebas vacias' % cuantas))

    # ------------------------------------------------------------------
    def crear_pruebas(self, grupo, alumnos):
        for dias_atras, titulo, tipo, mediciones in PRUEBAS:
            fecha = HOY - timedelta(days=dias_atras)

            evaluacion, creada = Evaluacion.objects.get_or_create(
                titulo=titulo, categoria=grupo,
                defaults={'fecha': fecha, 'fecha_fin': fecha + timedelta(days=2),
                          'tipo': TipoEvaluacion.objects.filter(nombre=tipo).first()}
            )
            if not creada:
                continue

            indicadores = []
            for nombre, valores in mediciones:
                indicador = Indicador.objects.filter(nombre=nombre).first()
                if indicador is None:
                    continue
                indicadores.append(indicador)

                for posicion, valor in enumerate(valores):
                    if valor is None or posicion >= len(alumnos):
                        continue  # ese dia no se le tomo a ese alumno
                    Medicion.objects.get_or_create(
                        evaluacion=evaluacion, jugador=alumnos[posicion], indicador=indicador,
                        defaults={'valor': Decimal(valor),
                                  'fecha': fecha + timedelta(days=posicion % 2)}
                    )

            evaluacion.indicadores.set(indicadores)
            self.stdout.write('  prueba %s (%s)' % (titulo, fecha.strftime('%d/%m/%Y')))

    def crear_medidas(self, alumnos):
        """Las fechas van contadas desde hoy, asi que si el comando se corre
        otro dia caerian en fechas nuevas y se duplicarian. Por eso al que ya
        tiene medidas no se le agregan mas."""
        ya_tienen = {j.id for j in alumnos if j.controles.exists()}

        for posicion, dias_atras, peso, estatura in MEDIDAS:
            if posicion >= len(alumnos):
                continue
            jugador = alumnos[posicion]
            if jugador.id in ya_tienen:
                continue
            ControlFisico.objects.create(
                jugador=jugador, fecha=HOY - timedelta(days=dias_atras),
                peso=Decimal(peso), estatura=estatura
            )
        self.stdout.write('  peso y estatura: %s controles' % ControlFisico.objects.count())

    def crear_notas(self, alumnos, kevyn):
        """Igual que las medidas: al que ya tiene notas no se le inventan mas."""
        ya_tienen = {j.id for j in alumnos if j.notas.exists()}

        for posicion, dias_atras, tipo, texto in NOTAS:
            if posicion >= len(alumnos):
                continue
            jugador = alumnos[posicion]
            if jugador.id in ya_tienen:
                continue
            Nota.objects.create(
                jugador=jugador, fecha=HOY - timedelta(days=dias_atras),
                tipo=tipo, texto=texto, entrenador=kevyn
            )
        self.stdout.write('  notas del profe: %s' % Nota.objects.count())

    def crear_asistencias(self, grupo, alumnos):
        """Marca todas las clases desde que entro cada uno.

        No es al azar: cada alumno tiene su ritmo (RITMO_ASISTENCIA) y se
        repite igual cada vez que se corre el comando, para que la pantalla
        no cambie sola de un dia para otro.
        """
        dias_de_clase = grupo.dias_lista()
        if not dias_de_clase:
            return

        creadas = 0
        for posicion, cada_cuantas_falta, cada_cuantas_tarde in RITMO_ASISTENCIA:
            if posicion >= len(alumnos):
                continue
            jugador = alumnos[posicion]

            if jugador.asistencias.exists():
                continue  # ya tiene historial: no se le inventa mas

            fecha = jugador.fecha_ingreso
            clase = 0
            marcas = []
            while fecha <= HOY:
                if str(fecha.isoweekday()) in dias_de_clase:
                    clase += 1
                    if clase % cada_cuantas_falta == 0:
                        # Una de cada tantas la falta; una de esas la justifica.
                        estado = (ASISTENCIA_JUSTIFICADO if clase % (cada_cuantas_falta * 2) == 0
                                  else ASISTENCIA_FALTA)
                    elif clase % cada_cuantas_tarde == 0:
                        estado = ASISTENCIA_ATRASO
                    else:
                        estado = ASISTENCIA_PRESENTE
                    marcas.append(Asistencia(jugador=jugador, categoria=grupo,
                                             fecha=fecha, estado=estado))
                fecha += timedelta(days=1)

            Asistencia.objects.bulk_create(marcas)
            creadas += len(marcas)
            resumen = jugador.resumen_asistencia()
            self.stdout.write('  %s: %s clases, %s%% de asistencia' % (
                jugador.nombre_completo(), len(marcas), resumen['porcentaje']))

        self.stdout.write('  asistencias cargadas: %s' % creadas)

    def crear_mensualidades(self, alumnos):
        """Abre los meses de cada uno desde su ingreso y los deja pagados.

        El unico que queda debiendo es el mes en curso: es la foto normal de
        una academia, el que viene hace rato esta al dia y debe el de ahora.
        """
        for jugador in alumnos:
            poner_al_dia_jugador(jugador)

        for jugador in alumnos:
            meses = list(jugador.mensualidades_en_orden())
            if not meses:
                continue

            # Todos menos el ultimo: ya los pago, dos o tres dias despues de
            # que le tocaba, que es como pasa de verdad.
            for mensualidad in meses[:-1]:
                if mensualidad.esta_pagada():
                    continue
                mensualidad.estado = MENSUALIDAD_PAGADO
                mensualidad.fecha_pago = min(
                    mensualidad.periodo_inicio + timedelta(days=2), HOY)
                mensualidad.forma_pago = PAGO_EFECTIVO
                mensualidad.save()

            self.stdout.write('  %s: %s meses, debe %s' % (
                jugador.nombre_completo(), len(meses), jugador.total_que_debe()))

        self.ponerle_un_descuento(alumnos)

    def ponerle_un_descuento(self, alumnos):
        """Un mes con rebaja, para que se vea de donde sale lo que paga.

        Pasa seguido: un mes le hacen precio por algo y al siguiente vuelve a
        pagar completo. Por eso el motivo se guarda en el mes.
        """
        if len(alumnos) < 2:
            return
        christian = alumnos[1]
        meses = list(christian.mensualidades_en_orden())
        if len(meses) < 4:
            return

        # Uno en porcentaje y otro en plata: las dos maneras en que se habla
        # un descuento en la cancha.
        rebajado = meses[2]
        if not rebajado.tiene_descuento():
            rebajado.descuento_aplicado = Decimal('20.00')
            rebajado.motivo_descuento = 'Se lesiono y entreno media jornada ese mes'
            rebajado.recalcular_por_ausencia()
            rebajado.save()

        en_plata = meses[3]
        if not en_plata.tiene_descuento():
            en_plata.descuento_monto = Decimal('5.00')
            en_plata.motivo_descuento = 'Acuerdo de ese mes: 5 menos'
            en_plata.recalcular_por_ausencia()
            en_plata.save()

        self.stdout.write('  %s tuvo dos meses con rebaja (%s y %s)' % (
            christian.nombre_completo(), rebajado.valor, en_plata.valor))
