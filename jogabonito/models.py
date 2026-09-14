# coding=utf-8
"""Modelos del sistema de la Academia Joga Bonito."""
from calendar import monthrange
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth.models import Group, User
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

validador_telefono = RegexValidator(
    r'^[0-9+\-\s()]{7,20}$',
    'Ingrese un telefono valido (solo numeros, espacios, + - y parentesis).'
)


def repartir_nombres(persona):
    """Mantiene en fila los nombres separados y los completos.

    En Ecuador se usan dos nombres y dos apellidos, y asi los pide el usuario
    (como en el SGA). Pero el sistema busca y ordena por `nombres` y
    `apellidos`, asi que esos se arman solos:

      - si llenaron los campos separados, mandan ellos;
      - si solo vino el nombre completo (una importacion, una prueba), se
        parte para llenar los separados.
    """
    persona.nombre1 = texto_limpio(persona.nombre1, mayusculas=True)
    persona.nombre2 = texto_limpio(persona.nombre2, mayusculas=True)
    persona.apellido1 = texto_limpio(persona.apellido1, mayusculas=True)
    persona.apellido2 = texto_limpio(persona.apellido2, mayusculas=True)

    if persona.nombre1 or persona.apellido1:
        persona.nombres = ' '.join(p for p in (persona.nombre1, persona.nombre2) if p)
        persona.apellidos = ' '.join(p for p in (persona.apellido1, persona.apellido2) if p)
        return

    persona.nombres = texto_limpio(persona.nombres, mayusculas=True)
    persona.apellidos = texto_limpio(persona.apellidos, mayusculas=True)

    partes = persona.nombres.split(' ')
    persona.nombre1 = partes[0] if partes and partes[0] else ''
    persona.nombre2 = ' '.join(partes[1:])

    partes = persona.apellidos.split(' ')
    persona.apellido1 = partes[0] if partes and partes[0] else ''
    persona.apellido2 = ' '.join(partes[1:])


def numero_para_whatsapp(numero):
    """09XXXXXXXX -> 5939XXXXXXXX, que es lo que entiende wa.me.

    El enlace wa.me abre la aplicacion si esta en el celular y WhatsApp Web si
    esta en la computadora, sin que haya que hacer nada distinto.
    """
    digitos = ''.join(c for c in (numero or '') if c.isdigit())
    if digitos.startswith('0'):
        digitos = '593' + digitos[1:]
    return digitos


def texto_limpio(valor, mayusculas=False):
    """Normaliza el texto que se guarda en la base."""
    valor = ' '.join((valor or '').split())
    return valor.upper() if mayusculas else valor


def dia_del_mes(anio, mes, dia):
    """Ese dia del mes, o el ultimo si el mes es mas corto (31 en febrero)."""
    ultimo = monthrange(anio, mes)[1]
    return date(anio, mes, min(max(dia, 1), ultimo))


def mes_siguiente(mes, anio):
    if mes == 12:
        return 1, anio + 1
    return mes + 1, anio


def restar_anios(fecha, anios):
    """La misma fecha de hace N anios (el 29 de febrero cae al 28)."""
    return dia_del_mes(fecha.year - anios, fecha.month, fecha.day)


def un_mes_despues(fecha):
    """La misma fecha del mes que viene (el 31 cae al ultimo dia del mes)."""
    mes, anio = mes_siguiente(fecha.month, fecha.year)
    return dia_del_mes(anio, mes, fecha.day)


