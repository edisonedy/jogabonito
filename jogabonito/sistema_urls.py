from django.urls import path

import jogabonito.adm_asistencia
import jogabonito.adm_categoria
import jogabonito.adm_entrenador
import jogabonito.adm_evaluacion
import jogabonito.adm_indicador
import jogabonito.adm_jugador
import jogabonito.adm_representante
import jogabonito.adm_solicitud
import jogabonito.commonviews

urlpatterns = [
    path('', jogabonito.commonviews.panel, name='panel'),
    path('login/', jogabonito.commonviews.login_user, name='login'),
    path('logout/', jogabonito.commonviews.logout_user, name='logout'),
    path('micuenta', jogabonito.commonviews.micuenta, name='micuenta'),
    path('pass', jogabonito.commonviews.passwd, name='passwd'),

    path('adm_entrenador', jogabonito.adm_entrenador.view, name='adm_entrenador'),
    path('adm_categoria', jogabonito.adm_categoria.view, name='adm_categoria'),
    path('adm_representante', jogabonito.adm_representante.view, name='adm_representante'),
    path('adm_jugador', jogabonito.adm_jugador.view, name='adm_jugador'),
    path('adm_asistencia', jogabonito.adm_asistencia.view, name='adm_asistencia'),
    path('adm_solicitud', jogabonito.adm_solicitud.view, name='adm_solicitud'),
    path('adm_evaluacion', jogabonito.adm_evaluacion.view, name='adm_evaluacion'),
    path('adm_indicador', jogabonito.adm_indicador.view, name='adm_indicador'),
]
