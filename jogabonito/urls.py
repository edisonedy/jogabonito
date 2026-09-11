from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

import jogabonito.commonviews
import jogabonito.landing

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', jogabonito.commonviews.login_user, name='root_login'),
    path('logout/', jogabonito.commonviews.logout_user, name='root_logout'),

    # Sistema interno
    path('sistema/', include('jogabonito.sistema_urls')),

    # Pagina publica de la academia (y formulario de inscripcion).
    path('', jogabonito.landing.home, name='landing'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