def normalizar_decimal(valor):
    """25.00 -> "25" y 12.50 -> "12.5", para mostrarlo sin ceros de mas."""
    texto = '%s' % (valor if valor is not None else 0)
    if '.' in texto:
        texto = texto.rstrip('0').rstrip('.')
    return texto or '0'


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
        `force_insert`, por eso el request NO se reenvia a super(). Tambien
        se acepta save(None), que es guardar sin saber quien lo hizo.
        """
        trae_request = bool(args) and (args[0] is None or hasattr(args[0], 'user'))
        request = args[0] if trae_request else None
        resto = args[1:] if trae_request else args

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
    nombre1 = models.CharField(max_length=60, blank=True, verbose_name='Primer nombre')
    nombre2 = models.CharField(max_length=60, blank=True, verbose_name='Segundo nombre')
    apellido1 = models.CharField(max_length=60, blank=True, verbose_name='Primer apellido')
    apellido2 = models.CharField(max_length=60, blank=True, verbose_name='Segundo apellido')
    nombres = models.CharField(max_length=100, blank=True, verbose_name='Nombres')
    apellidos = models.CharField(max_length=100, blank=True, verbose_name='Apellidos')
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
        constraints = [
            models.UniqueConstraint(
                fields=['cedula'],
                condition=~models.Q(cedula=''),
                name='entrenador_cedula_unica'
            )
        ]

    def __str__(self):
        return self.nombre_completo()

    def save(self, *args, **kwargs):
        repartir_nombres(self)
        self.cedula = texto_limpio(self.cedula)
        super().save(*args, **kwargs)

    def nombre_completo(self):
        return ('%s %s' % (self.apellidos, self.nombres)).strip()

    def numero_whatsapp(self):
        return numero_para_whatsapp(self.telefono)

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
    encargado = models.ForeignKey(
        'Entrenador', blank=True, null=True, on_delete=models.SET_NULL,
        related_name='grupos_a_cargo', verbose_name='Profe a cargo',
        help_text='El que dirige este grupo. Se cambia cuando haga falta.'
    )
    entrenadores = models.ManyToManyField(
        Entrenador, blank=True, related_name='categorias', verbose_name='Entrenadores'
    )
    dias = models.CharField(max_length=20, blank=True, verbose_name='Dias de entrenamiento')
    hora_inicio = models.TimeField(verbose_name='Hora de inicio')
    hora_fin = models.TimeField(verbose_name='Hora de fin')
    valor_mensual = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='Valor mensual')
    # Un grupo puede ser por horario (Manana/Tarde) y ademas por edad (Sub 10).
    edad_minima = models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name='Edad minima',
        help_text='Dejar vacio si el grupo no tiene limite de edad.'
    )
    edad_maxima = models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name='Edad maxima',
        help_text='Dejar vacio si el grupo no tiene limite de edad.'
    )
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

    # --- Rango de edad del grupo ----------------------------------------
    def tiene_rango_edad(self):
        return self.edad_minima is not None or self.edad_maxima is not None

    def rango_edad_texto(self):
        if self.edad_minima is not None and self.edad_maxima is not None:
            return '%s a %s anios' % (self.edad_minima, self.edad_maxima)
        if self.edad_maxima is not None:
            return 'Hasta %s anios' % self.edad_maxima
        if self.edad_minima is not None:
            return 'Desde %s anios' % self.edad_minima
        return 'Todas las edades'

    def edad_encaja(self, edad):
        """True si un jugador de esa edad entra en el grupo."""
        if edad is None:
            return True
        if self.edad_minima is not None and edad < self.edad_minima:
            return False
        if self.edad_maxima is not None and edad > self.edad_maxima:
            return False
        return True

    def jugadores_fuera_de_rango(self):
        """Activos que ya no encajan en la edad del grupo (para avisar, no bloquear)."""
        if not self.tiene_rango_edad():
            return []
        return [j for j in self.jugadores_activos() if not self.edad_encaja(j.edad())]


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
    nombre1 = models.CharField(max_length=60, blank=True, verbose_name='Primer nombre')
    nombre2 = models.CharField(max_length=60, blank=True, verbose_name='Segundo nombre')
    apellido1 = models.CharField(max_length=60, blank=True, verbose_name='Primer apellido')
    apellido2 = models.CharField(max_length=60, blank=True, verbose_name='Segundo apellido')
    nombres = models.CharField(max_length=100, blank=True, verbose_name='Nombres')
    apellidos = models.CharField(max_length=100, blank=True, verbose_name='Apellidos')
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
        constraints = [
            models.UniqueConstraint(
                fields=['cedula'],
                condition=~models.Q(cedula=''),
                name='representante_cedula_unica'
            )
        ]

    def __str__(self):
        return self.nombre_completo()

    def save(self, *args, **kwargs):
        repartir_nombres(self)
        self.cedula = texto_limpio(self.cedula)
        super().save(*args, **kwargs)

    def nombre_completo(self):
        return ('%s %s' % (self.apellidos, self.nombres)).strip()

    def numero_whatsapp(self):
        """El numero listo para el enlace de WhatsApp."""
        return numero_para_whatsapp(self.whatsapp or self.telefono)

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


class Division(ModeloBase):
    """La categoria por EDAD, aparte del horario en que entrena.

    El grupo dice cuando entrena (manana, tarde, noche) y ahi pueden estar
    mezclados chicos de varias edades. La division dice contra quien le toca
    jugar: sub-10, sub-12, etc. Sale sola de la edad de cada uno.
    """

    nombre = models.CharField(max_length=40, verbose_name='Nombre', help_text='Ejemplo: SUB-10.')
    edad_minima = models.PositiveSmallIntegerField(verbose_name='Desde (anios)')
    edad_maxima = models.PositiveSmallIntegerField(verbose_name='Hasta (anios)')
    orden = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Division'
        verbose_name_plural = 'Divisiones'
        ordering = ['orden', 'edad_minima']

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.nombre = texto_limpio(self.nombre, mayusculas=True)
        super().save(*args, **kwargs)

    def rango_texto(self):
        return 'de %s a %s anios' % (self.edad_minima, self.edad_maxima)

    def le_corresponde(self, edad):
        return self.edad_minima <= edad <= self.edad_maxima

    def rango_de_nacimiento(self, hoy=None):
        """Entre que fechas nacieron los que hoy caen en esta division.

        Sirve para filtrar en la base sin recorrer jugador por jugador.
        """
        hoy = hoy or date.today()
        desde = restar_anios(hoy, self.edad_maxima + 1) + timedelta(days=1)
        hasta = restar_anios(hoy, self.edad_minima)
        return desde, hasta

    def jugadores_activos(self):
        """Los que hoy caen en esta division, sin importar en que grupo entrenan."""
        return [
            jugador for jugador in Jugador.objects.filter(
                estado=JUGADOR_ACTIVO).select_related('categoria')
            if self.le_corresponde(jugador.edad())
        ]


class Jugador(ModeloBase):
    nombre1 = models.CharField(max_length=60, blank=True, verbose_name='Primer nombre')
    nombre2 = models.CharField(max_length=60, blank=True, verbose_name='Segundo nombre')
    apellido1 = models.CharField(max_length=60, blank=True, verbose_name='Primer apellido')
    apellido2 = models.CharField(max_length=60, blank=True, verbose_name='Segundo apellido')
    nombres = models.CharField(max_length=100, blank=True, verbose_name='Nombres')
    apellidos = models.CharField(max_length=100, blank=True, verbose_name='Apellidos')
    apodo = models.CharField(
        max_length=40, blank=True, verbose_name='Como le dicen',
        help_text='El apodo con el que le gusta que le llamen. Sale en la lista y en la asistencia.'
    )
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
    descuento = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Descuento (%)',
        help_text='Beca, hermano en la academia, convenio... Se aplica sobre el valor del mes.'
    )
    descuento_monto = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name='Descuento (en dolares)',
        help_text='Si el acuerdo fue "paga 5 menos" en vez de un porcentaje. '
                  'Si pones los dos, manda este.'
    )
    motivo_descuento = models.CharField(max_length=120, blank=True, verbose_name='Motivo del descuento')
    # ---- salud: lo que el profe tiene que saber antes de exigirle ----
    condicion_medica = models.TextField(
        blank=True, verbose_name='Enfermedad o condicion',
        help_text='Lo que tiene: del corazon, asma, epilepsia, diabetes, '
                  'condromalacia, fascitis plantar, una lesion vieja... '
                  'Se anota al inscribirlo y se va actualizando.'
    )
    cuidados = models.TextField(
        blank=True, verbose_name='Que puede hacer y que no',
        help_text='Lo que hay que cuidarle por esa condicion: nada de saltos, '
                  'no doble jornada, que avise si le duele... Sale marcado en su '
                  'ficha y en la lista de asistencia.'
    )
    alergias = models.CharField(
        max_length=200, blank=True, verbose_name='Alergias',
        help_text='A medicinas, comidas, picaduras. Vacio = ninguna conocida.'
    )
    tipo_sangre = models.CharField(
        max_length=5, blank=True, verbose_name='Tipo de sangre',
        help_text='Por si pasa algo en la cancha. Ejemplo: O+, A-.'
    )
    cobro_activo = models.BooleanField(
        default=True, verbose_name='Cobrarle cada mes',
        help_text='Mientras este prendido, al terminar un mes se le genera solo el siguiente. '
                  'Apagalo si dejo de venir o si por ahora no se le cobra.'
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
        repartir_nombres(self)
        self.apodo = texto_limpio(self.apodo, mayusculas=True)
        self.cedula = texto_limpio(self.cedula)
        super().save(*args, **kwargs)

    def nombre_completo(self):
        return ('%s %s' % (self.apellidos, self.nombres)).strip()

    def numero_whatsapp(self):
        """Su propio numero, para escribirle directo (los grandes lo usan)."""
        return numero_para_whatsapp(self.telefono)

    def whatsapp_de_contacto(self):
        """A quien se le escribe: al representante si lo tiene, si no, a el."""
        if self.representante_id and self.representante.numero_whatsapp():
            return self.representante.numero_whatsapp()
        return self.numero_whatsapp()

    def tiene_cuidados(self):
        return bool((self.cuidados or '').strip()
                    or (self.condicion_medica or '').strip())

    def resumen_salud(self):
        """Una linea con lo que hay que saber de su salud, para las listas."""
        partes = []
        if (self.condicion_medica or '').strip():
            partes.append(self.condicion_medica.strip())
        if (self.cuidados or '').strip():
            partes.append(self.cuidados.strip())
        if (self.alergias or '').strip():
            partes.append('alergico a %s' % self.alergias.strip())
        return ' · '.join(partes)

    def division(self):
        """La categoria por edad que le toca hoy. Sale sola de su edad."""
        edad = self.edad()
        for division in Division.objects.filter(activo=True):
            if division.le_corresponde(edad):
                return division
        return None

    def division_texto(self):
        division = self.division()
        return division.nombre if division else 'SIN DIVISION'

    def como_le_dicen(self):
        """El apodo si lo tiene; si no, su primer nombre."""
        if self.apodo:
            return self.apodo
        return (self.nombres or '').split(' ')[0]

    def nombre_con_apodo(self):
        """Para las listas: APELLIDOS NOMBRES (APODO)."""
        if not self.apodo:
            return self.nombre_completo()
        return '%s (%s)' % (self.nombre_completo(), self.apodo)

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

    def precio_base(self):
        """Lo que cuesta el mes de su grupo, antes del descuento."""
        return self.categoria.valor_mensual

    def valor_descuento(self):
        """Cuanto se le rebaja en dolares.

        El acuerdo se pudo hacer de dos maneras: "el 10 por ciento" o "5
        dolares menos". Si estan los dos, manda el de dolares, que es como la
        gente lo dice en voz alta.
        """
        if self.descuento_monto:
            return min(Decimal(self.descuento_monto), self.precio_base()).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)
        if not self.descuento:
            return Decimal('0.00')
        rebaja = self.precio_base() * Decimal(self.descuento) / Decimal('100')
        return rebaja.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def texto_rebaja(self):
        """Como se dice el descuento: en porcentaje o en plata."""
        if self.descuento_monto:
            return '$ %s' % normalizar_decimal(self.descuento_monto)
        if self.descuento:
            return '%s%%' % normalizar_decimal(self.descuento)
        return ''

    def tiene_rebaja(self):
        return bool(self.descuento_monto or self.descuento)

    def valor_mensual_vigente(self):
        """Lo que realmente paga este jugador cada mes."""
        valor = self.precio_base() - self.valor_descuento()
        if valor < 0:
            valor = Decimal('0.00')
        return valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def explicacion_precio(self):
        """Texto corto para mostrar de donde sale el valor."""
        partes = ['valor de %s' % self.categoria.nombre]
        if self.tiene_rebaja():
            detalle = '%s de descuento' % self.texto_rebaja()
            if self.motivo_descuento:
                detalle += ' (%s)' % self.motivo_descuento
            partes.append(detalle)
        return ', '.join(partes)

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
    def progreso(self, desde=None, hasta=None):
        """Como va en cada indicador: primera marca, ultima, mejor y si mejoro.

        Con `desde` y `hasta` se mira solo un tramo (por ejemplo, como estuvo
        en vacaciones o desde que empezo el campeonato). Cada indicador trae
        ademas su `historial`: TODAS las tomas de ese tramo, con su fecha.
        """
        mediciones = list(self.mediciones.select_related('indicador', 'evaluacion'))
        if desde:
            mediciones = [m for m in mediciones if m.dia() >= desde]
        if hasta:
            mediciones = [m for m in mediciones if m.dia() <= hasta]

        mediciones.sort(key=lambda m: (m.indicador.area, m.indicador.orden,
                                       m.indicador.nombre, m.dia()))

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

    def retrocesos(self):
        """En que indicadores su ultima marca es PEOR que la anterior.

        Compara las dos ultimas tomas, no la primera con la ultima: lo que
        interesa aqui es si viene bajando ahora, no como empezo el anio.
        """
        bajas = []
        for fila in self.progreso():
            historial = fila['historial']
            if len(historial) < 2:
                continue

            anterior, ultima = historial[-2], historial[-1]
            indicador = fila['indicador']
            if indicador.es_mejora(anterior.valor, ultima.valor) is not False:
                continue

            bajas.append({
                'indicador': indicador,
                'antes': anterior,
                'ahora': ultima,
                'desde': indicador.formatear(anterior.valor),
                'hasta': indicador.formatear(ultima.valor),
            })
        return bajas

    def linea_base(self):
        """Con que llego: sus marcas de la prueba INICIAL.

        Si la academia marco un tipo de evaluacion como inicial, esa es la
        base. Si no hay ninguna, la base es la primera vez que se le midio
        cada cosa, que para el caso es lo mismo: su punto de partida.
        """
        tomas = list(self.mediciones.select_related('indicador', 'evaluacion', 'evaluacion__tipo'))
        if not tomas:
            return {}

        de_la_inicial = [m for m in tomas if m.evaluacion.tipo and m.evaluacion.tipo.es_inicial]
        candidatas = de_la_inicial or tomas

        base = {}
        for medicion in candidatas:
            guardada = base.get(medicion.indicador_id)
            if guardada is None or medicion.dia() < guardada.dia():
                base[medicion.indicador_id] = medicion
        return base

    def como_llego_y_como_va(self):
        """Que tanto cambio desde su prueba inicial hasta hoy.

        Es la pregunta del representante: "con que llego mi hijo y como va".
        Solo salen los indicadores que tienen las dos marcas.
        """
        base = self.linea_base()
        if not base:
            return []

        filas = []
        for fila in self.progreso():
            indicador = fila['indicador']
            partida = base.get(indicador.id)
            ultima = fila['ultima']
            if partida is None or ultima is None or partida.pk == ultima.pk:
                continue

            filas.append({
                'indicador': indicador,
                'llego': partida,
                'ahora': ultima,
                'diferencia': ultima.valor - partida.valor,
                'mejoro': indicador.es_mejora(partida.valor, ultima.valor),
                'dias': (ultima.dia() - partida.dia()).days,
            })
        return filas

    def resumen_desde_la_base(self):
        """Cuantas cosas mejoro y cuantas no, desde su prueba inicial."""
        filas = self.como_llego_y_como_va()
        if not filas:
            return None

        mejoraron = len([f for f in filas if f['mejoro'] is True])
        bajaron = len([f for f in filas if f['mejoro'] is False])
        return {
            'total': len(filas),
            'mejoraron': mejoraron,
            'bajaron': bajaron,
            'igual': len(filas) - mejoraron - bajaron,
            'desde': min(f['llego'].dia() for f in filas),
        }

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

    def afinidad_posiciones(self):
        """Que tan bien le queda cada puesto de la cancha, de 0 a 100.

        Toma los puntajes por area de la tela de arania y los pondera con el
        peso que cada posicion le da a esa area. Solo cuentan las areas que ya
        se le midieron, asi que mientras mas completo este el jugador, mas
        confiable es la sugerencia.
        """
        radar = self.radar()
        puntajes = {e['area']: e for e in radar['ejes']}
        medidas = [a for a, e in puntajes.items() if e['medidos']]
        if not medidas:
            return []

        resultado = []
        for posicion in Posicion.objects.filter(activo=True):
            pesos = posicion.pesos_por_area()
            suma = 0.0
            total_pesos = 0
            for area in medidas:
                peso = pesos.get(area, 0)
                if peso:
                    suma += puntajes[area]['puntaje'] * peso
                    total_pesos += peso
            if not total_pesos:
                continue
            resultado.append({
                'posicion': posicion,
                'puntaje': round(suma / total_pesos, 1),
                'es_la_que_le_gusta': self.posicion_id == posicion.id,
                'areas_usadas': len(medidas),
            })

        resultado.sort(key=lambda x: -x['puntaje'])
        return resultado

    def posicion_sugerida(self):
        afinidades = self.afinidad_posiciones()
        return afinidades[0] if afinidades else None

    def fortalezas(self):
        return [x for x in self.comparativa_categoria() if x['posicion'] == 'fortaleza']

    def aspectos_a_mejorar(self):
        return [x for x in self.comparativa_categoria() if x['posicion'] == 'mejorar']

    def ultima_evaluacion(self):
        medicion = self.mediciones.select_related('evaluacion').order_by('-evaluacion__fecha').first()
        return medicion.evaluacion if medicion else None

    # --- Cuentas del jugador --------------------------------------------
    def dia_de_cobro(self):
        """El dia del mes en que se le cobra: el mismo en que entro."""
        return self.fecha_ingreso.day if self.fecha_ingreso else 10

    def periodo_de_cobro(self, mes, anio):
        """Los dias que cubre su mensualidad de ese mes.

        Arranca el dia en que ingreso y termina el dia anterior del mes
        siguiente, por eso no siempre son 30 dias: puede ser 28, 29, 30 o 31.
        """
        inicio = dia_del_mes(anio, mes, self.dia_de_cobro())
        otro_mes, otro_anio = mes_siguiente(mes, anio)
        inicio_siguiente = dia_del_mes(otro_anio, otro_mes, self.dia_de_cobro())
        return inicio, inicio_siguiente - timedelta(days=1)

    def ya_estaba_en(self, mes, anio):
        """True si el jugador ya habia ingresado en ese mes."""
        if not self.fecha_ingreso:
            return True
        return (anio, mes) >= (self.fecha_ingreso.year, self.fecha_ingreso.month)

    def controles_fisicos(self):
        """Su crecimiento, del mas viejo al mas nuevo."""
        return self.controles.all().order_by('fecha')

    def ultimo_control(self):
        return self.controles.all().order_by('-fecha').first()

    def crecimiento(self):
        """Cuanto cambio entre el primer control y el ultimo.

        No es rendimiento: es un ninio creciendo. Sirve para acompaniarlo, no
        para compararlo con el resto.
        """
        controles = list(self.controles_fisicos())
        if len(controles) < 2:
            return None

        primero, ultimo = controles[0], controles[-1]
        return {
            'primero': primero,
            'ultimo': ultimo,
            'peso': ultimo.diferencia_de_peso(primero),
            'estatura': ultimo.diferencia_de_estatura(primero),
            'dias': (ultimo.fecha - primero.fecha).days,
        }

    def ultima_mensualidad(self):
        """La ultima que se le genero, por el periodo que cubre."""
        return self.mensualidades.order_by(
            models.F('periodo_inicio').desc(nulls_last=True), '-anio', '-mes').first()

    def proximo_periodo(self):
        """Que mes le tocaria despues, y desde que dia hasta que dia.

        El primero arranca el dia en que ingreso. Los siguientes arrancan el
        dia despues de que termino el anterior, asi no se salta ni se repite
        ningun dia, aunque las fechas se hayan corregido a mano.
        """
        ultima = self.ultima_mensualidad()

        if ultima is None:
            if not self.fecha_ingreso:
                return None
            return self.periodo_de_cobro(self.fecha_ingreso.month, self.fecha_ingreso.year)

        if not ultima.periodo_fin:
            return None

        inicio = ultima.periodo_fin + timedelta(days=1)
        return inicio, un_mes_despues(inicio) - timedelta(days=1)

    def meses_adelantados(self, referencia=None):
        """Los meses que ya se le abrieron y todavia no empiezan.

        Estando en septiembre lo normal es tener abierto el mes que corre y,
        como mucho, el siguiente. Si ya hay uno que arranca en el futuro,
        abrir otro seria irse dos meses adelante.
        """
        referencia = referencia or date.today()
        return self.mensualidades.filter(periodo_inicio__gt=referencia).order_by('periodo_inicio')

    def mes_ya_adelantado(self, referencia=None):
        """El mes que ya tiene abierto por delante, si hay alguno."""
        return self.meses_adelantados(referencia).first()

    def se_le_cobra(self):
        """Solo se le generan meses nuevos si esta activo y con el cobro prendido."""
        return self.estado == JUGADOR_ACTIVO and self.cobro_activo

    def mensualidades_en_orden(self):
        """Todas sus mensualidades, de la mas vieja a la mas nueva."""
        return self.mensualidades.order_by(
            models.F('periodo_inicio').asc(nulls_last=True), 'anio', 'mes')

    def mensualidades_pendientes(self):
        return self.mensualidades.filter(estado=MENSUALIDAD_PENDIENTE).order_by(
            models.F('periodo_inicio').asc(nulls_last=True), 'anio', 'mes')

    def cubierto_hasta(self):
        """Hasta que dia tiene pagada su asistencia, sin huecos.

        Se van sumando los meses saldados desde el mas viejo; en cuanto
        aparece uno pendiente ahi se corta, porque de ahi en adelante debe.
        """
        cubierto = None
        for mensualidad in self.mensualidades_en_orden():
            if mensualidad.estado == MENSUALIDAD_PENDIENTE:
                break
            cubierto = mensualidad.periodo_fin or mensualidad.fecha_vencimiento
        return cubierto

    def debe_desde(self):
        """El dia en que arranca la deuda mas vieja."""
        primera = self.mensualidades_pendientes().first()
        if not primera:
            return None
        return primera.periodo_inicio or primera.fecha_vencimiento

    def historial_de_pagos(self):
        """Todo lo que se le cobro, agrupado por anio y del mas nuevo al mas viejo.

        Devuelve una lista de anios con sus meses y los totales de cada uno,
        mas el total general. Es lo que se le muestra al representante cuando
        pregunta "cuanto he pagado".
        """
        por_anio = {}
        for mensualidad in self.mensualidades_en_orden():
            anio = por_anio.setdefault(mensualidad.anio, {
                'anio': mensualidad.anio,
                'meses': [],
                'pagado': Decimal('0.00'),
                'pendiente': Decimal('0.00'),
                'cuantos_pagados': 0,
            })
            anio['meses'].append(mensualidad)

            if mensualidad.esta_pagada():
                anio['pagado'] += mensualidad.valor
                anio['cuantos_pagados'] += 1
            elif mensualidad.estado == MENSUALIDAD_PENDIENTE:
                anio['pendiente'] += mensualidad.valor

        anios = sorted(por_anio.values(), key=lambda x: -x['anio'])
        for anio in anios:
            anio['meses'].reverse()

        return {
            'anios': anios,
            'total_pagado': sum((a['pagado'] for a in anios), Decimal('0.00')),
            'total_pendiente': sum((a['pendiente'] for a in anios), Decimal('0.00')),
            'cuantos': sum(len(a['meses']) for a in anios),
        }

    def estado_de_cuenta(self):
        """Una frase que resume como va con los pagos."""
        if not self.mensualidades.exists():
            return 'Todavia no tiene mensualidades.'

        meses = self.meses_que_debe()
        if not meses:
            cubierto = self.cubierto_hasta()
            if cubierto:
                return 'Al dia, cubierto hasta el %s.' % cubierto.strftime('%d/%m/%Y')
            return 'Al dia.'

        texto = 'Debe %s mes%s' % (meses, '' if meses == 1 else 'es')
        desde = self.debe_desde()
        if desde:
            texto += ', desde el %s' % desde.strftime('%d/%m/%Y')
        cubierto = self.cubierto_hasta()
        if cubierto:
            texto += ' (pago hasta el %s)' % cubierto.strftime('%d/%m/%Y')
        return texto + '.'

    def meses_que_debe(self):
        return self.mensualidades_pendientes().count()

    def total_que_debe(self):
        total = sum((m.valor for m in self.mensualidades_pendientes()), Decimal('0.00'))
        return total.quantize(Decimal('0.01'))

    def mensualidades_atrasadas(self, dia=None):
        return [m for m in self.mensualidades_pendientes() if m.esta_atrasada(dia)]

    def esta_al_dia(self):
        return not self.mensualidades_atrasadas()

    def dias_de_atraso(self, dia=None):
        """Los dias de la deuda mas vieja."""
        atrasadas = self.mensualidades_atrasadas(dia)
        return max((m.dias_de_atraso(dia) for m in atrasadas), default=0)

    def cuantas_mediciones(self):
        return self.mediciones.count()

    def primera_medicion(self):
        """La toma mas vieja, para saber desde cuando hay historia."""
        tomas = list(self.mediciones.select_related('evaluacion'))
        return min(tomas, key=lambda m: m.dia()) if tomas else None

    def ultima_medicion(self):
        tomas = list(self.mediciones.select_related('evaluacion'))
        return max(tomas, key=lambda m: m.dia()) if tomas else None

    def medicion_inicial(self, indicador):
        """Primera marca del jugador en ese indicador (su linea base)."""
        tomas = list(Medicion.objects.filter(
            jugador=self, indicador=indicador).select_related('evaluacion'))
        return min(tomas, key=lambda m: m.dia()) if tomas else None

    # --- Tela de arania -------------------------------------------------
    def radar(self):
        """Puntaje 0-100 por area, para dibujar la tela de arania.

        Como los indicadores no se miden igual, cada uno se lleva a 0-100:
          - escala 1 a 10  -> contra su propio maximo (absoluto)
          - numeros y tiempos -> contra el mejor y el peor de SU GRUPO
            (en los tiempos se invierte, porque ahi menos es mejor)
        Devuelve tambien el detalle por indicador para el texto de apoyo.
        """
        from collections import defaultdict

        companieros = list(
            Jugador.objects.filter(categoria=self.categoria, estado=JUGADOR_ACTIVO)
            .values_list('pk', flat=True)
        )

        por_area = defaultdict(list)
        detalle = []

        for fila in self.progreso():
            indicador = fila['indicador']
            valor = fila['ultima'].valor

            if indicador.tipo_medida in MEDIDAS_ABSOLUTAS:
                # Estas tienen techo propio (10, 100%, si/no): se comparan
                # contra ese techo y no contra el resto del grupo.
                tope_bajo, tope_alto = TOPES_ABSOLUTOS[indicador.tipo_medida]
                minimo = indicador.valor_minimo if indicador.valor_minimo is not None else tope_bajo
                maximo = indicador.valor_maximo if indicador.valor_maximo is not None else tope_alto
                referencia = 'escala'
            else:
                # Ultimo valor de cada jugador activo del grupo en ese indicador.
                valores = []
                for jugador_id in companieros:
                    marca = Medicion.objects.filter(
                        jugador_id=jugador_id, indicador=indicador
                    ).order_by('-evaluacion__fecha').first()
                    if marca:
                        valores.append(marca.valor)
                if len(valores) < 2:
                    continue  # sin con quien comparar, no se puede normalizar
                minimo, maximo = min(valores), max(valores)
                referencia = 'grupo'

            if maximo == minimo:
                puntaje = 50.0
            else:
                puntaje = float((valor - minimo) * 100 / (maximo - minimo))
                if indicador.mejor_es == MEJOR_MENOR:
                    puntaje = 100.0 - puntaje
            puntaje = round(max(0.0, min(100.0, puntaje)), 1)

            por_area[indicador.area].append(puntaje)
            detalle.append({
                'indicador': indicador,
                'valor_texto': fila['ultima'].texto(),
                'puntaje': puntaje,
                'referencia': referencia,
            })

        ejes = []
        for area, etiqueta in AREAS_INDICADOR:
            puntajes = por_area.get(area, [])

            # Las cuatro de siempre salen aunque esten vacias, para que la tela
            # tenga forma. Las de portero y mental solo si se le midieron: a un
            # jugador de campo no le vamos a dibujar un eje de arquero en cero.
            if area not in AREAS_BASE and not puntajes:
                continue

            ejes.append({
                'area': area,
                'etiqueta': etiqueta,
                'puntaje': round(sum(puntajes) / len(puntajes), 1) if puntajes else 0.0,
                'medidos': len(puntajes),
                'color': COLORES_AREA.get(area, 'secondary'),
            })

        medidos = [e for e in ejes if e['medidos']]
        return {
            'ejes': ejes,
            'detalle': sorted(detalle, key=lambda x: x['puntaje']),
            'areas_medidas': len(medidos),
            'promedio': round(sum(e['puntaje'] for e in medidos) / len(medidos), 1) if medidos else 0.0,
        }


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
        return numero_para_whatsapp(self.telefono)


# ============================================================================
# MENSUALIDADES
# ============================================================================
MENSUALIDAD_PENDIENTE = 1
MENSUALIDAD_PAGADO = 2
MENSUALIDAD_EXONERADO = 3

ESTADOS_MENSUALIDAD = (
    (MENSUALIDAD_PENDIENTE, 'PENDIENTE'),
    (MENSUALIDAD_PAGADO, 'PAGADO'),
    (MENSUALIDAD_EXONERADO, 'EXONERADO'),
)

PAGO_EFECTIVO = 1
PAGO_TRANSFERENCIA = 2
PAGO_OTRO = 3

FORMAS_PAGO = (
    (PAGO_EFECTIVO, 'EFECTIVO'),
    (PAGO_TRANSFERENCIA, 'TRANSFERENCIA'),
    (PAGO_OTRO, 'OTRO'),
)

MESES = (
    (1, 'ENERO'), (2, 'FEBRERO'), (3, 'MARZO'), (4, 'ABRIL'),
    (5, 'MAYO'), (6, 'JUNIO'), (7, 'JULIO'), (8, 'AGOSTO'),
    (9, 'SEPTIEMBRE'), (10, 'OCTUBRE'), (11, 'NOVIEMBRE'), (12, 'DICIEMBRE'),
)

MESES_DICT = dict(MESES)

# Cuando no se conocen las fechas exactas del periodo, se asume un mes de 30 dias.
DIAS_DEL_MES_POR_DEFECTO = 30


class Mensualidad(ModeloBase):
    """La cuota de un jugador en un mes.

    El valor se copia al generarla, asi que si despues sube el precio de la
    categoria las mensualidades viejas no cambian.
    """

    jugador = models.ForeignKey(
        Jugador, on_delete=models.CASCADE, related_name='mensualidades', verbose_name='Jugador'
    )
    mes = models.IntegerField(choices=MESES, verbose_name='Mes')
    anio = models.PositiveSmallIntegerField(verbose_name='Anio')
    valor = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Valor a pagar')
    valor_completo = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name='Valor del mes completo',
        help_text='Lo que costaria el mes entero, antes de descontar semanas.'
    )
    descuento_aplicado = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name='Descuento aplicado (%)'
    )
    descuento_monto = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name='Descuento de este mes (en dolares)',
        help_text='Para cuando el acuerdo se hablo en plata: "este mes paga 5 menos".'
    )
    motivo_descuento = models.CharField(
        max_length=120, blank=True, verbose_name='Por que el descuento',
        help_text='El descuento puede ser de unos meses y despues no: por eso el '
                  'motivo se guarda en el mes, no en la persona.'
    )
    motivo_ajuste = models.CharField(max_length=150, blank=True, verbose_name='Motivo del ajuste')
    periodo_inicio = models.DateField(blank=True, null=True, verbose_name='El periodo arranca el')
    periodo_fin = models.DateField(blank=True, null=True, verbose_name='y termina el')
    dias_ausente = models.PositiveSmallIntegerField(
        default=0, verbose_name='Dias que avisó que no viene',
        help_text='Se le cobran solo los dias del periodo en que si puede entrenar.'
    )
    fecha_vencimiento = models.DateField(verbose_name='Se vence el')
    estado = models.IntegerField(choices=ESTADOS_MENSUALIDAD, default=MENSUALIDAD_PENDIENTE,
                                 verbose_name='Estado')
    fecha_pago = models.DateField(blank=True, null=True, verbose_name='Fecha de pago')
    forma_pago = models.IntegerField(choices=FORMAS_PAGO, blank=True, null=True, verbose_name='Forma de pago')
    comprobante = models.CharField(max_length=60, blank=True, verbose_name='Comprobante')
    observacion = models.CharField(max_length=250, blank=True, verbose_name='Observacion')

    class Meta:
        verbose_name = 'Mensualidad'
        verbose_name_plural = 'Mensualidades'
        ordering = ['-anio', '-mes', 'jugador__apellidos']
        constraints = [
            # La identidad de una mensualidad es el periodo que cubre, no el mes
            # del calendario: hay jugadores cuyo ciclo no arranca el dia 1.
            models.UniqueConstraint(fields=['jugador', 'periodo_inicio'],
                                    name='mensualidad_unica_por_periodo')
        ]
        indexes = [
            models.Index(fields=['anio', 'mes']),
            models.Index(fields=['estado', 'fecha_vencimiento']),
        ]

    def __str__(self):
        return '%s - %s %s' % (self.jugador.nombre_completo(), self.nombre_mes(), self.anio)

    def save(self, *args, **kwargs):
        self.observacion = texto_limpio(self.observacion)
        self.motivo_ajuste = texto_limpio(self.motivo_ajuste)
        self.motivo_descuento = texto_limpio(self.motivo_descuento)
        self.comprobante = texto_limpio(self.comprobante, mayusculas=True)
        if not self.valor_completo:
            self.valor_completo = self.valor
        if self.periodo_inicio:
            # El mes es solo la etiqueta: manda el dia en que arranca el periodo.
            self.mes = self.periodo_inicio.month
            self.anio = self.periodo_inicio.year
        super().save(*args, **kwargs)

    def dias_del_periodo(self):
        """Cuantos dias cubre esta mensualidad.

        El periodo va del dia en que el jugador ingreso al dia anterior del mes
        siguiente, asi que no siempre son 30: puede ser 28, 29, 30 o 31.
        """
        if self.periodo_inicio and self.periodo_fin:
            return (self.periodo_fin - self.periodo_inicio).days + 1
        return DIAS_DEL_MES_POR_DEFECTO

    def dias_cobrados(self):
        return max(self.dias_del_periodo() - (self.dias_ausente or 0), 0)

    def valor_por_dia(self):
        dias = self.dias_del_periodo() or 1
        return (self.valor_completo / Decimal(dias)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)

    def valor_con_descuento(self):
        """El precio del mes ya con la rebaja de ESE mes, sin contar ausencias."""
        valor = self.valor_completo - self.rebaja_del_mes()
        return max(valor, Decimal('0.00')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)

    def recalcular_por_ausencia(self):
        """Cobra solo los dias del periodo en que el jugador si entrena.

        Primero se le hace el descuento del mes y sobre eso se prorratea, que
        es el orden en que se explica: 25 menos el 10%% es 22,50, y de ahi se
        bajan los dias que aviso. Los dias son los REALES del periodo, no los
        de un mes teorico: si tiene 31 y falta 7, paga 24/31.
        """
        dias = self.dias_del_periodo() or 1
        ausente = min(max(self.dias_ausente or 0, 0), dias)
        self.dias_ausente = ausente
        proporcion = Decimal(dias - ausente) / Decimal(dias)
        self.valor = (self.valor_con_descuento() * proporcion).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
        return self.valor

    def tiene_ajuste(self):
        return bool(self.dias_ausente)

    def tiene_descuento(self):
        return bool(self.descuento_monto or self.descuento_aplicado)

    def rebaja_del_mes(self):
        """Cuanto se le baja este mes, en dolares."""
        if self.descuento_monto:
            return min(Decimal(self.descuento_monto), self.valor_completo).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)
        if not self.descuento_aplicado:
            return Decimal('0.00')
        rebaja = self.valor_completo * Decimal(self.descuento_aplicado) / Decimal('100')
        return rebaja.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def texto_descuento(self):
        """De donde sale lo que paga este mes: 25 menos 10 por ciento = 22,50."""
        if not self.tiene_descuento():
            return ''
        if self.descuento_monto:
            como = '$ %s' % normalizar_decimal(self.descuento_monto)
        else:
            como = '%s%%' % normalizar_decimal(self.descuento_aplicado)
        texto = '%s de descuento sobre %s, paga %s' % (
            como, self.valor_completo, self.valor_con_descuento())
        if self.motivo_descuento:
            texto += ' (%s)' % self.motivo_descuento
        return texto

    def texto_periodo(self):
        if not (self.periodo_inicio and self.periodo_fin):
            return self.periodo()
        return 'del %s al %s' % (self.periodo_inicio.strftime('%d/%m/%Y'),
                                 self.periodo_fin.strftime('%d/%m/%Y'))

    def texto_ajuste(self):
        if not self.tiene_ajuste():
            return ''
        dias = self.dias_ausente
        texto = 'avisó que no viene %s dia%s de %s' % (
            dias, '' if dias == 1 else 's', self.dias_del_periodo())
        if self.motivo_ajuste:
            texto += ' (%s)' % self.motivo_ajuste
        return texto

    def nombre_mes(self):
        return MESES_DICT.get(self.mes, '')

    def periodo(self):
        return '%s %s' % (self.nombre_mes().title(), self.anio)

    def esta_pagada(self):
        return self.estado == MENSUALIDAD_PAGADO

    def esta_atrasada(self, dia=None):
        """Pendiente y ya paso la fecha de vencimiento."""
        if self.estado != MENSUALIDAD_PENDIENTE:
            return False
        return (dia or date.today()) > self.fecha_vencimiento

    def dias_de_atraso(self, dia=None):
        if not self.esta_atrasada(dia):
            return 0
        return ((dia or date.today()) - self.fecha_vencimiento).days

    def estado_visible(self):
        """PENDIENTE se convierte en ATRASADO cuando ya paso la fecha."""
        if self.esta_atrasada():
            return 'ATRASADO'
        return self.get_estado_display()

    def color(self):
        if self.estado == MENSUALIDAD_PAGADO:
            return 'success'
        if self.estado == MENSUALIDAD_EXONERADO:
            return 'info'
        return 'danger' if self.esta_atrasada() else 'warning'


# ============================================================================
# EVALUACIONES: que se le mide a cada jugador y como va mejorando
# ============================================================================
AREA_TECNICA = 1
AREA_FISICA = 2
AREA_TACTICA = 3
AREA_ACTITUD = 4
AREA_PORTERO = 5       # lo que solo se le mide al arquero
AREA_MENTAL = 6        # concentracion, decision bajo presion, reaccion

# Las cuatro que tiene cualquier jugador de campo: son los ejes fijos del radar.
AREAS_BASE = (AREA_TECNICA, AREA_FISICA, AREA_TACTICA, AREA_ACTITUD)

AREAS_INDICADOR = (
    (AREA_TECNICA, 'TECNICA'),
    (AREA_FISICA, 'FISICA'),
    (AREA_TACTICA, 'TACTICA'),
    (AREA_ACTITUD, 'ACTITUD'),
    (AREA_PORTERO, 'PORTERO'),
    (AREA_MENTAL, 'MENTAL'),
)

COLORES_AREA = {
    AREA_TECNICA: 'success',
    AREA_FISICA: 'danger',
    AREA_TACTICA: 'primary',
    AREA_ACTITUD: 'warning',
    AREA_PORTERO: 'info',
    AREA_MENTAL: 'dark',
}

MEDIDA_ESCALA = 1      # 1 a 10, lo califica el entrenador
MEDIDA_NUMERO = 2      # una cantidad con unidad: metros, repeticiones, goles
MEDIDA_TIEMPO = 3      # segundos: aqui mejorar es bajar el numero
MEDIDA_PORCENTAJE = 4  # 0 a 100: aciertos sobre intentos
MEDIDA_SI_NO = 5       # 1 o 0: lo hace o no lo hace

TIPOS_MEDIDA = (
    (MEDIDA_ESCALA, 'ESCALA 1 A 10'),
    (MEDIDA_NUMERO, 'NUMERO CON UNIDAD'),
    (MEDIDA_TIEMPO, 'TIEMPO EN SEGUNDOS'),
    (MEDIDA_PORCENTAJE, 'PORCENTAJE (0 A 100)'),
    (MEDIDA_SI_NO, 'SI O NO (1 O 0)'),
)

# Las que se comparan contra un maximo fijo y no contra el resto del grupo.
MEDIDAS_ABSOLUTAS = (MEDIDA_ESCALA, MEDIDA_PORCENTAJE, MEDIDA_SI_NO)

# El techo natural de cada una de esas.
TOPES_ABSOLUTOS = {
    MEDIDA_ESCALA: (1, 10),
    MEDIDA_PORCENTAJE: (0, 100),
    MEDIDA_SI_NO: (0, 1),
}

MEJOR_MAYOR = 1
MEJOR_MENOR = 2

SENTIDOS_MEJORA = (
    (MEJOR_MAYOR, 'MIENTRAS MAS ALTO, MEJOR'),
    (MEJOR_MENOR, 'MIENTRAS MAS BAJO, MEJOR'),
)


class Posicion(ModeloBase):
    """Puesto en la cancha.

    Cada posicion dice cuanto pesa cada area para jugar ahi (de 0 a 3). Con eso
    el sistema calcula que tan bien le queda cada puesto a un jugador segun lo
    que se le ha medido. Ejemplo: al arquero le pesa mas lo fisico y la actitud;
    al volante ofensivo, la tecnica y la tactica.
    """

    nombre = models.CharField(max_length=60, unique=True, verbose_name='Nombre')
    abreviatura = models.CharField(max_length=6, blank=True, verbose_name='Abreviatura')
    peso_tecnica = models.PositiveSmallIntegerField(default=1, verbose_name='Cuanto pesa la tecnica (0 a 3)')
    peso_fisica = models.PositiveSmallIntegerField(default=1, verbose_name='Cuanto pesa lo fisico (0 a 3)')
    peso_tactica = models.PositiveSmallIntegerField(default=1, verbose_name='Cuanto pesa la tactica (0 a 3)')
    peso_actitud = models.PositiveSmallIntegerField(default=1, verbose_name='Cuanto pesa la actitud (0 a 3)')
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

    def pesos_por_area(self):
        """{area: peso} para calcular la afinidad del jugador.

        Las areas que no estan aqui (portero, mental) pesan 0: no definen el
        puesto de un jugador de campo. El arquero se mide con las suyas, pero
        eso no cambia si a alguien le queda ser lateral o volante.
        """
        return {
            AREA_TECNICA: self.peso_tecnica,
            AREA_FISICA: self.peso_fisica,
            AREA_TACTICA: self.peso_tactica,
            AREA_ACTITUD: self.peso_actitud,
        }

    def pesos_texto(self):
        partes = []
        for etiqueta, peso in (('tecnica', self.peso_tecnica), ('fisica', self.peso_fisica),
                               ('tactica', self.peso_tactica), ('actitud', self.peso_actitud)):
            if peso:
                partes.append('%s x%s' % (etiqueta, peso))
        return ', '.join(partes) or 'sin pesos definidos'


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
        if self.tipo_medida == MEDIDA_PORCENTAJE:
            return '%'
        if self.tipo_medida == MEDIDA_SI_NO:
            return ''
        return self.unidad

    def formatear(self, valor):
        if valor is None:
            return '-'
        if self.tipo_medida == MEDIDA_SI_NO:
            return 'SI' if valor else 'NO'

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


# Los colores que Bootstrap sabe pintar. Se eligen de una lista para que nadie
# tenga que acordarse de como se escriben.
COLORES_ETIQUETA = (
    ('primary', 'AZUL'),
    ('success', 'VERDE'),
    ('danger', 'ROJO'),
    ('warning', 'AMARILLO'),
    ('info', 'CELESTE'),
    ('secondary', 'GRIS'),
    ('dark', 'NEGRO'),
)


class TipoEvaluacion(ModeloBase):
    """Que clase de prueba es: diagnostica inicial, seguimiento, final...

    El administrador arma su propia lista. La que este marcada como
    `es_inicial` se usa como linea base: el punto de partida del jugador.
    """

    nombre = models.CharField(max_length=80, unique=True, verbose_name='Tipo de evaluacion')
    descripcion = models.CharField(max_length=250, blank=True, verbose_name='Para que sirve')
    color = models.CharField(
        max_length=20, default='secondary', choices=COLORES_ETIQUETA, verbose_name='Color',
        help_text='Con este color sale la etiqueta del tipo en las listas.'
    )
    es_inicial = models.BooleanField(
        default=False, verbose_name='Es la prueba inicial',
        help_text='Marca la linea base del jugador: con que llego a la academia.'
    )
    orden = models.IntegerField(default=0, verbose_name='Orden')
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Tipo de evaluacion'
        verbose_name_plural = 'Tipos de evaluacion'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return '%s' % self.nombre

    def save(self, *args, **kwargs):
        self.nombre = texto_limpio(self.nombre, mayusculas=True)
        self.descripcion = texto_limpio(self.descripcion)
        self.color = texto_limpio(self.color).lower() or 'secondary'
        super().save(*args, **kwargs)


class Evaluacion(ModeloBase):
    """Una jornada de pruebas: fecha, grupo y que indicadores se van a tomar."""

    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name='evaluaciones', verbose_name='Categoria'
    )
    jugador = models.ForeignKey(
        'Jugador', blank=True, null=True, on_delete=models.CASCADE,
        related_name='evaluaciones_propias', verbose_name='Solo a este jugador',
        help_text='Dejalo vacio para tomarle la prueba a todo el grupo. Elige a uno '
                  'cuando es una prueba individual: el que recien llega, o el que '
                  'falto y hay que tomarle aparte.'
    )
    tipo = models.ForeignKey(
        TipoEvaluacion, blank=True, null=True, on_delete=models.SET_NULL,
        related_name='evaluaciones', verbose_name='Tipo de evaluacion'
    )
    fecha = models.DateField(verbose_name='Fecha de la prueba')
    fecha_fin = models.DateField(
        blank=True, null=True, verbose_name='Hasta',
        help_text='Solo si la prueba se toma en varios dias. Al que falto ese dia '
                  'se le mide otro y queda con la fecha en que si vino.'
    )
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

    def ultimo_dia(self):
        """El ultimo dia en que se puede tomar esta prueba."""
        return self.fecha_fin or self.fecha

    def dura_varios_dias(self):
        return bool(self.fecha_fin and self.fecha_fin != self.fecha)

    def abarca(self, dia):
        """True si ese dia cae dentro de la prueba."""
        return self.fecha <= dia <= self.ultimo_dia()

    def dia_para_medir(self, dia=None):
        """Con que fecha se guarda una marca que se toma hoy.

        Si hoy cae dentro de la prueba, queda con el dia real (asi el que
        falto y vino despues queda con SU fecha). Si no, se usa el dia en que
        arranco la prueba.
        """
        dia = dia or date.today()
        return dia if self.abarca(dia) else self.fecha

    def texto_fechas(self):
        if not self.dura_varios_dias():
            return self.fecha.strftime('%d/%m/%Y')
        return 'del %s al %s' % (self.fecha.strftime('%d/%m'),
                                 self.ultimo_dia().strftime('%d/%m/%Y'))

    def indicadores_ordenados(self):
        return self.indicadores.all().order_by('area', 'orden', 'nombre')

    def es_individual(self):
        return self.jugador_id is not None

    def jugadores(self):
        """A quien se le toma: al grupo entero o solo al jugador elegido."""
        if self.jugador_id:
            return Jugador.objects.filter(pk=self.jugador_id)
        return self.categoria.jugadores.filter(estado=JUGADOR_ACTIVO).order_by('apellidos', 'nombres')

    def texto_a_quien(self):
        if self.jugador_id:
            return 'Individual: %s' % self.jugador.nombre_completo()
        return self.categoria.nombre

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
    fecha = models.DateField(
        blank=True, null=True, verbose_name='Dia en que se le tomo',
        help_text='Si no se pone, vale el dia en que arranco la prueba.'
    )
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

    def dia(self):
        """El dia real en que se le tomo la marca a ESTE jugador."""
        return self.fecha or self.evaluacion.fecha

    def anterior(self):
        """La medicion previa del mismo jugador en el mismo indicador."""
        # Se acota en la base por la fecha de la prueba (ninguna medicion es
        # anterior al dia en que arranco la suya) y se afina en Python con el
        # dia real de cada una.
        candidatas = Medicion.objects.filter(
            jugador=self.jugador, indicador=self.indicador,
            evaluacion__fecha__lte=self.dia()
        ).exclude(pk=self.pk).select_related('evaluacion')

        anteriores = [m for m in candidatas if m.dia() < self.dia()]
        if not anteriores:
            return None
        return max(anteriores, key=lambda m: m.dia())

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


# ============================================================================
# NOTAS DEL PROFE SOBRE CADA NINIO
# ============================================================================
NOTA_GENERAL = 1
NOTA_FELICITACION = 2
NOTA_ATENCION = 3
NOTA_SALUD = 4

TIPOS_NOTA = (
    (NOTA_GENERAL, 'COMO VA'),
    (NOTA_FELICITACION, 'PARA FELICITARLO'),
    (NOTA_ATENCION, 'HAY QUE ESTAR PENDIENTE'),
    (NOTA_SALUD, 'SALUD O LESION'),
)

COLORES_NOTA = {
    NOTA_GENERAL: 'secondary',
    NOTA_FELICITACION: 'success',
    NOTA_ATENCION: 'warning',
    NOTA_SALUD: 'danger',
}

ICONOS_NOTA = {
    NOTA_GENERAL: 'bi-chat-left-text',
    NOTA_FELICITACION: 'bi-star-fill',
    NOTA_ATENCION: 'bi-exclamation-triangle-fill',
    NOTA_SALUD: 'bi-bandaid-fill',
}


class Nota(ModeloBase):
    """Lo que el profe anota de un ninio: como va, que le paso, que trabajar.

    Es la memoria de la academia: dentro de un anio nadie se acuerda de por
    que un chico dejo de venir dos semanas, pero la nota si.
    """

    jugador = models.ForeignKey(
        Jugador, on_delete=models.CASCADE, related_name='notas', verbose_name='Jugador'
    )
    fecha = models.DateField(default=date.today, verbose_name='Fecha')
    tipo = models.IntegerField(choices=TIPOS_NOTA, default=NOTA_GENERAL, verbose_name='De que se trata')
    texto = models.TextField(verbose_name='La nota', help_text='Que paso o que hay que trabajar con el.')
    entrenador = models.ForeignKey(
        Entrenador, blank=True, null=True, on_delete=models.SET_NULL,
        related_name='notas', verbose_name='Quien la escribio'
    )

    class Meta:
        verbose_name = 'Nota'
        verbose_name_plural = 'Notas'
        ordering = ['-fecha', '-id']
        indexes = [models.Index(fields=['jugador', '-fecha'])]

    def __str__(self):
        return '%s - %s' % (self.jugador.nombre_completo(), self.fecha)

    def save(self, *args, **kwargs):
        self.texto = ' '.join((self.texto or '').split())
        super().save(*args, **kwargs)

    def color(self):
        return COLORES_NOTA.get(self.tipo, 'secondary')

    def icono(self):
        return ICONOS_NOTA.get(self.tipo, 'bi-chat-left-text')

    def firma(self):
        """Quien la escribio, para que no queden notas anonimas."""
        if self.entrenador:
            return self.entrenador.nombre_completo()
        return 'ADMINISTRACION'


# ============================================================================
# QUIEN ESTA A CARGO DE CADA GRUPO
# ============================================================================
def quien_dirige(categoria):
    """El profe a cargo de ese grupo.

    Es a proposito lo mas simple que se puede: un grupo, un encargado. Si un
    dia lo cubre otro, eso se conversa; el sistema no se mete.
    """
    return categoria.encargado


# ============================================================================
# PESO Y ESTATURA (crecimiento, no rendimiento)
# ============================================================================
class ControlFisico(ModeloBase):
    """Cuanto pesa y cuanto mide el jugador en una fecha.

    Va aparte de las mediciones de las pruebas a proposito: el peso y la
    estatura no son una marca que se mejora, son un ninio creciendo. No entran
    al radar ni se comparan con el grupo.
    """

    jugador = models.ForeignKey(
        Jugador, on_delete=models.CASCADE, related_name='controles', verbose_name='Jugador'
    )
    fecha = models.DateField(default=date.today, verbose_name='Fecha del control')
    peso = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, verbose_name='Peso (kg)'
    )
    estatura = models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name='Estatura (cm)'
    )
    observacion = models.CharField(max_length=200, blank=True, verbose_name='Observacion')

    class Meta:
        verbose_name = 'Control fisico'
        verbose_name_plural = 'Controles fisicos'
        ordering = ['-fecha']
        constraints = [
            models.UniqueConstraint(fields=['jugador', 'fecha'], name='control_unico_por_dia')
        ]

    def __str__(self):
        return '%s - %s' % (self.jugador.nombre_completo(), self.fecha)

    def save(self, *args, **kwargs):
        self.observacion = texto_limpio(self.observacion)
        super().save(*args, **kwargs)

    def imc(self):
        """Indice de masa corporal. Solo tiene sentido con los dos datos."""
        if not self.peso or not self.estatura:
            return None
        metros = Decimal(self.estatura) / Decimal('100')
        return (self.peso / (metros * metros)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)

    def texto_peso(self):
        return '%s kg' % normalizar_decimal(self.peso) if self.peso else '-'

    def texto_estatura(self):
        return '%s cm' % self.estatura if self.estatura else '-'

    def diferencia_de_peso(self, otro):
        if not (self.peso and otro and otro.peso):
            return None
        return self.peso - otro.peso

    def diferencia_de_estatura(self, otro):
        if not (self.estatura and otro and otro.estatura):
            return None
        return self.estatura - otro.estatura

    def anterior(self):
        return ControlFisico.objects.filter(
            jugador=self.jugador, fecha__lt=self.fecha).order_by('-fecha').first()
