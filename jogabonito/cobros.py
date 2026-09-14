# coding=utf-8
"""El cobro que se genera solo.

La idea es simple: cada jugador tiene su propio ciclo, que arranca el dia en
que ingreso a la academia. Cuando su mes se termina, el sistema le abre el
siguiente desde el dia despues, sin esperar a que alguien apriete un boton y
sin importar si pago o no el anterior (si sigue viniendo, sigue debiendo).

Se corta en dos casos:
  1. el jugador ya no esta activo (se retiro),
  2. le apagaron el interruptor "cobrarle cada mes".

Esto se ejecuta cuando se abre el modulo de mensualidades y tambien con el
comando "poner_al_dia", por si algun dia se quiere dejar programado.
"""
from datetime import date

from jogabonito.models import JUGADOR_ACTIVO, MENSUALIDAD_PENDIENTE, Jugador, Mensualidad

# Tope de seguridad: si algo se descuadra, no se generan meses sin fin.
MAXIMO_MESES_ATRASADOS = 24


def crear_mensualidad(jugador, inicio, fin, request=None):
    """Abre el mes del jugador con el precio que tiene hoy."""
    valor = jugador.valor_mensual_vigente()
    mensualidad = Mensualidad(
        jugador=jugador,
        mes=inicio.month,
        anio=inicio.year,
        valor=valor,
        valor_completo=valor,
        descuento_aplicado=jugador.descuento,
        periodo_inicio=inicio,
        periodo_fin=fin,
        fecha_vencimiento=inicio,
        estado=MENSUALIDAD_PENDIENTE,
    )
    mensualidad.save(request)
    return mensualidad


def poner_al_dia_jugador(jugador, hasta=None, request=None):
    """Le abre los meses que le falten hasta hoy. Devuelve los que creo."""
    hasta = hasta or date.today()
    creadas = []

    if not jugador.se_le_cobra():
        return creadas

    for _ in range(MAXIMO_MESES_ATRASADOS):
        periodo = jugador.proximo_periodo()
        if not periodo:
            break

        inicio, fin = periodo
        if inicio > hasta:
            break  # todavia no le toca

        if Mensualidad.objects.filter(jugador=jugador, periodo_inicio=inicio).exists():
            break  # ese periodo ya esta abierto

        creadas.append(crear_mensualidad(jugador, inicio, fin, request))

    return creadas


def poner_al_dia(hasta=None, request=None, categoria=None):
    """Recorre a todos los que se les cobra y les abre los meses que falten."""
    jugadores = Jugador.objects.filter(
        estado=JUGADOR_ACTIVO, cobro_activo=True).select_related('categoria')
    if categoria:
        jugadores = jugadores.filter(categoria=categoria)

    creadas = 0
    alcanzados = 0
    for jugador in jugadores:
        nuevas = poner_al_dia_jugador(jugador, hasta, request)
        if nuevas:
            creadas += len(nuevas)
            alcanzados += 1

    return {'creadas': creadas, 'jugadores': alcanzados}


def texto_resultado(resultado):
    """Lo que se le muestra al usuario despues de poner al dia."""
    if not resultado['creadas']:
        return 'Todo esta al dia: nadie tenia un mes pendiente de abrir.'

    return 'Se abrieron %s mensualidad%s de %s jugador%s.' % (
        resultado['creadas'], '' if resultado['creadas'] == 1 else 'es',
        resultado['jugadores'], '' if resultado['jugadores'] == 1 else 'es',
    )


def proximos_cobros():
    """Cuando le toca el siguiente mes a cada jugador que se cobra.

    Es la pantalla de control: sirve para ver, sin crear nada, que el cobro de
    cada uno cae el dia que le corresponde segun cuando entro.
    """
    hoy = date.today()
    filas = []

    jugadores = Jugador.objects.filter(
        estado=JUGADOR_ACTIVO, cobro_activo=True).select_related('categoria')

    for jugador in jugadores:
        periodo = jugador.proximo_periodo()
        if not periodo:
            continue
        inicio, fin = periodo
        filas.append({
            'jugador': jugador,
            'inicio': inicio,
            'fin': fin,
            'ya_toca': inicio <= hoy,
            'faltan': (inicio - hoy).days,
        })

    filas.sort(key=lambda x: x['inicio'])
    return filas


def a_quienes_les_falta():
    """Solo los que ya tienen un mes por abrir hoy."""
    return [fila for fila in proximos_cobros() if fila['ya_toca']]
