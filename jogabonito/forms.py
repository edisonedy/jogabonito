# coding=utf-8
"""Formularios de la FASE 1.

Toda validacion vive aqui o en el modelo: las vistas nunca confian en el POST.
"""
from datetime import date

from django import forms
from django.contrib.auth.models import User

from jogabonito.funciones import validar_cedula, validar_imagen
from jogabonito.models import (
    DIAS_SEMANA, MEDIDA_NUMERO, Asistencia, Categoria, Entrenador, Evaluacion, Indicador, Jugador,
    PerfilUsuario, Posicion, Representante, SolicitudInscripcion,
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

    def _validar_foto(self, campo):
        imagen = self.cleaned_data.get(campo)
        if imagen and hasattr(imagen, 'size'):
            valido, mensaje = validar_imagen(imagen)
            if not valido:
                raise forms.ValidationError(mensaje)
        return imagen


class EntrenadorForm(BaseForm):
    class Meta:
        model = Entrenador
        fields = ['nombres', 'apellidos', 'cedula', 'telefono', 'email', 'fotografia', 'activo']

    def clean_fotografia(self):
        return self._validar_foto('fotografia')


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
                  'valor_mensual', 'activo']
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
        return limpios


class RepresentanteForm(BaseForm):
    class Meta:
        model = Representante
        fields = ['nombres', 'apellidos', 'cedula', 'telefono', 'whatsapp', 'email',
                  'parentesco', 'direccion', 'activo']


class JugadorForm(BaseForm):
    class Meta:
        model = Jugador
        fields = ['nombres', 'apellidos', 'cedula', 'fecha_nacimiento', 'fotografia', 'telefono',
                  'direccion', 'fecha_ingreso', 'categoria', 'representante', 'valor_mensual',
                  'posicion', 'pie_habil', 'dorsal', 'observacion', 'estado']
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
        return self._validar_foto('fotografia')

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
    class Meta:
        model = Posicion
        fields = ['nombre', 'abreviatura', 'orden', 'activo']


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
        fields = ['categoria', 'fecha', 'titulo', 'indicadores', 'observacion']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'indicadores': forms.CheckboxSelectMultiple(attrs={'class': CLASE_GRUPO_CHECK}),
        }

    def __init__(self, *args, **kwargs):
        self.categorias_permitidas = kwargs.pop('categorias', None)
        super().__init__(*args, **kwargs)
        self.fields['fecha'].input_formats = ['%Y-%m-%d', '%d-%m-%Y']
        self.fields['indicadores'].queryset = Indicador.objects.filter(activo=True).order_by(
            'area', 'orden', 'nombre')
        if self.categorias_permitidas is not None:
            self.fields['categoria'].queryset = self.categorias_permitidas
        else:
            self.fields['categoria'].queryset = Categoria.objects.filter(activo=True)

    def clean_fecha(self):
        fecha = self.cleaned_data.get('fecha')
        if fecha and fecha > date.today():
            raise forms.ValidationError('No se puede registrar una prueba de una fecha futura.')
        return fecha

    def clean_indicadores(self):
        indicadores = self.cleaned_data.get('indicadores')
        if not indicadores:
            raise forms.ValidationError('Elige al menos un indicador para medir.')
        return indicadores


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
