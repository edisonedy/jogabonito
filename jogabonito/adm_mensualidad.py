# coding=utf-8
"""Modulo: mensualidades.

Como funciona el precio de cada jugador:
  1. todos pagan el valor de su categoria (por ejemplo 25 dolares),
  2. si tiene descuento (beca, hermano, convenio), se le resta el porcentaje,
  3. si aviso que no viene unos dias, se le cobran solo los dias que si entrena.

No existe un precio por jugador: el precio vive en el grupo. Lo que si queda
fijo es lo YA generado, porque el valor se copia a la mensualidad.

Cada jugador vence el mismo dia del mes en que ingreso: si entro un 22, se le
cobra el 22 de cada mes. Y no se le generan meses anteriores a su ingreso.

Al abrir el mes, el valor se COPIA a la mensualidad. Asi, si maniana suben
los precios, lo que ya se genero no cambia.

El mes siguiente se abre SOLO: cuando termina un periodo, el sistema arranca
el que sigue al dia siguiente (ver cobros.py). Deja de hacerlo si el jugador
se retira o si le apagan el interruptor "cobrarle cada mes".
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import render

from jogabonito.cobros import crear_mensualidad, poner_al_dia, proximos_cobros, texto_resultado
from jogabonito.commonviews import adduserdata
from jogabonito.decorators import URL_LOGIN, last_access, secure_module, solo_administrador
from jogabonito.forms import (
    CobroRapidoForm, MensualidadForm, MensualidadNuevaForm, PrecioJugadorForm,
)
from jogabonito.funciones import bad_json, ok_json, paginar, url_back
from jogabonito.models import (
    ESTADOS_MENSUALIDAD, FORMAS_PAGO, JUGADOR_ACTIVO, MENSUALIDAD_EXONERADO, MENSUALIDAD_PAGADO,
    MENSUALIDAD_PENDIENTE, MESES, Categoria, Jugador, Mensualidad, dia_del_mes,
)

MODULO = 'adm_mensualidad'
DIA_DE_VENCIMIENTO = 10
ESTADOS_VALIDOS = dict(ESTADOS_MENSUALIDAD)
FORMAS_VALIDAS = dict(FORMAS_PAGO)


def primer_error(form):
    return next(iter(form.errors.values()))[0]


def fecha_de_vencimiento(mes, anio, dia=DIA_DE_VENCIMIENTO):
    """Ese dia del mes, o el ultimo si el mes es mas corto (31 en febrero)."""
    return dia_del_mes(anio, mes, dia)


def periodo_del_jugador(jugador, mes, anio):
    """Los dias que cubre la mensualidad de ese jugador en ese mes.

    Arranca el dia en que ingreso y termina el dia anterior del mes siguiente.
    Si entro un 13, su periodo va del 13 de este mes al 12 del siguiente, y por
    eso no siempre son 30 dias: puede ser 28, 29, 30 o 31.
    """
    return jugador.periodo_de_cobro(mes, anio)


def ficha_de_precio(jugador):
    """Lo que la pantalla necesita saber del jugador para sugerir fechas."""
    return {
        'dia': jugador.dia_de_cobro(),
        'valor': '%s' % jugador.valor_mensual_vigente(),
        'grupo': jugador.categoria.nombre,
        'explicacion': jugador.explicacion_precio(),
        'ingreso': jugador.fecha_ingreso.strftime('%d/%m/%Y') if jugador.fecha_ingreso else '',
    }


def periodo_pedido(request, clave_mes='mes', clave_anio='anio'):
    """Mes y anio de la pantalla; por defecto, el mes en curso."""
    hoy = date.today()
    try:
        mes = int(request.GET.get(clave_mes) or request.POST.get(clave_mes) or hoy.month)
        anio = int(request.GET.get(clave_anio) or request.POST.get(clave_anio) or hoy.year)
    except (TypeError, ValueError):
        return hoy.month, hoy.year
    if mes < 1 or mes > 12 or anio < 2000 or anio > hoy.year + 5:
        return hoy.month, hoy.year
    return mes, anio


def resumen_del_mes(mes, anio):
    """Cuanto se cobro, cuanto falta y cuantos estan atrasados."""
    del_mes = Mensualidad.objects.filter(mes=mes, anio=anio)
    cobrado = del_mes.filter(estado=MENSUALIDAD_PAGADO).aggregate(t=Sum('valor'))['t'] or Decimal('0.00')
    pendiente = del_mes.filter(estado=MENSUALIDAD_PENDIENTE).aggregate(t=Sum('valor'))['t'] or Decimal('0.00')
    atrasadas = [m for m in del_mes.filter(estado=MENSUALIDAD_PENDIENTE) if m.esta_atrasada()]

    return {
        'generadas': del_mes.count(),
        'pagadas': del_mes.filter(estado=MENSUALIDAD_PAGADO).count(),
        'pendientes': del_mes.filter(estado=MENSUALIDAD_PENDIENTE).count(),
        'exoneradas': del_mes.filter(estado=MENSUALIDAD_EXONERADO).count(),
        'atrasadas': len(atrasadas),
        'cobrado': cobrado,
        'por_cobrar': pendiente,
    }


@login_required(login_url=URL_LOGIN)
@secure_module
@solo_administrador
@last_access
@transaction.atomic()
def view(request):
    data = {}

    if request.method == 'POST':
        action = request.POST.get('action')

        # ---- generar las mensualidades del mes -----------------------
        if action == 'generar':
            try:
                mes, anio = periodo_pedido(request)

                categoria_id = request.POST.get('categoria')
                jugadores = Jugador.objects.filter(estado=JUGADOR_ACTIVO).select_related('categoria')
                if categoria_id:
                    jugadores = jugadores.filter(categoria_id=int(categoria_id))

                ya_generadas = set(
                    Mensualidad.objects.filter(mes=mes, anio=anio).values_list('jugador_id', flat=True)
                )
                # Tambien se respeta el periodo exacto, por si alguien corrigio fechas.
                periodos_abiertos = set(
                    Mensualidad.objects.filter(periodo_inicio__isnull=False).values_list(
                        'jugador_id', 'periodo_inicio')
                )

                creadas = 0
                sin_ingresar = 0
                for jugador in jugadores:
                    if jugador.id in ya_generadas:
                        continue  # nunca se pisa lo que ya existe
                    if not jugador.ya_estaba_en(mes, anio):
                        sin_ingresar += 1
                        continue  # todavia no entraba a la academia ese mes

                    valor = jugador.valor_mensual_vigente()
                    inicio, fin = periodo_del_jugador(jugador, mes, anio)
                    if (jugador.id, inicio) in periodos_abiertos:
                        continue
                    Mensualidad(
                        jugador=jugador,
                        mes=mes,
                        anio=anio,
                        valor=valor,
                        valor_completo=valor,
                        descuento_aplicado=jugador.descuento,
                        periodo_inicio=inicio,
                        periodo_fin=fin,
                        fecha_vencimiento=inicio,
                    ).save(request)
                    creadas += 1

                if creadas:
                    mensaje = 'Se generaron %s mensualidades.' % creadas
                else:
                    mensaje = 'No habia nada que generar en ese mes.'
                if sin_ingresar:
                    mensaje += ' %s jugador%s todavia no habia ingresado.' % (
                        sin_ingresar, '' if sin_ingresar == 1 else 'es')

                return ok_json({'mensaje': mensaje})
            except (TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- abrir los meses que falten a todos ----------------------
        if action == 'aldia':
            try:
                resultado = poner_al_dia(request=request)
                return ok_json({'mensaje': texto_resultado(resultado)})
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- abrirle el siguiente mes a UNO, de un solo clic ---------
        if action == 'siguiente':
            try:
                jugador = Jugador.objects.select_related('categoria').get(pk=int(request.POST['id']))

                if jugador.estado != JUGADOR_ACTIVO:
                    return bad_json(mensaje='%s no esta activo. Activalo primero si volvio.'
                                            % jugador.nombre_completo())

                periodo = jugador.proximo_periodo()
                if not periodo:
                    return bad_json(mensaje='No se sabe desde cuando cobrarle: '
                                            'revisa su fecha de ingreso.')

                inicio, fin = periodo
                if Mensualidad.objects.filter(jugador=jugador, periodo_inicio=inicio).exists():
                    return bad_json(mensaje='Ese mes ya esta abierto.')

                mensualidad = crear_mensualidad(jugador, inicio, fin, request)
                return ok_json({'mensaje': 'Listo: %s del %s al %s, %s.' % (
                    mensualidad.periodo(),
                    inicio.strftime('%d/%m'), fin.strftime('%d/%m/%Y'),
                    mensualidad.valor,
                )})
            except Jugador.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- cobrarle el mes a UN jugador ----------------------------
        if action == 'add':
            try:
                form = MensualidadNuevaForm(request.POST)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))

                mensualidad = form.save(commit=False)
                mensualidad.valor_completo = mensualidad.valor
                mensualidad.descuento_aplicado = mensualidad.jugador.descuento
                mensualidad.fecha_vencimiento = mensualidad.periodo_inicio
                mensualidad.estado = MENSUALIDAD_PENDIENTE
                mensualidad.save(request)

                return ok_json({'mensaje': 'Listo: %s debe %s de %s (%s).' % (
                    mensualidad.jugador.nombre_completo(),
                    mensualidad.valor,
                    mensualidad.periodo(),
                    mensualidad.texto_periodo(),
                )})
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- cobrar rapido: llego, pago, listo -----------------------
        if action == 'cobrar':
            try:
                mensualidad = Mensualidad.objects.get(pk=int(request.POST['id']))
                if mensualidad.esta_pagada():
                    return bad_json(mensaje='Esa mensualidad ya estaba pagada.')

                form = CobroRapidoForm(request.POST, instance=mensualidad)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))

                mensualidad = form.save(commit=False)
                mensualidad.estado = MENSUALIDAD_PAGADO
                mensualidad.save(request)

                return ok_json({'mensaje': 'Cobrado: %s de %s, %s.' % (
                    mensualidad.valor, mensualidad.jugador.nombre_completo(),
                    mensualidad.periodo())})
            except Mensualidad.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- registrar el pago (pantalla completa) -------------------
        if action == 'pagar':
            try:
                mensualidad = Mensualidad.objects.get(pk=int(request.POST['id']))
                form = MensualidadForm(request.POST, instance=mensualidad)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))

                mensualidad = form.save(commit=False)
                mensualidad.recalcular_por_ausencia()
                if mensualidad.estado == MENSUALIDAD_PAGADO and not mensualidad.fecha_pago:
                    mensualidad.fecha_pago = date.today()
                if mensualidad.estado != MENSUALIDAD_PAGADO:
                    mensualidad.fecha_pago = None
                    mensualidad.forma_pago = None
                mensualidad.save(request)
                return ok_json({'mensaje': 'Mensualidad actualizada.'})
            except Mensualidad.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- descuento del jugador -----------------------------------
        if action == 'precio':
            try:
                jugador = Jugador.objects.get(pk=int(request.POST['id']))
                form = PrecioJugadorForm(request.POST, instance=jugador)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))
                jugador = form.save(commit=False)
                jugador.save(request)
                if jugador.cobro_activo:
                    aviso = 'Listo: paga %s al mes y se le sigue cobrando cada mes.'
                else:
                    aviso = 'Listo: paga %s al mes, pero ya no se le abriran meses nuevos.'
                return ok_json({'mensaje': aviso % jugador.valor_mensual_vigente()})
            except Jugador.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        if action == 'delete':
            try:
                mensualidad = Mensualidad.objects.get(pk=int(request.POST['id']))
                if mensualidad.esta_pagada():
                    return bad_json(mensaje='No se puede borrar una mensualidad ya pagada. '
                                            'Si fue un error, cambiala a pendiente primero.')
                mensualidad.delete()
                return ok_json({'mensaje': 'Mensualidad eliminada.'})
            except Mensualidad.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=2, ex=ex)

        return bad_json(error=0)

    # ----------------------------- GET --------------------------------
    adduserdata(request, data)
    action = request.GET.get('action')
    mes, anio = periodo_pedido(request)

    if action in ('cobrar', 'pagar', 'delete'):
        try:
            mensualidad = Mensualidad.objects.get(pk=int(request.GET['id']))
        except (Mensualidad.DoesNotExist, KeyError, ValueError):
            return url_back(request)

        data['mensualidad'] = mensualidad

        if action == 'delete':
            data['title'] = 'Eliminar mensualidad'
            return render(request, 'adm_mensualidad/delete.html', data)

        if action == 'cobrar':
            data['title'] = 'Cobrar %s' % mensualidad.periodo()
            data['form'] = CobroRapidoForm(instance=mensualidad)
            return render(request, 'adm_mensualidad/cobrar.html', data)

        data['title'] = 'Editar %s' % mensualidad.periodo()
        data['form'] = MensualidadForm(instance=mensualidad)
        return render(request, 'adm_mensualidad/pagar.html', data)

    if action == 'siguiente':
        try:
            jugador = Jugador.objects.select_related('categoria').get(pk=int(request.GET['id']))
        except (Jugador.DoesNotExist, KeyError, ValueError):
            return url_back(request)

        data['title'] = 'Abrir el siguiente mes'
        data['jugador'] = jugador
        data['proximo'] = jugador.proximo_periodo()
        data['valor'] = jugador.valor_mensual_vigente()
        return render(request, 'adm_mensualidad/siguiente.html', data)

    if action == 'aldia':
        data['title'] = 'Como se cobra cada mes'
        data['proximos'] = proximos_cobros()
        data['pausados'] = Jugador.objects.filter(
            estado=JUGADOR_ACTIVO, cobro_activo=False).select_related('categoria')
        data['mes'] = mes
        data['anio'] = anio
        return render(request, 'adm_mensualidad/aldia.html', data)

    if action == 'add':
        data['title'] = 'Cobrar a un solo jugador'
        activos = Jugador.objects.filter(estado=JUGADOR_ACTIVO).select_related('categoria')
        inicial = {'mes': mes, 'anio': anio}

        try:
            elegido = activos.get(pk=int(request.GET['jugador']))
            inicio, fin = elegido.periodo_de_cobro(mes, anio)
            inicial['jugador'] = elegido.id
            inicial['periodo_inicio'] = inicio
            inicial['periodo_fin'] = fin
            inicial['valor'] = elegido.valor_mensual_vigente()
        except (Jugador.DoesNotExist, KeyError, TypeError, ValueError):
            pass

        data['form'] = MensualidadNuevaForm(initial=inicial)
        data['fichas'] = {'%s' % j.id: ficha_de_precio(j) for j in activos}
        return render(request, 'adm_mensualidad/add.html', data)

    if action == 'precio':
        try:
            jugador = Jugador.objects.get(pk=int(request.GET['id']))
        except (Jugador.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Precio de %s' % jugador.nombre_completo()
        data['jugador'] = jugador
        data['proximo'] = jugador.proximo_periodo()
        data['form'] = PrecioJugadorForm(instance=jugador)
        return render(request, 'adm_mensualidad/precio.html', data)

    if action == 'generar':
        data['title'] = 'Generar mensualidades'
        data['mes'] = mes
        data['anio'] = anio
        data['meses'] = MESES
        data['categorias'] = Categoria.objects.filter(activo=True).order_by('hora_inicio')
        data['resumen'] = resumen_del_mes(mes, anio)
        data['activos'] = Jugador.objects.filter(estado=JUGADOR_ACTIVO).count()
        return render(request, 'adm_mensualidad/generar.html', data)

    if action == 'deudores':
        data['title'] = 'Quien debe'
        deudores = []
        for jugador in Jugador.objects.filter(
            estado=JUGADOR_ACTIVO, mensualidades__estado=MENSUALIDAD_PENDIENTE
        ).select_related('categoria', 'representante').distinct():
            pendientes = list(jugador.mensualidades_pendientes())
            atrasadas = [m for m in pendientes if m.esta_atrasada()]
            deudores.append({
                'jugador': jugador,
                'meses': len(pendientes),
                'total': jugador.total_que_debe(),
                'atrasadas': len(atrasadas),
                'dias': jugador.dias_de_atraso(),
                'detalle': pendientes,
            })
        deudores.sort(key=lambda x: (-x['dias'], -x['meses']))
        data['deudores'] = deudores
        return render(request, 'adm_mensualidad/deudores.html', data)

    # ---- listado del mes ---------------------------------------------
    # Al entrar al modulo se abren solos los meses que ya vencieron: nadie
    # tiene que acordarse de generar nada.
    recien_abiertas = poner_al_dia(request=request)
    if recien_abiertas['creadas']:
        data['aviso_automatico'] = texto_resultado(recien_abiertas)

    data['title'] = 'Mensualidades'
    mensualidades = Mensualidad.objects.filter(mes=mes, anio=anio).select_related(
        'jugador', 'jugador__categoria')

    buscar = (request.GET.get('s') or '').strip()
    if buscar:
        mensualidades = mensualidades.filter(
            Q(jugador__nombres__icontains=buscar) | Q(jugador__apellidos__icontains=buscar)
        )

    categoria_id = request.GET.get('categoria')
    if categoria_id:
        try:
            mensualidades = mensualidades.filter(jugador__categoria_id=int(categoria_id))
            data['categoria_id'] = int(categoria_id)
        except (TypeError, ValueError):
            pass

    estado = request.GET.get('estado')
    if estado == 'atrasadas':
        pendientes = mensualidades.filter(estado=MENSUALIDAD_PENDIENTE)
        ids = [m.id for m in pendientes if m.esta_atrasada()]
        mensualidades = mensualidades.filter(id__in=ids)
        data['estado_id'] = 'atrasadas'
    elif estado:
        try:
            mensualidades = mensualidades.filter(estado=int(estado))
            data['estado_id'] = int(estado)
        except (TypeError, ValueError):
            pass

    data['search'] = buscar
    data['mes'] = mes
    data['anio'] = anio
    data['meses'] = MESES
    data['anios'] = range(date.today().year - 2, date.today().year + 2)
    data['estados'] = ESTADOS_MENSUALIDAD
    data['categorias'] = Categoria.objects.filter(activo=True).order_by('hora_inicio')
    data['resumen'] = resumen_del_mes(mes, anio)
    data['mensualidades'] = paginar(request, mensualidades.order_by(
        'jugador__apellidos', 'jugador__nombres'), data, MODULO, por_pagina=40)
    return render(request, 'adm_mensualidad/view.html', data)
