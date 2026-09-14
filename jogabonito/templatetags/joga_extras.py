# coding=utf-8
"""Filtros propios de las plantillas.

La tela de arania se calcula aqui para que el SVG quede limpio: el lienzo es de
300x240, el centro esta en (150, 112) y el radio maximo es 80, de modo que las
etiquetas de alrededor entren sin cortarse.

OJO: todas las coordenadas salen ya como TEXTO con punto decimal. Si se
devolvieran numeros, Django los escribiria con coma (el idioma es es-EC) y el
SVG los descartaria por invalidos.
"""
import math

from django import template

register = template.Library()

CENTRO_X = 150.0
CENTRO_Y = 112.0
RADIO = 80.0
RADIO_ETIQUETAS = 92.0


def angulo_del_eje(indice, total):
    """Primer eje arriba, los demas en sentido horario."""
    return (2 * math.pi * indice / (total or 1)) - (math.pi / 2)


def coordenada(valor):
    return '%.1f' % valor


@register.filter
def poligono_radar(ejes, radio=RADIO):
    """Puntos del poligono que dibuja el rendimiento del jugador."""
    try:
        radio = float(radio)
    except (TypeError, ValueError):
        radio = RADIO

    total = len(ejes)
    puntos = []
    for indice, eje in enumerate(ejes):
        angulo = angulo_del_eje(indice, total)
        distancia = (float(eje['puntaje']) / 100.0) * radio
        puntos.append('%s,%s' % (
            coordenada(CENTRO_X + distancia * math.cos(angulo)),
            coordenada(CENTRO_Y + distancia * math.sin(angulo)),
        ))
    return ' '.join(puntos)


@register.filter
def vertices_radar(ejes, radio=RADIO):
    """Un punto por eje, para marcar el valor sobre la tela."""
    try:
        radio = float(radio)
    except (TypeError, ValueError):
        radio = RADIO

    total = len(ejes)
    vertices = []
    for indice, eje in enumerate(ejes):
        angulo = angulo_del_eje(indice, total)
        distancia = (float(eje['puntaje']) / 100.0) * radio
        vertices.append({
            'x': coordenada(CENTRO_X + distancia * math.cos(angulo)),
            'y': coordenada(CENTRO_Y + distancia * math.sin(angulo)),
            'eje': eje,
        })
    return vertices


@register.filter
def etiquetas_radar(ejes, radio=RADIO_ETIQUETAS):
    """Posicion y alineacion de cada etiqueta alrededor de la tela."""
    try:
        radio = float(radio)
    except (TypeError, ValueError):
        radio = RADIO_ETIQUETAS

    total = len(ejes)
    etiquetas = []
    for indice, eje in enumerate(ejes):
        angulo = angulo_del_eje(indice, total)
        x = CENTRO_X + radio * math.cos(angulo)
        y = CENTRO_Y + radio * math.sin(angulo)

        if abs(x - CENTRO_X) < 1:
            anclaje = 'middle'
        elif x > CENTRO_X:
            anclaje = 'start'
        else:
            anclaje = 'end'

        # Las de abajo bajan un poco mas para no pisar la tela.
        if y > CENTRO_Y + 1:
            y += 10
        elif abs(y - CENTRO_Y) < 1:
            y += 4

        etiquetas.append({
            'x': coordenada(x),
            'y': coordenada(y),
            'y_valor': coordenada(y + 12),
            'anclaje': anclaje,
            'eje': eje,
        })
    return etiquetas


@register.filter
def linea_radar(ejes, radio=RADIO):
    """Rayos del centro a cada vertice, para el fondo de la tela."""
    try:
        radio = float(radio)
    except (TypeError, ValueError):
        radio = RADIO

    total = len(ejes)
    return [
        {
            'x': coordenada(CENTRO_X + radio * math.cos(angulo_del_eje(indice, total))),
            'y': coordenada(CENTRO_Y + radio * math.sin(angulo_del_eje(indice, total))),
        }
        for indice in range(total)
    ]
