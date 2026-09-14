# coding=utf-8
"""Modulo: tablero con el pulso de la academia.

Todo lo que sale aqui respeta el alcance del usuario: el administrador ve la
academia completa y el entrenador solo sus categorias.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render

from jogabonito.acceso import categorias_permitidas, jugadores_permitidos
from jogabonito.adm_turno import grupos_a_cargo_de, grupos_de_hoy
from jogabonito.commonviews import adduserdata, perfil_de
from jogabonito.decorators import URL_LOGIN, last_access, secure_module
from jogabonito.funciones import url_back

from jogabonito.models import (
    ASISTENCIA_ATRASO, ASISTENCIA_FALTA, ASISTENCIA_JUSTIFICADO, ASISTENCIA_PRESENTE,
    JUGADOR_ACTIVO, MENSUALIDAD_PAGADO, MENSUALIDAD_PENDIENTE, SOLICITUD_NUEVA, Asistencia,
    Evaluacion, Mensualidad, SolicitudInscripcion,
)

MODULO = 'dashboard'
DIAS_VENTANA = 30
ASISTENCIA_BAJA = 70          # % por debajo del cual el jugador entra en alerta
DIAS_CUMPLEANIOS = 30


def asistencia_del_dia(categorias, dia):
    registros = Asistencia.objects.filter(categoria__in=categorias, fecha=dia)
    conteo = registros.values('estado').annotate(total=Count('id'))
    por_estado = {fila['estado']: fila['total'] for fila in conteo}

    # Cuantos deberian haber entrenado hoy segun los dias de cada grupo.
    esperados = 0
    grupos_hoy = []
    for categoria in categorias:
        if categoria.entrena_hoy(dia):
            grupos_hoy.append(categoria)
            esperados += categoria.total_jugadores_activos()

    presentes = por_estado.get(ASISTENCIA_PRESENTE, 0)
    atrasos = por_estado.get(ASISTENCIA_ATRASO, 0)
    marcados = sum(por_estado.values())

    return {
        'presentes': presentes,
        'faltas': por_estado.get(ASISTENCIA_FALTA, 0),
        'atrasos': atrasos,
        'justificados': por_estado.get(ASISTENCIA_JUSTIFICADO, 0),
        'marcados': marcados,
        'esperados': esperados,
        'grupos_hoy': grupos_hoy,
        'pendientes': max(esperados - marcados, 0),
        'porcentaje': round((presentes + atrasos) * 100.0 / marcados, 1) if marcados else 0.0,
    }


def cumpleanios_proximos(jugadores, dias=DIAS_CUMPLEANIOS):
    """Cumpleanios de los proximos dias, ordenados por cercania."""
    hoy = date.today()
    proximos = []
    for jugador in jugadores:
        if not jugador.fecha_nacimiento:
            continue
        try:
            siguiente = jugador.fecha_nacimiento.replace(year=hoy.year)
        except ValueError:  # 29 de febrero
            siguiente = jugador.fecha_nacimiento.replace(year=hoy.year, day=28)
        if siguiente < hoy:
            try:
                siguiente = siguiente.replace(year=hoy.year + 1)
            except ValueError:
                siguiente = siguiente.replace(year=hoy.year + 1, day=28)
        faltan = (siguiente - hoy).days
        if faltan <= dias:
            proximos.append({
                'jugador': jugador,
                'fecha': siguiente,
                'faltan': faltan,
                'cumple': jugador.edad() + (0 if faltan == 0 else 1),
                'es_hoy': faltan == 0,
            })
    return sorted(proximos, key=lambda x: x['faltan'])[:6]


def dinero_del_mes(dia):
    """Cuanto se cobro y cuanto falta de las mensualidades de este mes."""
    del_mes = Mensualidad.objects.filter(mes=dia.month, anio=dia.year)
    cobrado = del_mes.filter(estado=MENSUALIDAD_PAGADO).aggregate(t=Sum('valor'))['t'] or 0
    por_cobrar = del_mes.filter(estado=MENSUALIDAD_PENDIENTE).aggregate(t=Sum('valor'))['t'] or 0
    return {
        'cobrado': cobrado,
        'por_cobrar': por_cobrar,
        'generadas': del_mes.count(),
        'pagadas': del_mes.filter(estado=MENSUALIDAD_PAGADO).count(),
    }


def deuda_completa(maximo=6):
    """TODA la plata pendiente, no solo la de este mes.

    El usuario necesita el numero grande ("cuanto me deben") y quienes son los
    que mas deben, que casi nunca son los del atraso mas viejo.
    """
    pendientes = Mensualidad.objects.filter(
        estado=MENSUALIDAD_PENDIENTE
    ).select_related('jugador', 'jugador__categoria', 'jugador__representante')

    por_jugador = {}
    total = Decimal('0.00')
    vencido = Decimal('0.00')

    for mensualidad in pendientes:
        total += mensualidad.valor
        atrasada = mensualidad.esta_atrasada()
        if atrasada:
            vencido += mensualidad.valor

        fila = por_jugador.setdefault(mensualidad.jugador_id, {
            'jugador': mensualidad.jugador, 'meses': 0, 'total': Decimal('0.00'),
            'dias': 0, 'atrasados': 0,
        })
        fila['meses'] += 1
        fila['total'] += mensualidad.valor
        if atrasada:
            fila['atrasados'] += 1
            fila['dias'] = max(fila['dias'], mensualidad.dias_de_atraso())

    filas = sorted(por_jugador.values(), key=lambda x: (-x['total'], -x['dias']))
    return {
        'total': total,
        'vencido': vencido,
        'por_vencer': total - vencido,
        'cuantos': len(por_jugador),
        'top': filas[:maximo],
    }


def quienes_estan_bajando(jugadores, maximo=6):
    """Los que en su ultima prueba salieron peor que en la anterior.

    Se mira solo la ultima comparacion de cada indicador: interesa quien viene
    cayendo AHORA, para hablar con el y con la familia a tiempo.
    """
    filas = []
    for jugador in jugadores:
        bajas = jugador.retrocesos()
        if bajas:
            filas.append({'jugador': jugador, 'bajas': bajas, 'cuantos': len(bajas)})

    filas.sort(key=lambda x: -x['cuantos'])
    return filas[:maximo]


def deudores_del_dia(maximo=6):
    """Jugadores con mensualidades vencidas, del atraso mas viejo al mas nuevo."""
    atrasadas = [
        m for m in Mensualidad.objects.filter(estado=MENSUALIDAD_PENDIENTE)
        .select_related('jugador', 'jugador__categoria', 'jugador__representante')
        if m.esta_atrasada()
    ]

    por_jugador = {}
    for mensualidad in atrasadas:
        fila = por_jugador.setdefault(mensualidad.jugador_id, {
            'jugador': mensualidad.jugador, 'meses': 0, 'total': 0, 'dias': 0,
        })
        fila['meses'] += 1
        fila['total'] += mensualidad.valor
        fila['dias'] = max(fila['dias'], mensualidad.dias_de_atraso())

    filas = sorted(por_jugador.values(), key=lambda x: -x['dias'])
    return filas[:maximo]


@login_required(login_url=URL_LOGIN)
@secure_module
@last_access
def view(request):
    data = {}
    perfil = perfil_de(request.user)
    if perfil is None or not perfil.activo:
        return url_back(request)

    adduserdata(request, data)
    hoy = date.today()
    desde = hoy - timedelta(days=DIAS_VENTANA)

    categorias = list(categorias_permitidas(perfil).filter(activo=True).order_by('hora_inicio'))
    jugadores = jugadores_permitidos(perfil).filter(estado=JUGADOR_ACTIVO)

    data['title'] = 'Tablero'
    data['hoy'] = hoy
    data['dias_ventana'] = DIAS_VENTANA
    data['es_administrador'] = perfil.es_administrador()

    # ---- numeros grandes ---------------------------------------------
    data['total_jugadores'] = jugadores.count()
    data['total_categorias'] = len(categorias)
    data['asistencia'] = asistencia_del_dia(categorias, hoy)

    if perfil.es_administrador():
        data['solicitudes_nuevas'] = SolicitudInscripcion.objects.filter(estado=SOLICITUD_NUEVA).count()
        data['dinero'] = dinero_del_mes(hoy)
        data['deudores'] = deudores_del_dia()
        data['deuda'] = deuda_completa()

    # ---- resumen por grupo -------------------------------------------
    resumen_grupos = []
    for categoria in categorias:
        registros = Asistencia.objects.filter(categoria=categoria, fecha__gte=desde)
        total = registros.count()
        asistio = registros.filter(estado__in=[ASISTENCIA_PRESENTE, ASISTENCIA_ATRASO]).count()
        resumen_grupos.append({
            'categoria': categoria,
            'jugadores': categoria.total_jugadores_activos(),
            'asistencia': round(asistio * 100.0 / total, 1) if total else None,
            'entreno_hoy': categoria.entrena_hoy(hoy),
            'fuera_de_rango': len(categoria.jugadores_fuera_de_rango()),
        })
    data['grupos'] = resumen_grupos

    # ---- a quien hay que mirar ---------------------------------------
    en_alerta = []
    for jugador in jugadores.select_related('categoria'):
        resumen = jugador.resumen_asistencia(desde=desde)
        if resumen['total'] >= 3 and resumen['porcentaje'] < ASISTENCIA_BAJA:
            en_alerta.append({'jugador': jugador, 'resumen': resumen})
    en_alerta.sort(key=lambda x: x['resumen']['porcentaje'])
    data['en_alerta'] = en_alerta[:8]
    data['asistencia_baja'] = ASISTENCIA_BAJA

    # ---- ultimas evaluaciones ----------------------------------------
    evaluaciones = Evaluacion.objects.filter(categoria__in=categorias).select_related(
        'categoria', 'tipo').order_by('-fecha')[:5]
    data['evaluaciones'] = evaluaciones
    data['sin_evaluar'] = jugadores.filter(mediciones__isnull=True).distinct().count()
    data['bajando'] = quienes_estan_bajando(jugadores.select_related('categoria'))

    # ---- cumpleanios --------------------------------------------------
    data['cumpleanios'] = cumpleanios_proximos(list(jugadores))

    # ---- quien esta a cargo de lo de hoy ------------------------------
    data['clases_hoy'] = grupos_de_hoy(categorias, hoy)
    data['mis_grupos'] = grupos_a_cargo_de(perfil.entrenador(), categorias)

    return render(request, 'dashboard/view.html', data)
