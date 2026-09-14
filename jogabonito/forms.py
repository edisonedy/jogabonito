# coding=utf-8
"""Formularios de la FASE 1.

Toda validacion vive aqui o en el modelo: las vistas nunca confian en el POST.
"""
from datetime import date

from django import forms
from django.contrib.auth.models import User

from jogabonito.funciones import validar_cedula, validar_imagen
from jogabonito.models import (
    DIAS_SEMANA, JUGADOR_ACTIVO, MEDIDA_NUMERO, MENSUALIDAD_PAGADO, PARENTESCOS, Asistencia, Categoria,
    ControlFisico, Division, Entrenador, Evaluacion, Nota,
    Indicador, Jugador, Mensualidad, PerfilUsuario, Posicion, Representante, SolicitudInscripcion,
    TipoEvaluacion,
)

CLASE_INPUT = 'form-control form-control-sm'
CLASE_SELECT = 'form-select form-select-sm'
CLASE_CHECK = 'form-check-input'
CLASE_GRUPO_CHECK = 'check-group'


class BaseForm(forms.ModelForm):
    """Aplica las clases de Bootstrap a todos los widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
                # El atributo cae tanto en el <div> contenedor como en cada <input>,
                # por eso la clase se estiliza por separado en joga.css.
                widget.attrs.setdefault('class', CLASE_GRUPO_CHECK)
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', CLASE_CHECK)
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', CLASE_SELECT)
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault('class', CLASE_INPUT)
                widget.attrs.setdefault('rows', 3)
            else:
                widget.attrs.setdefault('class', CLASE_INPUT)

    def clean_cedula(self):
        cedula = (self.cleaned_data.get('cedula') or '').strip()
        if cedula and not validar_cedula(cedula):
            raise forms.ValidationError('La cedula ingresada no es valida.')
        return cedula

    def validar_foto(self, campo):
        imagen = self.cleaned_data.get(campo)
        if imagen and hasattr(imagen, 'size'):
            valido, mensaje = validar_imagen(imagen)
            if not valido:
                raise forms.ValidationError(mensaje)
        return imagen


class EntrenadorForm(BaseForm):
    class Meta:
        model = Entrenador
        fields = ['nombre1', 'nombre2', 'apellido1', 'apellido2', 'cedula', 'telefono',
                  'email', 'fotografia', 'activo']

    def clean_fotografia(self):
        return self.validar_foto('fotografia')


class CategoriaForm(BaseForm):
    dias = forms.MultipleChoiceField(
        choices=DIAS_SEMANA,
        required=False,
        label='Dias de entrenamiento',
        widget=forms.CheckboxSelectMultiple(attrs={'class': CLASE_GRUPO_CHECK})
    )

    class Meta:
        model = Categoria
        fields = ['nombre', 'descripcion', 'entrenadores', 'dias', 'hora_inicio', 'hora_fin',
                  'valor_mensual', 'edad_minima', 'edad_maxima', 'activo']
        widgets = {
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'hora_fin': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'entrenadores': forms.SelectMultiple(attrs={'size': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['entrenadores'].queryset = Entrenador.objects.filter(activo=True)
        if self.instance and self.instance.pk:
            self.initial['dias'] = self.instance.dias_lista()

    def clean_dias(self):
        return ','.join(sorted(self.cleaned_data.get('dias') or []))

    def clean_valor_mensual(self):
        valor = self.cleaned_data.get('valor_mensual')
        if valor is not None and valor < 0:
            raise forms.ValidationError('El valor mensual no puede ser negativo.')
        return valor

    def clean(self):
        limpios = super().clean()
        inicio, fin = limpios.get('hora_inicio'), limpios.get('hora_fin')
        if inicio and fin and fin <= inicio:
            self.add_error('hora_fin', 'La hora de fin debe ser posterior a la hora de inicio.')

        edad_min, edad_max = limpios.get('edad_minima'), limpios.get('edad_maxima')
        if edad_min is not None and edad_max is not None and edad_max < edad_min:
            self.add_error('edad_maxima', 'La edad maxima no puede ser menor que la minima.')
        return limpios


class RepresentanteForm(BaseForm):
    class Meta:
        model = Representante
        fields = ['nombre1', 'nombre2', 'apellido1', 'apellido2', 'cedula', 'telefono', 'whatsapp', 'email',
                  'parentesco', 'direccion', 'activo']


class DivisionForm(BaseForm):
    """Categoria por edad. Cada jugador cae en una segun los anios que tiene."""

    class Meta:
        model = Division
        fields = ['nombre', 'edad_minima', 'edad_maxima', 'orden', 'activo']

    def clean(self):
        limpios = super().clean()
        minima = limpios.get('edad_minima')
        maxima = limpios.get('edad_maxima')

        if minima is not None and maxima is not None and maxima < minima:
            self.add_error('edad_maxima', 'La edad maxima no puede ser menor que la minima.')
            return limpios

        if minima is None or maxima is None:
            return limpios

        # Dos divisiones que se pisan dejarian al ninio en dos categorias.
        otras = Division.objects.filter(activo=True)
        if self.instance and self.instance.pk:
            otras = otras.exclude(pk=self.instance.pk)

        for otra in otras:
            if minima <= otra.edad_maxima and otra.edad_minima <= maxima:
                self.add_error('edad_minima', 'Ese rango se cruza con %s (%s).' % (
                    otra.nombre, otra.rango_texto()))
                break

        return limpios


def exigir_nombre_y_apellido(form):
    """El primer nombre y el primer apellido no pueden faltar."""
    for campo, aviso in (('nombre1', 'Escribe el primer nombre.'),
                         ('apellido1', 'Escribe el primer apellido.')):
        if campo in form.fields:
            form.fields[campo].required = True
            form.fields[campo].error_messages['required'] = aviso


class JugadorForm(BaseForm):
    class Meta:
        model = Jugador
        fields = ['nombre1', 'nombre2', 'apellido1', 'apellido2', 'apodo', 'cedula',
                  'fecha_nacimiento', 'fotografia', 'telefono',
                  'direccion', 'fecha_ingreso', 'categoria', 'representante',
                  'posicion', 'pie_habil', 'dorsal', 'cuidados', 'observacion', 'estado']
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_ingreso': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].queryset = Categoria.objects.filter(activo=True)
        self.fields['representante'].queryset = Representante.objects.filter(activo=True)
        self.fields['representante'].required = False
        self.fields['posicion'].queryset = Posicion.objects.filter(activo=True)
        self.fields['posicion'].required = False
        self.fields['posicion'].empty_label = 'Sin definir'
        self.fields['pie_habil'].required = False
        self.fields['fecha_nacimiento'].input_formats = ['%Y-%m-%d', '%d-%m-%Y']
        self.fields['fecha_ingreso'].input_formats = ['%Y-%m-%d', '%d-%m-%Y']

    def clean_fotografia(self):
        return self.validar_foto('fotografia')

    def clean(self):
        limpios = super().clean()
        nacimiento, ingreso = limpios.get('fecha_nacimiento'), limpios.get('fecha_ingreso')
        if nacimiento and ingreso and ingreso < nacimiento:
            self.add_error('fecha_ingreso', 'La fecha de ingreso no puede ser anterior al nacimiento.')
        return limpios


class UsuarioEntrenadorForm(forms.Form):
    """Crea o actualiza el acceso al sistema de un entrenador."""

    username = forms.CharField(max_length=150, label='Usuario',
                               widget=forms.TextInput(attrs={'class': CLASE_INPUT}))
    password = forms.CharField(max_length=128, label='Clave', required=False,
                               widget=forms.PasswordInput(attrs={'class': CLASE_INPUT}),
                               help_text='Dejar vacio para no cambiar la clave actual.')

    def __init__(self, *args, **kwargs):
        self.entrenador = kwargs.pop('entrenador', None)
        super().__init__(*args, **kwargs)
        if self.entrenador and self.entrenador.usuario:
            self.fields['username'].initial = self.entrenador.usuario.username

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip().lower()
        existentes = User.objects.filter(username=username)
        if self.entrenador and self.entrenador.usuario:
            existentes = existentes.exclude(pk=self.entrenador.usuario.pk)
        if existentes.exists():
            raise forms.ValidationError('Ese nombre de usuario ya esta ocupado.')
        return username

    def clean_password(self):
        clave = self.cleaned_data.get('password') or ''
        sin_usuario = not (self.entrenador and self.entrenador.usuario)
        if sin_usuario and len(clave) < 8:
            raise forms.ValidationError('La clave debe tener al menos 8 caracteres.')
        if clave and len(clave) < 8:
            raise forms.ValidationError('La clave debe tener al menos 8 caracteres.')
        return clave


class CambiarClaveForm(forms.Form):
    clave_actual = forms.CharField(widget=forms.PasswordInput(attrs={'class': CLASE_INPUT}), label='Clave actual')
    clave_nueva = forms.CharField(widget=forms.PasswordInput(attrs={'class': CLASE_INPUT}), label='Clave nueva')
    clave_repetir = forms.CharField(widget=forms.PasswordInput(attrs={'class': CLASE_INPUT}), label='Repetir clave')

    def __init__(self, *args, **kwargs):
        self.usuario = kwargs.pop('usuario', None)
        super().__init__(*args, **kwargs)

    def clean_clave_actual(self):
        clave = self.cleaned_data.get('clave_actual') or ''
        if self.usuario and not self.usuario.check_password(clave):
            raise forms.ValidationError('La clave actual no es correcta.')
        return clave

    def clean(self):
        limpios = super().clean()
        nueva, repetir = limpios.get('clave_nueva'), limpios.get('clave_repetir')
        if nueva and len(nueva) < 8:
            self.add_error('clave_nueva', 'La clave debe tener al menos 8 caracteres.')
        elif nueva and nueva != repetir:
            self.add_error('clave_repetir', 'Las claves no coinciden.')
        return limpios


class AsistenciaDetalleForm(BaseForm):
    """Estado + observacion de un jugador en una fecha (modal de la FASE 2)."""

    class Meta:
        model = Asistencia
        fields = ['estado', 'observacion']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['observacion'].required = False


class PosicionForm(BaseForm):
    """Puesto y cuanto pesa cada area para jugar ahi."""

    class Meta:
        model = Posicion
        fields = ['nombre', 'abreviatura', 'peso_tecnica', 'peso_fisica', 'peso_tactica',
                  'peso_actitud', 'orden', 'activo']

    def clean(self):
        limpios = super().clean()
        pesos = [limpios.get('peso_tecnica'), limpios.get('peso_fisica'),
                 limpios.get('peso_tactica'), limpios.get('peso_actitud')]
        for peso in pesos:
            if peso is not None and peso > 3:
                self.add_error(None, 'Los pesos van de 0 a 3.')
                break
        if not any(p for p in pesos if p):
            self.add_error(None, 'Al menos un area debe pesar mas que cero.')
        return limpios


class IndicadorForm(BaseForm):
    """Define QUE se le va a medir al jugador."""

    class Meta:
        model = Indicador
        fields = ['nombre', 'descripcion', 'area', 'tipo_medida', 'unidad', 'mejor_es',
                  'valor_minimo', 'valor_maximo', 'orden', 'activo']

    def clean(self):
        limpios = super().clean()
        minimo, maximo = limpios.get('valor_minimo'), limpios.get('valor_maximo')
        if minimo is not None and maximo is not None and maximo <= minimo:
            self.add_error('valor_maximo', 'El valor maximo debe ser mayor que el minimo.')
        if limpios.get('tipo_medida') == MEDIDA_NUMERO and not (limpios.get('unidad') or '').strip():
            self.add_error('unidad', 'Indica la unidad (seg, m, reps, goles...).')
        return limpios


class EvaluacionForm(BaseForm):
    """Una jornada de pruebas: cuando, a que grupo y que se va a medir."""

    class Meta:
        model = Evaluacion
        fields = ['categoria', 'jugador', 'tipo', 'fecha', 'fecha_fin', 'titulo',
                  'indicadores', 'observacion']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'indicadores': forms.CheckboxSelectMultiple(attrs={'class': CLASE_GRUPO_CHECK}),
        }

    def __init__(self, *args, **kwargs):
        self.categorias_permitidas = kwargs.pop('categorias', None)
        super().__init__(*args, **kwargs)
        self.fields['fecha'].input_formats = ['%Y-%m-%d', '%d-%m-%Y']
        self.fields['fecha_fin'].input_formats = ['%Y-%m-%d', '%d-%m-%Y']
        self.fields['fecha_fin'].required = False

        # Casi siempre la prueba es de hoy: las dos fechas vienen puestas.
        if not (self.instance and self.instance.pk):
            self.initial.setdefault('fecha', date.today())
            self.initial.setdefault('fecha_fin', date.today())
        self.fields['indicadores'].queryset = Indicador.objects.filter(activo=True).order_by(
            'area', 'orden', 'nombre')
        self.fields['tipo'].queryset = TipoEvaluacion.objects.filter(activo=True)
        self.fields['tipo'].required = False
        self.fields['tipo'].empty_label = 'Sin clasificar'
        if self.categorias_permitidas is not None:
            self.fields['categoria'].queryset = self.categorias_permitidas
        else:
            self.fields['categoria'].queryset = Categoria.objects.filter(activo=True)

        # Individual: solo jugadores de los grupos que el usuario maneja.
        self.fields['jugador'].required = False
        self.fields['jugador'].empty_label = 'A todo el grupo'
        self.fields['titulo'].required = False
        # Que se mide se elige en la pantalla siguiente, no en el modal.
        self.fields['indicadores'].required = False
        self.fields['titulo'].help_text = (
            'Si es de un solo jugador y lo dejas vacio, se le pone el nombre solo.')
        self.fields['fecha_fin'].help_text = (
            'Solo para la prueba de todo el grupo, cuando se toma en varios dias. '
            'La de un solo jugador es de un dia y ya.')
        self.fields['jugador'].queryset = Jugador.objects.filter(
            estado=JUGADOR_ACTIVO,
            categoria__in=self.fields['categoria'].queryset
        ).select_related('categoria').order_by('apellidos', 'nombres')

    def clean_fecha(self):
        fecha = self.cleaned_data.get('fecha')
        if fecha and fecha > date.today():
            raise forms.ValidationError('No se puede registrar una prueba de una fecha futura.')
        return fecha

    def nombre_sugerido(self, jugador, tipo, fecha):
        """Como se llama una prueba de un solo jugador si no le ponen nombre.

        La primera que se le toma es su prueba inicial: con eso llego. Las
        siguientes llevan la fecha, que es lo unico que las distingue.
        """
        es_la_primera = not jugador.mediciones.exists()
        if es_la_primera or (tipo and tipo.es_inicial):
            return 'PRUEBA INICIAL DE %s' % jugador.nombre_completo()
        return 'PRUEBA DE %s DEL %s' % (jugador.nombre_completo(), fecha.strftime('%d/%m/%Y'))

    def clean(self):
        """La individual es de UN jugador, de UN dia y con nombre propio."""
        limpios = super().clean()
        jugador = limpios.get('jugador')
        categoria = limpios.get('categoria')

        if jugador and categoria and jugador.categoria_id != categoria.id:
            self.add_error('jugador', '%s no entrena en %s. Elige su grupo o deja la '
                                      'prueba para todo el grupo.'
                                      % (jugador.nombre_completo(), categoria.nombre))
            return limpios

        if jugador:
            # Tomarle una prueba a uno es cosa de un dia: no hay rango.
            limpios['fecha_fin'] = None
            if not (limpios.get('titulo') or '').strip() and limpios.get('fecha'):
                limpios['titulo'] = self.nombre_sugerido(
                    jugador, limpios.get('tipo'), limpios['fecha'])

        elif not (limpios.get('titulo') or '').strip():
            self.add_error('titulo', 'Ponle un nombre a la prueba del grupo.')

        return limpios

    def clean_fecha_fin(self):
        """El "hasta" solo tiene sentido si es despues del dia en que arranco."""
        fin = self.cleaned_data.get('fecha_fin')
        inicio = self.cleaned_data.get('fecha')
        if fin and inicio and fin < inicio:
            raise forms.ValidationError('La prueba no puede terminar antes de empezar.')
        if fin and inicio and (fin - inicio).days > 31:
            raise forms.ValidationError('Una prueba que dura mas de un mes ya son dos pruebas.')
        return fin

    # Que se va a medir NO se pide aqui: se elige en la pantalla siguiente,
    # que tiene espacio para la lista completa. Por eso no hay validacion.


class RepresentanteDelJugadorForm(forms.Form):
    """Asigna un representante al jugador: uno que ya existe o uno nuevo.

    Asi no hay que salir a otro modulo para registrar al papa o a la mama.
    """

    existente = forms.ModelChoiceField(
        queryset=Representante.objects.none(), required=False,
        label='Elegir uno que ya esta registrado',
        widget=forms.Select(attrs={'class': CLASE_SELECT})
    )
    nombres = forms.CharField(max_length=100, required=False, label='Nombres',
                              widget=forms.TextInput(attrs={'class': CLASE_INPUT}))
    apellidos = forms.CharField(max_length=100, required=False, label='Apellidos',
                                widget=forms.TextInput(attrs={'class': CLASE_INPUT}))
    telefono = forms.CharField(max_length=20, required=False, label='Telefono',
                               widget=forms.TextInput(attrs={'class': CLASE_INPUT}))
    whatsapp = forms.CharField(max_length=20, required=False, label='WhatsApp',
                               widget=forms.TextInput(attrs={'class': CLASE_INPUT}))
    parentesco = forms.ChoiceField(choices=PARENTESCOS, required=False, label='Parentesco',
                                   widget=forms.Select(attrs={'class': CLASE_SELECT}))

    def __init__(self, *args, **kwargs):
        jugador = kwargs.pop('jugador', None)
        super().__init__(*args, **kwargs)
        self.fields['existente'].queryset = Representante.objects.filter(activo=True)
        self.fields['existente'].empty_label = 'Sin representante / crear uno nuevo'
        if jugador and jugador.representante_id:
            self.fields['existente'].initial = jugador.representante_id

    def quiere_crear(self):
        limpios = getattr(self, 'cleaned_data', {})
        return bool((limpios.get('nombres') or '').strip() or (limpios.get('apellidos') or '').strip())

    def clean(self):
        limpios = super().clean()
        if not self.quiere_crear():
            return limpios

        if not (limpios.get('nombres') or '').strip():
            self.add_error('nombres', 'Escribe los nombres del representante.')
        if not (limpios.get('apellidos') or '').strip():
            self.add_error('apellidos', 'Escribe los apellidos del representante.')
        if not (limpios.get('telefono') or '').strip():
            self.add_error('telefono', 'El telefono es necesario para poder contactarlo.')
        return limpios

    def asignar(self, jugador, request=None):
        """Deja al jugador con el representante elegido (o con el nuevo)."""
        limpios = self.cleaned_data

        if self.quiere_crear():
            representante = Representante(
                nombres=limpios['nombres'],
                apellidos=limpios['apellidos'],
                telefono=limpios['telefono'],
                whatsapp=limpios.get('whatsapp') or '',
                parentesco=int(limpios.get('parentesco') or 1),
            )
            representante.save(request)
        else:
            representante = limpios.get('existente')

        jugador.representante = representante
        jugador.save(request)
        return representante


class PrecioJugadorForm(BaseForm):
    """Como se le cobra: si se le sigue cobrando y con que descuento.

    El precio base no se toca aqui: ese sale del grupo.
    """

    class Meta:
        model = Jugador
        fields = ['cobro_activo', 'descuento', 'motivo_descuento']

    def clean_descuento(self):
        descuento = self.cleaned_data.get('descuento') or 0
        if descuento < 0 or descuento > 100:
            raise forms.ValidationError('El descuento va de 0 a 100 por ciento.')
        return descuento

    def clean(self):
        limpios = super().clean()
        if limpios.get('descuento') and not (limpios.get('motivo_descuento') or '').strip():
            self.add_error('motivo_descuento', 'Escribe por que se le hace el descuento.')
        return limpios


def dias_entre(inicio, fin):
    """Cuantos dias cubre un periodo, contando el primero y el ultimo."""
    return (fin - inicio).days + 1


class CamposDeFecha:
    """Lo que comparten los dos formularios que manejan fechas del periodo."""

    FECHAS = ('periodo_inicio', 'periodo_fin', 'fecha_vencimiento', 'fecha_pago')

    def preparar_fechas(self):
        for nombre in self.FECHAS:
            if nombre in self.fields:
                self.fields[nombre].input_formats = ['%Y-%m-%d', '%d-%m-%Y']

    def revisar_periodo(self, limpios):
        """El periodo tiene que ir de menos a mas y durar como un mes."""
        inicio = limpios.get('periodo_inicio')
        fin = limpios.get('periodo_fin')
        if not (inicio and fin):
            return limpios
        if fin < inicio:
            self.add_error('periodo_fin', 'El periodo termina antes de empezar.')
        elif dias_entre(inicio, fin) > 62:
            self.add_error('periodo_fin', 'Ese periodo dura mas de dos meses. Revisa las fechas.')
        return limpios


class MensualidadForm(BaseForm, CamposDeFecha):
    """Cobro de una mensualidad. Aqui tambien se corrigen las fechas."""

    class Meta:
        model = Mensualidad
        fields = ['periodo_inicio', 'periodo_fin', 'fecha_vencimiento', 'valor_completo',
                  'estado', 'dias_ausente', 'motivo_ajuste', 'fecha_pago', 'forma_pago',
                  'comprobante', 'observacion']
        widgets = {
            'periodo_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'periodo_fin': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_pago': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.preparar_fechas()

        # Casi siempre se cobra el mismo dia que se registra: la fecha viene
        # puesta en hoy para no tener que escribirla.
        if not self.initial.get('fecha_pago') and not (self.instance and self.instance.fecha_pago):
            self.initial['fecha_pago'] = date.today()

        self.fields['fecha_vencimiento'].required = False
        self.fields['fecha_vencimiento'].help_text = (
            'Si la dejas vacia se usa el dia en que arranca el periodo.')

        # Lo normal es que pague el valor de su grupo, pero un mes puede salir
        # distinto (le subieron el precio, un acuerdo suelto, una rebaja).
        self.fields['valor_completo'].label = 'Valor de este mes'
        self.fields['valor_completo'].help_text = (
            'Lo que cuesta el mes completo. Si avisa que no viene unos dias, '
            'sobre este valor se hace la rebaja.')
        self.fields['valor_completo'].localize = False
        self.fields['valor_completo'].widget.is_localized = False
        self.fields['valor_completo'].required = False
        self.fields['fecha_pago'].required = False
        self.fields['forma_pago'].required = False
        self.fields['comprobante'].required = False
        self.fields['motivo_ajuste'].required = False
        self.fields['dias_ausente'].required = False

    def clean_fecha_pago(self):
        fecha = self.cleaned_data.get('fecha_pago')
        if fecha and fecha > date.today():
            raise forms.ValidationError('La fecha de pago no puede ser futura.')
        return fecha

    def clean_valor_completo(self):
        valor = self.cleaned_data.get('valor_completo')
        if valor is not None and valor < 0:
            raise forms.ValidationError('El valor no puede ser negativo.')
        return valor

    def clean(self):
        limpios = super().clean()
        self.conservar_fechas(limpios)
    def conservar_fechas(self, limpios):
        """Un periodo en blanco no borra el que ya tenia la mensualidad.

        El vencimiento no entra aqui: si lo dejan vacio se acomoda al dia en
        que arranca el periodo, que puede ser uno nuevo.
        """
        if not (self.instance and self.instance.pk):
            return limpios
        for nombre in ('periodo_inicio', 'periodo_fin'):
            if not limpios.get(nombre):
                limpios[nombre] = getattr(self.instance, nombre)
        return limpios

    def clean(self):
        limpios = super().clean()
        self.conservar_fechas(limpios)
        self.revisar_periodo(limpios)

        # Vacio = no se toca lo que ya costaba ese mes.
        if limpios.get('valor_completo') is None and self.instance and self.instance.pk:
            limpios['valor_completo'] = self.instance.valor_completo

        if not limpios.get('fecha_vencimiento'):
            # se acomoda al periodo; si tampoco hay periodo, queda la que tenia
            limpios['fecha_vencimiento'] = (limpios.get('periodo_inicio')
                                            or getattr(self.instance, 'fecha_vencimiento', None))
        if not limpios.get('fecha_vencimiento'):
            self.add_error('fecha_vencimiento', 'Indica cuando se vence.')

        inicio = limpios.get('periodo_inicio')
        fin = limpios.get('periodo_fin')
        dias = dias_entre(inicio, fin) if inicio and fin and fin >= inicio else 31
        if (limpios.get('dias_ausente') or 0) > dias:
            self.add_error('dias_ausente', 'El periodo tiene %s dias.' % dias)

        if limpios.get('estado') == MENSUALIDAD_PAGADO and not limpios.get('forma_pago'):
            self.add_error('forma_pago', 'Indica como pago.')
        if limpios.get('dias_ausente') and not (limpios.get('motivo_ajuste') or '').strip():
            self.add_error('motivo_ajuste', 'Escribe por que no va a venir esos dias.')
        return limpios


class CobroRapidoForm(BaseForm, CamposDeFecha):
    """Solo para cobrar: como pago y cuando. Nada mas.

    Es el caso de todos los dias: el representante llega, paga lo que dice la
    pantalla y listo. Si hay que cambiar fechas o el valor, para eso esta el
    boton de editar.
    """

    class Meta:
        model = Mensualidad
        fields = ['forma_pago', 'fecha_pago', 'comprobante']
        widgets = {
            'fecha_pago': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.preparar_fechas()
        self.fields['forma_pago'].required = True
        self.fields['forma_pago'].empty_label = 'Como pago...'
        self.fields['comprobante'].required = False
        self.fields['fecha_pago'].required = False
        self.fields['fecha_pago'].help_text = 'Si lo dejas vacio, se cobra con la fecha de hoy.'

        if not self.initial.get('fecha_pago') and not (self.instance and self.instance.fecha_pago):
            self.initial['fecha_pago'] = date.today()

    def clean_fecha_pago(self):
        fecha = self.cleaned_data.get('fecha_pago')
        if fecha and fecha > date.today():
            raise forms.ValidationError('La fecha de pago no puede ser futura.')
        return fecha

    def clean(self):
        limpios = super().clean()
        if not limpios.get('fecha_pago'):
            limpios['fecha_pago'] = date.today()
        return limpios


class MensualidadNuevaForm(BaseForm, CamposDeFecha):
    """Cobrarle el mes a UN solo jugador, con las fechas que uno quiera.

    Sirve para el que entra a mitad de mes o para el que se cobra aparte,
    sin tener que generarle el mes a toda la academia.
    """

    class Meta:
        model = Mensualidad
        fields = ['jugador', 'mes', 'anio', 'periodo_inicio', 'periodo_fin', 'valor',
                  'observacion']
        widgets = {
            'periodo_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'periodo_fin': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.preparar_fechas()
        self.fields['jugador'].queryset = Jugador.objects.filter(
            estado=JUGADOR_ACTIVO).select_related('categoria').order_by('apellidos', 'nombres')
        self.fields['jugador'].empty_label = 'Elige al jugador...'
        self.fields['periodo_inicio'].help_text = (
            'Si no pones nada, arranca el dia del mes en que el jugador ingreso.')
        self.fields['valor'].required = False
        self.fields['valor'].localize = False
        self.fields['valor'].widget.is_localized = False
        self.fields['valor'].help_text = (
            'Vacio = el valor de su grupo, ya con su descuento.')

    def clean_valor(self):
        valor = self.cleaned_data.get('valor')
        if valor is not None and valor < 0:
            raise forms.ValidationError('El valor no puede ser negativo.')
        return valor

    def clean(self):
        limpios = super().clean()
        self.revisar_periodo(limpios)

        jugador = limpios.get('jugador')
        mes = limpios.get('mes')
        anio = limpios.get('anio')
        if not (jugador and mes and anio):
            return limpios

        inicio, fin = jugador.periodo_de_cobro(mes, anio)
        limpios['periodo_inicio'] = limpios.get('periodo_inicio') or inicio
        limpios['periodo_fin'] = limpios.get('periodo_fin') or fin

        if Mensualidad.objects.filter(
            jugador=jugador, periodo_inicio=limpios['periodo_inicio']
        ).exists():
            self.add_error('mes', '%s ya tiene la mensualidad que arranca el %s.' % (
                jugador.nombre_completo(), limpios['periodo_inicio'].strftime('%d/%m/%Y')))
            return limpios

        if limpios.get('valor') is None:
            limpios['valor'] = jugador.valor_mensual_vigente()
        return limpios


class ControlFisicoForm(BaseForm):
    """Peso y estatura de un dia. Va aparte de las pruebas a proposito."""

    class Meta:
        model = ControlFisico
        fields = ['fecha', 'peso', 'estatura', 'observacion']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        self.jugador = kwargs.pop('jugador', None)
        super().__init__(*args, **kwargs)
        self.fields['fecha'].input_formats = ['%Y-%m-%d', '%d-%m-%Y']
        self.fields['peso'].required = False
        self.fields['peso'].localize = False
        self.fields['peso'].widget.is_localized = False
        self.fields['estatura'].required = False

    def clean_fecha(self):
        fecha = self.cleaned_data.get('fecha')
        if fecha and fecha > date.today():
            raise forms.ValidationError('No se puede registrar un control de una fecha futura.')
        return fecha

    def clean_peso(self):
        peso = self.cleaned_data.get('peso')
        if peso is not None and not (10 <= peso <= 200):
            raise forms.ValidationError('El peso deberia ir entre 10 y 200 kg. Revisa el numero.')
        return peso

    def clean_estatura(self):
        estatura = self.cleaned_data.get('estatura')
        if estatura is not None and not (80 <= estatura <= 230):
            raise forms.ValidationError('La estatura va en centimetros, entre 80 y 230.')
        return estatura

    def clean(self):
        limpios = super().clean()
        if not limpios.get('peso') and not limpios.get('estatura'):
            raise forms.ValidationError('Pon al menos el peso o la estatura.')

        jugador = self.jugador or getattr(self.instance, 'jugador', None)
        fecha = limpios.get('fecha')
        if jugador and fecha:
            repetido = ControlFisico.objects.filter(jugador=jugador, fecha=fecha)
            if self.instance and self.instance.pk:
                repetido = repetido.exclude(pk=self.instance.pk)
            if repetido.exists():
                self.add_error('fecha', 'Ya hay un control de ese dia. Editalo en vez de repetirlo.')
        return limpios


class NotaForm(BaseForm):
    """La nota que el profe escribe sobre un ninio."""

    class Meta:
        model = Nota
        fields = ['fecha', 'tipo', 'texto']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'texto': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Ej: se le nota mas seguro con el balon, pero le cuesta pedir la pelota.'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha'].input_formats = ['%Y-%m-%d', '%d-%m-%Y']

    def clean_fecha(self):
        fecha = self.cleaned_data.get('fecha')
        if fecha and fecha > date.today():
            raise forms.ValidationError('No se puede anotar algo que todavia no pasa.')
        return fecha

    def clean_texto(self):
        texto = ' '.join((self.cleaned_data.get('texto') or '').split())
        if len(texto) < 5:
            raise forms.ValidationError('Escribe un poco mas para que se entienda.')
        return texto


class TipoEvaluacionForm(BaseForm):
    class Meta:
        model = TipoEvaluacion
        fields = ['nombre', 'descripcion', 'color', 'es_inicial', 'orden', 'activo']


class SolicitudInscripcionForm(forms.ModelForm):
    """Formulario publico de la landing. Nadie autenticado lo llena."""

    # Campo trampa: los robots lo llenan, las personas no lo ven.
    apellido_confirmacion = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = SolicitudInscripcion
        fields = ['nombre', 'telefono', 'edad', 'categoria', 'mensaje']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre del nino o del interesado'}),
            'telefono': forms.TextInput(attrs={'placeholder': '09XXXXXXXX', 'inputmode': 'tel'}),
            'edad': forms.NumberInput(attrs={'min': 3, 'max': 60, 'inputmode': 'numeric'}),
            'mensaje': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Cuentanos algo mas (opcional)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].queryset = Categoria.objects.filter(activo=True).order_by('hora_inicio')
        self.fields['categoria'].required = False
        self.fields['categoria'].empty_label = 'Cualquier horario'
        self.fields['mensaje'].required = False
        for nombre, campo in self.fields.items():
            if nombre == 'apellido_confirmacion':
                continue
            if isinstance(campo.widget, forms.Select):
                campo.widget.attrs.setdefault('class', 'form-select')
            else:
                campo.widget.attrs.setdefault('class', 'form-control')

    def clean_apellido_confirmacion(self):
        if (self.cleaned_data.get('apellido_confirmacion') or '').strip():
            raise forms.ValidationError('Solicitud no valida.')
        return ''

    def clean_nombre(self):
        nombre = ' '.join((self.cleaned_data.get('nombre') or '').split())
        if len(nombre) < 3:
            raise forms.ValidationError('Escribe el nombre completo.')
        return nombre

    def clean_edad(self):
        edad = self.cleaned_data.get('edad')
        if edad is None or edad < 3 or edad > 60:
            raise forms.ValidationError('Ingresa una edad entre 3 y 60 anios.')
        return edad


class PerfilUsuarioForm(BaseForm):
    class Meta:
        model = PerfilUsuario
        fields = ['rol', 'telefono', 'activo']
