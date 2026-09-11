# coding=utf-8
"""Modelos del sistema de la Academia Joga Bonito (FASE 1)."""
from datetime import date

from django.contrib.auth.models import Group, User
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

validador_telefono = RegexValidator(
    r'^[0-9+\-\s()]{7,20}$',
    'Ingrese un telefono valido (solo numeros, espacios, + - y parentesis).'
)


def texto_limpio(valor, mayusculas=False):
    """Normaliza el texto que se guarda en la base."""
    valor = ' '.join((valor or '').split())
    return valor.upper() if mayusculas else valor


class ModeloBase(models.Model):
    """Modelo base con auditoria: se usa `instancia.save(request)`."""

    usuario_creacion = models.ForeignKey(User, related_name='+', blank=True, null=True, on_delete=models.PROTECT)
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    usuario_modificacion = models.ForeignKey(User, related_name='+', blank=True, null=True, on_delete=models.PROTECT)
    fecha_modificacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Acepta `save(request)` sin romper el contrato de Django.

        Django interpreta el primer argumento posicional de save() como
        `force_insert`, por eso el request NO se reenvia a super().
        """
        request = args[0] if args and hasattr(args[0], 'user') else None
        resto = args[1:] if request is not None else args

        usuario_id = None
        if request is not None:
            usuario = getattr(request, 'user', None)
            if usuario is not None and getattr(usuario, 'is_authenticated', False):
                usuario_id = usuario.id

        if self.pk:
            self.usuario_modificacion_id = usuario_id
            self.fecha_modificacion = timezone.now()
        else:
            self.usuario_creacion_id = usuario_id
            self.fecha_creacion = timezone.now()

        super().save(*resto, **kwargs)

    def en_uso(self):
        """Indica si el registro tiene relaciones que impiden eliminarlo."""
        for relacion in self._meta.related_objects:
            related = getattr(self, relacion.get_accessor_name(), None)
            if related is None:
                continue
            if hasattr(related, 'exists'):
                if related.exists():
                    return True
            else:
                return True
        return False


# ============================================================================
# SEGURIDAD: modulos y permisos por grupo
# ============================================================================
class Modulo(ModeloBase):
    url = models.CharField(default='', max_length=100, unique=True, verbose_name='URL')
    nombre = models.CharField(default='', max_length=100, verbose_name='Nombre')
    descripcion = models.CharField(default='', max_length=200, blank=True, verbose_name='Descripcion')
    icono = models.CharField(default='fa-solid fa-layer-group', max_length=60, verbose_name='Icono')
    orden = models.IntegerField(default=0, verbose_name='Orden')
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Modulo'
        verbose_name_plural = 'Modulos'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return '%s (/%s)' % (self.nombre, self.url)

    def save(self, *args, **kwargs):
        self.url = texto_limpio(self.url).lower()
        self.nombre = texto_limpio(self.nombre)
        self.descripcion = texto_limpio(self.descripcion)
        super().save(*args, **kwargs)


class GruposModulos(ModeloBase):
    grupo = models.OneToOneField(Group, on_delete=models.PROTECT, verbose_name='Grupo')
    modulos = models.ManyToManyField(Modulo, verbose_name='Modulos')

    class Meta:
        verbose_name = 'Grupo de modulos'
        verbose_name_plural = 'Grupos de modulos'
        ordering = ['grupo']

    def __str__(self):
        return '%s' % self.grupo.name

    def modulos_activos(self):
        return self.modulos.filter(activo=True).order_by('orden', 'nombre')


# ============================================================================
# USUARIOS
# ============================================================================
ROL_ADMINISTRADOR = 1
ROL_ENTRENADOR = 2

ROLES = (
    (ROL_ADMINISTRADOR, 'ADMINISTRADOR'),
    (ROL_ENTRENADOR, 'ENTRENADOR'),
)


class PerfilUsuario(ModeloBase):
    """Un usuario del sistema y su rol. Una academia, un perfil por usuario."""

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil', verbose_name='Usuario')
    rol = models.IntegerField(choices=ROLES, default=ROL_ENTRENADOR, verbose_name='Rol')
    telefono = models.CharField(max_length=20, blank=True, validators=[validador_telefono], verbose_name='Telefono')
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Perfil de usuario'
        verbose_name_plural = 'Perfiles de usuarios'
        ordering = ['usuario__username']

    def __str__(self):
        return '%s (%s)' % (self.usuario.get_full_name() or self.usuario.username, self.get_rol_display())

    def es_administrador(self):
        return self.rol == ROL_ADMINISTRADOR or self.usuario.is_superuser

    def es_entrenador(self):
        return self.rol == ROL_ENTRENADOR and not self.usuario.is_superuser

    def entrenador(self):
        """Ficha de entrenador vinculada a este usuario (si existe)."""
        return Entrenador.objects.filter(usuario=self.usuario).first()

    def nombre_completo(self):
        entrenador = self.entrenador()
        if entrenador:
            return entrenador.nombre_completo()
        return self.usuario.get_full_name() or self.usuario.username


# ============================================================================
# ENTRENADORES
# ============================================================================
class Entrenador(ModeloBase):
    nombres = models.CharField(max_length=100, verbose_name='Nombres')
    apellidos = models.CharField(max_length=100, verbose_name='Apellidos')
    cedula = models.CharField(max_length=13, blank=True, verbose_name='Cedula')
    telefono = models.CharField(max_length=20, validators=[validador_telefono], verbose_name='Telefono')
    email = models.EmailField(blank=True, verbose_name='Correo electronico')
    fotografia = models.ImageField(upload_to='entrenadores/', blank=True, null=True, verbose_name='Fotografia')
    usuario = models.OneToOneField(
        User, blank=True, null=True, on_delete=models.SET_NULL,
        related_name='entrenador', verbose_name='Usuario del sistema'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Entrenador'
        verbose_name_plural = 'Entrenadores'
        ordering = ['apellidos', 'nombres']

    def __str__(self):
        return self.nombre_completo()

    def save(self, *args, **kwargs):
        self.nombres = texto_limpio(self.nombres, mayusculas=True)
        self.apellidos = texto_limpio(self.apellidos, mayusculas=True)
        self.cedula = texto_limpio(self.cedula)
        super().save(*args, **kwargs)

    def nombre_completo(self):
        return ('%s %s' % (self.apellidos, self.nombres)).strip()

    def categorias_activas(self):
        return self.categorias.filter(activo=True).order_by('hora_inicio', 'nombre')

    def total_jugadores(self):
        return Jugador.objects.filter(categoria__entrenadores=self, estado=JUGADOR_ACTIVO).distinct().count()


# ============================================================================
# CATEGORIAS / GRUPOS
# ============================================================================
DIAS_SEMANA = (
    ('1', 'Lunes'),
    ('2', 'Martes'),
    ('3', 'Miercoles'),
    ('4', 'Jueves'),
    ('5', 'Viernes'),
    ('6', 'Sabado'),
    ('7', 'Domingo'),
)

DIAS_SEMANA_DICT = dict(DIAS_SEMANA)


class Categoria(ModeloBase):
    """Grupo de entrenamiento: Manana, Tarde, Noche, Sub-12, etc."""

    nombre = models.CharField(max_length=80, unique=True, verbose_name='Nombre')
    descripcion = models.CharField(max_length=200, blank=True, verbose_name='Descripcion')
    entrenadores = models.ManyToManyField(
        Entrenador, blank=True, related_name='categorias', verbose_name='Entrenadores'
    )
    dias = models.CharField(max_length=20, blank=True, verbose_name='Dias de entrenamiento')
    hora_inicio = models.TimeField(verbose_name='Hora de inicio')
    hora_fin = models.TimeField(verbose_name='Hora de fin')
    valor_mensual = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='Valor mensual')
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['hora_inicio', 'nombre']

    def __str__(self):
        return '%s' % self.nombre

    def save(self, *args, **kwargs):
        self.nombre = texto_limpio(self.nombre, mayusculas=True)
        self.descripcion = texto_limpio(self.descripcion)
        self.dias = ','.join(self.dias_lista())
        super().save(*args, **kwargs)

    def dias_lista(self):
        """Devuelve ['1','3','5'] ordenado y sin repetidos."""
        valores = [d.strip() for d in (self.dias or '').split(',') if d.strip() in DIAS_SEMANA_DICT]
        return sorted(set(valores))

    def dias_nombres(self):
        return [DIAS_SEMANA_DICT[d] for d in self.dias_lista()]

    def dias_texto(self):
        return ', '.join(self.dias_nombres()) or 'Sin dias definidos'

    def horario_texto(self):
        return '%s - %s' % (self.hora_inicio.strftime('%H:%M'), self.hora_fin.strftime('%H:%M'))

    def entrena_hoy(self, dia=None):
        dia = dia or date.today()
        return str(dia.isoweekday()) in self.dias_lista()

    def jugadores_activos(self):
        return self.jugadores.filter(estado=JUGADOR_ACTIVO).order_by('apellidos', 'nombres')

    def total_jugadores_activos(self):
        return self.jugadores.filter(estado=JUGADOR_ACTIVO).count()

    def entrenadores_texto(self):
        return ', '.join([e.nombre_completo() for e in self.entrenadores.all()]) or 'Sin entrenador'


# ============================================================================
# REPRESENTANTES
# ============================================================================
PARENTESCOS = (
    (1, 'PADRE'),
    (2, 'MADRE'),
    (3, 'ABUELO/A'),
    (4, 'TIO/A'),
    (5, 'HERMANO/A'),
    (6, 'OTRO'),
)


class Representante(ModeloBase):
    nombres = models.CharField(max_length=100, verbose_name='Nombres')
    apellidos = models.CharField(max_length=100, verbose_name='Apellidos')
    cedula = models.CharField(max_length=13, blank=True, verbose_name='Cedula')
    telefono = models.CharField(max_length=20, validators=[validador_telefono], verbose_name='Telefono')
    whatsapp = models.CharField(max_length=20, blank=True, validators=[validador_telefono], verbose_name='WhatsApp')
    email = models.EmailField(blank=True, verbose_name='Correo electronico')
    parentesco = models.IntegerField(choices=PARENTESCOS, default=1, verbose_name='Parentesco')
    direccion = models.CharField(max_length=200, blank=True, verbose_name='Direccion')
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Representante'
        verbose_name_plural = 'Representantes'
        ordering = ['apellidos', 'nombres']

    def __str__(self):
        return self.nombre_completo()

    def save(self, *args, **kwargs):
        self.nombres = texto_limpio(self.nombres, mayusculas=True)
        self.apellidos = texto_limpio(self.apellidos, mayusculas=True)
        self.cedula = texto_limpio(self.cedula)
        super().save(*args, **kwargs)

    def nombre_completo(self):
        return ('%s %s' % (self.apellidos, self.nombres)).strip()

    def numero_whatsapp(self):
        return self.whatsapp or self.telefono

    def total_jugadores(self):
        return self.jugadores.count()


# ============================================================================
# JUGADORES
# ============================================================================
JUGADOR_ACTIVO = 1
JUGADOR_INACTIVO = 2
JUGADOR_RETIRADO = 3

ESTADOS_JUGADOR = (
    (JUGADOR_ACTIVO, 'ACTIVO'),
    (JUGADOR_INACTIVO, 'INACTIVO'),
    (JUGADOR_RETIRADO, 'RETIRADO'),
)

PIE_DERECHO = 1
PIE_IZQUIERDO = 2
PIE_AMBOS = 3

PIES_HABILES = (
    (PIE_DERECHO, 'DERECHO'),
    (PIE_IZQUIERDO, 'IZQUIERDO'),
    (PIE_AMBOS, 'AMBOS'),
)


class Jugador(ModeloBase):
    nombres = models.CharField(max_length=100, verbose_name='Nombres')
    apellidos = models.CharField(max_length=100, verbose_name='Apellidos')
    cedula = models.CharField(max_length=13, blank=True, verbose_name='Cedula')
    fecha_nacimiento = models.DateField(verbose_name='Fecha de nacimiento')
    fotografia = models.ImageField(upload_to='jugadores/', blank=True, null=True, verbose_name='Fotografia')
    telefono = models.CharField(max_length=20, blank=True, validators=[validador_telefono], verbose_name='Telefono')
    direccion = models.CharField(max_length=200, blank=True, verbose_name='Direccion')
    fecha_ingreso = models.DateField(default=date.today, verbose_name='Fecha de ingreso')
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name='jugadores', verbose_name='Categoria'
    )
    representante = models.ForeignKey(
        Representante, blank=True, null=True, on_delete=models.SET_NULL,
        related_name='jugadores', verbose_name='Representante'
    )
    valor_mensual = models.DecimalField(
        max_digits=8, decimal_places=2, blank=True, null=True,
        verbose_name='Valor mensual personalizado',
        help_text='Dejar vacio para usar el valor de la categoria.'
    )
    posicion = models.ForeignKey(
        'Posicion', blank=True, null=True, on_delete=models.SET_NULL,
        related_name='jugadores', verbose_name='Posicion que le gusta'
    )
    pie_habil = models.IntegerField(choices=PIES_HABILES, blank=True, null=True, verbose_name='Pie habil')
    dorsal = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Dorsal')
    observacion = models.TextField(blank=True, verbose_name='Observacion general')
    estado = models.IntegerField(choices=ESTADOS_JUGADOR, default=JUGADOR_ACTIVO, verbose_name='Estado')

    class Meta:
        verbose_name = 'Jugador'
        verbose_name_plural = 'Jugadores'
        ordering = ['apellidos', 'nombres']
        constraints = [
            models.UniqueConstraint(
                fields=['cedula'],
                condition=~models.Q(cedula=''),
                name='jugador_cedula_unica'
            )
        ]

    def __str__(self):
        return self.nombre_completo()

    def save(self, *args, **kwargs):
        self.nombres = texto_limpio(self.nombres, mayusculas=True)
        self.apellidos = texto_limpio(self.apellidos, mayusculas=True)
        self.cedula = texto_limpio(self.cedula)
        super().save(*args, **kwargs)

    def nombre_completo(self):
        return ('%s %s' % (self.apellidos, self.nombres)).strip()

    def edad(self, referencia=None):
        referencia = referencia or date.today()
        if not self.fecha_nacimiento:
            return 0
        anios = referencia.year - self.fecha_nacimiento.year
        if (referencia.month, referencia.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day):
            anios -= 1
        return max(anios, 0)

    def es_menor_edad(self):
        return self.edad() < 18

    def valor_mensual_vigente(self):
        """Valor personalizado del jugador o, si no tiene, el de su categoria."""
        if self.valor_mensual is not None:
            return self.valor_mensual
        return self.categoria.valor_mensual

    def esta_activo(self):
        return self.estado == JUGADOR_ACTIVO

    def entrenadores(self):
        return self.categoria.entrenadores.all()

    # --- Asistencia (FASE 2) --------------------------------------------
    def resumen_asistencia(self, desde=None, hasta=None):
        """Conteo por estado y porcentaje de asistencia del jugador."""
        registros = self.asistencias.all()
        if desde:
            registros = registros.filter(fecha__gte=desde)
        if hasta:
            registros = registros.filter(fecha__lte=hasta)

        conteo = {estado: 0 for estado, _ in ESTADOS_ASISTENCIA}
        for estado in registros.values_list('estado', flat=True):
            conteo[estado] = conteo.get(estado, 0) + 1

        total = sum(conteo.values())
        asistio = conteo[ASISTENCIA_PRESENTE] + conteo[ASISTENCIA_ATRASO]
        return {
            'total': total,
            'presentes': conteo[ASISTENCIA_PRESENTE],
            'faltas': conteo[ASISTENCIA_FALTA],
            'atrasos': conteo[ASISTENCIA_ATRASO],
            'justificados': conteo[ASISTENCIA_JUSTIFICADO],
            'porcentaje': round(asistio * 100.0 / total, 1) if total else 0.0,
        }

    def porcentaje_asistencia(self, desde=None, hasta=None):
        """Porcentaje de clases a las que llego (presente o atrasado)."""
        return self.resumen_asistencia(desde, hasta)['porcentaje']

    def ultimas_asistencias(self, cantidad=10):
        return self.asistencias.all().order_by('-fecha')[:cantidad]

    # --- Evaluaciones y progreso ----------------------------------------
    def progreso(self):
        """Como va en cada indicador: primera marca, ultima, mejor y si mejoro.

        Devuelve una lista de diccionarios lista para pintar en pantalla o para
        armar el resumen que mas adelante leera el asistente de IA.
        """
        mediciones = list(
            self.mediciones.select_related('indicador', 'evaluacion')
            .order_by('indicador__area', 'indicador__orden', 'indicador__nombre', 'evaluacion__fecha')
        )

        por_indicador = {}
        for medicion in mediciones:
            por_indicador.setdefault(medicion.indicador_id, []).append(medicion)

        resultado = []
        for lista in por_indicador.values():
            indicador = lista[0].indicador
            valores = [m.valor for m in lista]
            mejor = min(valores) if indicador.mejor_es == MEJOR_MENOR else max(valores)
            primera, ultima = lista[0], lista[-1]
            diferencia = ultima.valor - primera.valor if len(lista) > 1 else None

            resultado.append({
                'indicador': indicador,
                'tomas': len(lista),
                'primera': primera,
                'ultima': ultima,
                'mejor': mejor,
                'mejor_texto': indicador.formatear(mejor),
                'diferencia': diferencia,
                'mejoro': indicador.es_mejora(primera.valor, ultima.valor) if len(lista) > 1 else None,
                'historial': lista,
            })

        resultado.sort(key=lambda x: (x['indicador'].area, x['indicador'].orden, x['indicador'].nombre))
        return resultado

    def comparativa_categoria(self):
        """Ultimo valor del jugador contra el promedio de su grupo.

        De aqui salen las fortalezas (esta por encima del grupo) y lo que hay
        que trabajar (esta por debajo).
        """
        from django.db.models import Avg

        resultado = []
        for fila in self.progreso():
            indicador = fila['indicador']
            ultima = fila['ultima']

            # Ultimo valor de cada companiero en ese indicador.
            companieros = Jugador.objects.filter(
                categoria=self.categoria, estado=JUGADOR_ACTIVO
            ).exclude(pk=self.pk).values_list('pk', flat=True)

            ultimos = []
            for jugador_id in companieros:
                medicion = Medicion.objects.filter(
                    jugador_id=jugador_id, indicador=indicador
                ).order_by('-evaluacion__fecha').first()
                if medicion:
                    ultimos.append(medicion.valor)

            promedio = sum(ultimos) / len(ultimos) if ultimos else None
            if promedio is None:
                posicion = None
            elif indicador.mejor_es == MEJOR_MENOR:
                posicion = 'fortaleza' if ultima.valor < promedio else 'mejorar'
            else:
                posicion = 'fortaleza' if ultima.valor > promedio else 'mejorar'

            resultado.append({
                'indicador': indicador,
                'valor': ultima.valor,
                'valor_texto': ultima.texto(),
                'promedio': round(promedio, 2) if promedio is not None else None,
                'promedio_texto': indicador.formatear(round(promedio, 2)) if promedio is not None else '-',
                'comparados': len(ultimos),
                'posicion': posicion,
            })
        return resultado

    def fortalezas(self):
        return [x for x in self.comparativa_categoria() if x['posicion'] == 'fortaleza']

    def aspectos_a_mejorar(self):
        return [x for x in self.comparativa_categoria() if x['posicion'] == 'mejorar']

    def ultima_evaluacion(self):
        medicion = self.mediciones.select_related('evaluacion').order_by('-evaluacion__fecha').first()
        return medicion.evaluacion if medicion else None


# ============================================================================
# ASISTENCIA (FASE 2)
# ============================================================================
ASISTENCIA_PRESENTE = 1
ASISTENCIA_FALTA = 2
ASISTENCIA_ATRASO = 3
ASISTENCIA_JUSTIFICADO = 4

ESTADOS_ASISTENCIA = (
    (ASISTENCIA_PRESENTE, 'PRESENTE'),
    (ASISTENCIA_FALTA, 'FALTA'),
    (ASISTENCIA_ATRASO, 'ATRASO'),
    (ASISTENCIA_JUSTIFICADO, 'JUSTIFICADO'),
)

# Etiqueta corta y color para los botones grandes del telefono.
ASISTENCIA_BOTONES = (
    (ASISTENCIA_PRESENTE, 'P', 'PRESENTE', 'success'),
    (ASISTENCIA_FALTA, 'F', 'FALTA', 'danger'),
    (ASISTENCIA_ATRASO, 'A', 'ATRASO', 'warning'),
    (ASISTENCIA_JUSTIFICADO, 'J', 'JUSTIFICADO', 'info'),
)


class Asistencia(ModeloBase):
    """Un registro por jugador, categoria y fecha de entrenamiento."""

    jugador = models.ForeignKey(
        Jugador, on_delete=models.CASCADE, related_name='asistencias', verbose_name='Jugador'
    )
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name='asistencias', verbose_name='Categoria'
    )
    fecha = models.DateField(verbose_name='Fecha')
    estado = models.IntegerField(choices=ESTADOS_ASISTENCIA, default=ASISTENCIA_PRESENTE, verbose_name='Estado')
    observacion = models.CharField(max_length=250, blank=True, verbose_name='Observacion')

    class Meta:
        verbose_name = 'Asistencia'
        verbose_name_plural = 'Asistencias'
        ordering = ['-fecha', 'jugador__apellidos']
        constraints = [
            models.UniqueConstraint(
                fields=['jugador', 'categoria', 'fecha'],
                name='asistencia_unica_por_jugador_fecha'
            )
        ]
        indexes = [
            models.Index(fields=['categoria', 'fecha']),
            models.Index(fields=['jugador', 'fecha']),
        ]

    def __str__(self):
        return '%s %s: %s' % (self.jugador.nombre_completo(), self.fecha, self.get_estado_display())

    def save(self, *args, **kwargs):
        self.observacion = texto_limpio(self.observacion)
        super().save(*args, **kwargs)

    def color(self):
        for estado, _corta, _larga, color in ASISTENCIA_BOTONES:
            if estado == self.estado:
                return color
        return 'secondary'

    def asistio(self):
        return self.estado in (ASISTENCIA_PRESENTE, ASISTENCIA_ATRASO)

    def usuario_registro(self):
        """Quien dejo el registro como esta ahora."""
        return self.usuario_modificacion or self.usuario_creacion


# ============================================================================
# SOLICITUDES DE INSCRIPCION (llegan desde la pagina publica)
# ============================================================================
SOLICITUD_NUEVA = 1
SOLICITUD_CONTACTADO = 2
SOLICITUD_INSCRITO = 3
SOLICITUD_DESCARTADO = 4

ESTADOS_SOLICITUD = (
    (SOLICITUD_NUEVA, 'NUEVA'),
    (SOLICITUD_CONTACTADO, 'CONTACTADO'),
    (SOLICITUD_INSCRITO, 'INSCRITO'),
    (SOLICITUD_DESCARTADO, 'DESCARTADO'),
)

COLORES_SOLICITUD = {
    SOLICITUD_NUEVA: 'success',
    SOLICITUD_CONTACTADO: 'info',
    SOLICITUD_INSCRITO: 'primary',
    SOLICITUD_DESCARTADO: 'secondary',
}


class SolicitudInscripcion(ModeloBase):
    """Formulario publico: alguien pide un cupo en la academia."""

    nombre = models.CharField(max_length=150, verbose_name='Nombre del interesado')
    telefono = models.CharField(max_length=20, validators=[validador_telefono], verbose_name='Telefono')
    edad = models.PositiveSmallIntegerField(verbose_name='Edad')
    categoria = models.ForeignKey(
        Categoria, blank=True, null=True, on_delete=models.SET_NULL,
        related_name='solicitudes', verbose_name='Grupo de interes'
    )
    mensaje = models.TextField(blank=True, verbose_name='Mensaje')
    estado = models.IntegerField(choices=ESTADOS_SOLICITUD, default=SOLICITUD_NUEVA, verbose_name='Estado')
    nota_interna = models.TextField(blank=True, verbose_name='Nota interna')
    origen_ip = models.GenericIPAddressField(blank=True, null=True, verbose_name='IP de origen')

    class Meta:
        verbose_name = 'Solicitud de inscripcion'
        verbose_name_plural = 'Solicitudes de inscripcion'
        ordering = ['-fecha_creacion']
        indexes = [models.Index(fields=['estado', '-fecha_creacion'])]

    def __str__(self):
        return '%s (%s)' % (self.nombre, self.get_estado_display())

    def save(self, *args, **kwargs):
        self.nombre = texto_limpio(self.nombre, mayusculas=True)
        self.telefono = texto_limpio(self.telefono)
        super().save(*args, **kwargs)

    def color(self):
        return COLORES_SOLICITUD.get(self.estado, 'secondary')

    def es_nueva(self):
        return self.estado == SOLICITUD_NUEVA

    def numero_whatsapp(self):
        """Normaliza 09XXXXXXXX a formato internacional de Ecuador."""
        numero = ''.join(c for c in (self.telefono or '') if c.isdigit())
        if numero.startswith('0'):
            numero = '593' + numero[1:]
        return numero


# ============================================================================
# EVALUACIONES: que se le mide a cada jugador y como va mejorando
# ============================================================================
AREA_TECNICA = 1
AREA_FISICA = 2
AREA_TACTICA = 3
AREA_ACTITUD = 4

AREAS_INDICADOR = (
    (AREA_TECNICA, 'TECNICA'),
    (AREA_FISICA, 'FISICA'),
    (AREA_TACTICA, 'TACTICA'),
    (AREA_ACTITUD, 'ACTITUD'),
)

COLORES_AREA = {
    AREA_TECNICA: 'success',
    AREA_FISICA: 'danger',
    AREA_TACTICA: 'primary',
    AREA_ACTITUD: 'warning',
}

MEDIDA_ESCALA = 1      # 1 a 10, lo califica el entrenador
MEDIDA_NUMERO = 2      # una cantidad con unidad: metros, repeticiones, goles
MEDIDA_TIEMPO = 3      # segundos: aqui mejorar es bajar el numero

TIPOS_MEDIDA = (
    (MEDIDA_ESCALA, 'ESCALA 1 A 10'),
    (MEDIDA_NUMERO, 'NUMERO CON UNIDAD'),
    (MEDIDA_TIEMPO, 'TIEMPO EN SEGUNDOS'),
)

MEJOR_MAYOR = 1
MEJOR_MENOR = 2

SENTIDOS_MEJORA = (
    (MEJOR_MAYOR, 'MIENTRAS MAS ALTO, MEJOR'),
    (MEJOR_MENOR, 'MIENTRAS MAS BAJO, MEJOR'),
)


class Posicion(ModeloBase):
    """Puesto en la cancha. Catalogo editable."""

    nombre = models.CharField(max_length=60, unique=True, verbose_name='Nombre')
    abreviatura = models.CharField(max_length=6, blank=True, verbose_name='Abreviatura')
    orden = models.IntegerField(default=0, verbose_name='Orden')
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Posicion'
        verbose_name_plural = 'Posiciones'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return '%s' % self.nombre

    def save(self, *args, **kwargs):
        self.nombre = texto_limpio(self.nombre, mayusculas=True)
        self.abreviatura = texto_limpio(self.abreviatura, mayusculas=True)
        super().save(*args, **kwargs)


class Indicador(ModeloBase):
    """QUE se le mide al jugador. El administrador arma su propia lista."""

    nombre = models.CharField(max_length=100, unique=True, verbose_name='Que se mide')
    descripcion = models.CharField(max_length=250, blank=True, verbose_name='Como se toma la prueba')
    area = models.IntegerField(choices=AREAS_INDICADOR, default=AREA_TECNICA, verbose_name='Area')
    tipo_medida = models.IntegerField(choices=TIPOS_MEDIDA, default=MEDIDA_ESCALA, verbose_name='Tipo de medida')
    unidad = models.CharField(max_length=15, blank=True, verbose_name='Unidad',
                              help_text='Ejemplo: seg, m, reps, goles. Solo para medida con numero.')
    mejor_es = models.IntegerField(choices=SENTIDOS_MEJORA, default=MEJOR_MAYOR, verbose_name='Sentido de la mejora')
    valor_minimo = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True,
                                       verbose_name='Valor minimo aceptado')
    valor_maximo = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True,
                                       verbose_name='Valor maximo aceptado')
    orden = models.IntegerField(default=0, verbose_name='Orden')
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Indicador'
        verbose_name_plural = 'Indicadores'
        ordering = ['area', 'orden', 'nombre']

    def __str__(self):
        return '%s' % self.nombre

    def save(self, *args, **kwargs):
        self.nombre = texto_limpio(self.nombre, mayusculas=True)
        self.descripcion = texto_limpio(self.descripcion)
        self.unidad = texto_limpio(self.unidad)
        if self.tipo_medida == MEDIDA_ESCALA:
            self.unidad = ''
            self.valor_minimo = self.valor_minimo if self.valor_minimo is not None else 1
            self.valor_maximo = self.valor_maximo if self.valor_maximo is not None else 10
            self.mejor_es = MEJOR_MAYOR
        elif self.tipo_medida == MEDIDA_TIEMPO:
            self.unidad = self.unidad or 'seg'
            self.mejor_es = MEJOR_MENOR
        super().save(*args, **kwargs)

    def color_area(self):
        return COLORES_AREA.get(self.area, 'secondary')

    def sufijo(self):
        if self.tipo_medida == MEDIDA_ESCALA:
            return '/ 10'
        return self.unidad

    def formatear(self, valor):
        if valor is None:
            return '-'
        texto = ('%s' % valor).rstrip('0').rstrip('.') if '.' in ('%s' % valor) else '%s' % valor
        sufijo = self.sufijo()
        return ('%s %s' % (texto, sufijo)).strip()

    def es_mejora(self, anterior, actual):
        """True si el cambio es una mejora para este indicador."""
        if anterior is None or actual is None or anterior == actual:
            return None
        if self.mejor_es == MEJOR_MENOR:
            return actual < anterior
        return actual > anterior

    def rango_valido(self, valor):
        if self.valor_minimo is not None and valor < self.valor_minimo:
            return False
        if self.valor_maximo is not None and valor > self.valor_maximo:
            return False
        return True


class Evaluacion(ModeloBase):
    """Una jornada de pruebas: fecha, grupo y que indicadores se van a tomar."""

    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name='evaluaciones', verbose_name='Categoria'
    )
    fecha = models.DateField(verbose_name='Fecha de la prueba')
    titulo = models.CharField(max_length=120, verbose_name='Titulo',
                              help_text='Ejemplo: Prueba semanal 3, Control de mitad de temporada.')
    indicadores = models.ManyToManyField(Indicador, related_name='evaluaciones', verbose_name='Que se va a medir')
    observacion = models.TextField(blank=True, verbose_name='Observacion')
    cerrada = models.BooleanField(default=False, verbose_name='Cerrada',
                                  help_text='Una evaluacion cerrada ya no admite cambios.')

    class Meta:
        verbose_name = 'Evaluacion'
        verbose_name_plural = 'Evaluaciones'
        ordering = ['-fecha', 'categoria__nombre']

    def __str__(self):
        return '%s - %s (%s)' % (self.titulo, self.categoria.nombre, self.fecha)

    def save(self, *args, **kwargs):
        self.titulo = texto_limpio(self.titulo)
        super().save(*args, **kwargs)

    def indicadores_ordenados(self):
        return self.indicadores.all().order_by('area', 'orden', 'nombre')

    def jugadores(self):
        return self.categoria.jugadores.filter(estado=JUGADOR_ACTIVO).order_by('apellidos', 'nombres')

    def total_esperado(self):
        return self.jugadores().count() * self.indicadores.count()

    def total_registrado(self):
        return self.mediciones.count()

    def avance(self):
        esperado = self.total_esperado()
        if not esperado:
            return 0
        return round(self.total_registrado() * 100.0 / esperado)


class Medicion(ModeloBase):
    """El numero que saco un jugador en un indicador dentro de una evaluacion."""

    evaluacion = models.ForeignKey(
        Evaluacion, on_delete=models.CASCADE, related_name='mediciones', verbose_name='Evaluacion'
    )
    jugador = models.ForeignKey(
        Jugador, on_delete=models.CASCADE, related_name='mediciones', verbose_name='Jugador'
    )
    indicador = models.ForeignKey(
        Indicador, on_delete=models.PROTECT, related_name='mediciones', verbose_name='Indicador'
    )
    valor = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Valor')
    observacion = models.CharField(max_length=250, blank=True, verbose_name='Observacion')

    class Meta:
        verbose_name = 'Medicion'
        verbose_name_plural = 'Mediciones'
        ordering = ['-evaluacion__fecha', 'jugador__apellidos']
        constraints = [
            models.UniqueConstraint(
                fields=['evaluacion', 'jugador', 'indicador'],
                name='medicion_unica_por_evaluacion'
            )
        ]
        indexes = [
            models.Index(fields=['jugador', 'indicador']),
            models.Index(fields=['evaluacion', 'jugador']),
        ]

    def __str__(self):
        return '%s - %s: %s' % (self.jugador.nombre_completo(), self.indicador.nombre, self.valor)

    def save(self, *args, **kwargs):
        self.observacion = texto_limpio(self.observacion)
        super().save(*args, **kwargs)

    def texto(self):
        return self.indicador.formatear(self.valor)

    def anterior(self):
        """La medicion previa del mismo jugador en el mismo indicador."""
        return Medicion.objects.filter(
            jugador=self.jugador, indicador=self.indicador,
            evaluacion__fecha__lt=self.evaluacion.fecha
        ).order_by('-evaluacion__fecha').first()

    def diferencia(self):
        previa = self.anterior()
        if previa is None:
            return None
        return self.valor - previa.valor

    def mejoro(self):
        previa = self.anterior()
        if previa is None:
            return None
        return self.indicador.es_mejora(previa.valor, self.valor)
