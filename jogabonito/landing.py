# coding=utf-8
"""Pagina publica de la academia y formulario de inscripcion (FASE 5).

Es la unica parte del sistema que ve gente sin cuenta, asi que aqui no se
muestra ningun dato personal: solo los grupos, los horarios y el contacto.
"""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from jogabonito.commonviews import ip_cliente
from jogabonito.forms import SolicitudInscripcionForm
from jogabonito.models import JUGADOR_ACTIVO, Categoria, Entrenador, Jugador, SolicitudInscripcion

# Fortalezas de la academia. Se editan aqui cuando cambien.
FORTALEZAS = [
    {
        'icono': 'fa-solid fa-graduation-cap',
        'titulo': 'Entrenador formado en ATFA',
        'texto': 'La academia la dirige un licenciado y entrenador formador graduado en la ATFA de '
                 'Argentina: metodologia de formacion, no improvisacion.',
    },
    {
        'icono': 'fa-solid fa-futbol',
        'titulo': 'Tecnica, disciplina y pasion',
        'texto': 'Trabajamos el control, el pase, la gambeta y la toma de decisiones, con el orden '
                 'y la constancia que exige el futbol de primer nivel.',
    },
    {
        'icono': 'fa-solid fa-people-group',
        'titulo': 'Grupos por horario',
        'texto': 'Cada grupo entrena con pocos jugadores, para que el entrenador pueda corregir uno '
                 'por uno y nadie se quede mirando.',
    },
    {
        'icono': 'fa-solid fa-clock',
        'titulo': 'Horarios que se acomodan',
        'texto': 'Manana, tarde y noche. El representante elige el grupo que le sirve a la familia '
                 'sin pelear con el horario del colegio.',
    },
    {
        'icono': 'fa-solid fa-clipboard-check',
        'titulo': 'Control de asistencia real',
        'texto': 'Registramos la asistencia de cada entrenamiento, para que el representante sepa '
                 'cuando su hijo asistio, falto o llego tarde.',
    },
    {
        'icono': 'fa-solid fa-heart',
        'titulo': 'Formacion integral',
        'texto': 'Ninos, ninas y jovenes. Puntualidad, respeto al companiero y al rival, y trabajo '
                 'en equipo: el futbol es la excusa para formar personas.',
    },
]

# Credenciales verificables del director (salen de su perfil publico).
CREDENCIALES_DIRECTOR = [
    {'icono': 'fa-solid fa-user-graduate', 'texto': 'Licenciado'},
    {'icono': 'fa-solid fa-futbol', 'texto': 'Entrenador formador'},
    {'icono': 'fa-solid fa-certificate', 'texto': 'Graduado en ATFA (Argentina)'},
]

# Los cuatro valores de la academia, tal como estan en su arte oficial.
VALORES = [
    {'icono': 'fa-solid fa-futbol', 'texto': 'Disciplina'},
    {'icono': 'fa-solid fa-handshake', 'texto': 'Respeto'},
    {'icono': 'fa-solid fa-people-group', 'texto': 'Trabajo en equipo'},
    {'icono': 'fa-solid fa-star', 'texto': 'Pasion'},
]


def datos_publicos():
    categorias = Categoria.objects.filter(activo=True).order_by('hora_inicio', 'nombre')
    entrenadores = Entrenador.objects.filter(activo=True).order_by('apellidos', 'nombres')
    return {
        'fortalezas': FORTALEZAS,
        'credenciales': CREDENCIALES_DIRECTOR,
        'valores': VALORES,
        'categorias': categorias,
        # El cuerpo tecnico sale de la base: solo nombre y foto, nada de telefonos.
        'entrenadores': entrenadores,
        'total_jugadores': Jugador.objects.filter(estado=JUGADOR_ACTIVO).count(),
        'total_entrenadores': entrenadores.count(),
        'total_categorias': categorias.count(),
    }


def supera_el_tope(ip):
    """Freno simple contra el spam del formulario publico."""
    if not ip:
        return False
    desde = timezone.now() - timedelta(hours=1)
    recientes = SolicitudInscripcion.objects.filter(origen_ip=ip, fecha_creacion__gte=desde).count()
    return recientes >= settings.SOLICITUDES_MAXIMAS_POR_HORA


@require_http_methods(['GET', 'HEAD', 'POST'])
@transaction.atomic()
def home(request):
    data = datos_publicos()

    if request.method == 'POST':
        form = SolicitudInscripcionForm(request.POST)
        ip = ip_cliente(request)

        if supera_el_tope(ip):
            data['form'] = form
            data['error'] = ('Ya recibimos varias solicitudes desde este dispositivo. '
                             'Escribenos por WhatsApp y te atendemos enseguida.')
            return render(request, 'landing/index.html', data, status=429)

        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.origen_ip = ip or None
            solicitud.save()
            data['form'] = SolicitudInscripcionForm()
            data['enviado'] = True
            data['nombre_enviado'] = solicitud.nombre
            return render(request, 'landing/index.html', data)

        data['form'] = form
        data['error'] = 'Revisa los datos del formulario, por favor.'
        return render(request, 'landing/index.html', data, status=400)

    data['form'] = SolicitudInscripcionForm()
    return render(request, 'landing/index.html', data)
